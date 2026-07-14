import os
import numpy as np
import osmnx as ox
import pandas as pd
import folium
from sklearn.neighbors import BallTree

# 설정값
place = "Gwangjin-gu, Seoul, South Korea"
graph_path = "gwangjin.graphml"

# 임시 CSV 파일사용, 추후 변경예정
grid_path = "route/temp__safety_grid.csv"

# 현재 임시 테스트용 CSV 기준 컬럼명
LAT_COL = "위도"
LON_COL = "경도"
SCORE_COL = "안전점수"
GRADE_COL = "안전등급"

# 최종 CSV에 추가할 예정인 컬럼들
# GRID_ID_COL = "grid_id"                      # 추가예정
# ROW_COL = "row"                               # 추가예정
# COL_COL = "col"                               # 추가예정
# GRID_SIZE_COL = "grid_size_m"                 # 추가예정
# CCTV_COUNT_COL = "cctv_count"                 # 추가예정
# STREETLIGHT_COUNT_COL = "streetlight_count"   # 추가예정
# EMERGENCY_BELL_COUNT_COL = "emergency_bell_count"  # 추가예정
# POLICE_COUNT_COL = "police_count"             # 추가예정

# 안전 가중치 튜닝 파라미터
# 0 = 시간만 최적화, 1 = 안전만 최적화
ALPHA_DEFAULT = 0.5

# 안전경로 추천 임계값 (최단경로 대비 시간 증가율)
TIME_INCREASE_THRESHOLD = 0.15

# 지도 시각화에 사용할 타일
# "CartoDB positron" : 깔끔하고 UI에 얹기 좋음
# "OpenStreetMap"    : 지명/상호 등 정보량이 많음
MAP_TILES = "CartoDB positron"

# 결과 지도를 저장할 경로 (팀원 공유 / 발표용)
MAP_OUTPUT_PATH = "route_map.html"


# 그래프 다운로드 (없으면 다운로드, 있으면 재사용)
def load_graph():
    if os.path.exists(graph_path):
        G = ox.load_graphml(graph_path)
        print("저장된 그래프 불러옴")
    else:
        G = ox.graph_from_place(place, network_type="walk")
        ox.save_graphml(G, graph_path)
        print("그래프 새로 다운로드 및 저장")

    print(f"노드 수 : {len(G.nodes)}")
    print(f"엣지 수 : {len(G.edges)}")

    # travel_time을 사용하기 위해 반드시 필요(속도, 이동시간 계산)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    return G


# safety_grid.csv 읽기(현재는 테스트용)
def load_safety_grid():
    # 파일 경로 읽기
    grid = pd.read_csv(grid_path, encoding="utf-8-sig")

    # 설정한 한글 컬럼명들이 파일에 존재하는지 확인
    missing = [c for c in (LAT_COL, LON_COL, SCORE_COL) if c not in grid.columns]
    if missing:
        raise ValueError(f"safety_grid.csv에 다음 컬럼이 없습니다: {missing}")

    # GRADE_COL(안전등급)은 아직 사용 안 함 (추가예정)
    if GRADE_COL not in grid.columns:
        print(f"참고: {GRADE_COL} 컬럼 없음 (지금은 사용 안 하므로 무시)")

    return grid


# 모든 노드에 안전점수 매핑
def attach_safety_scores(G, grid):
    print("노드 안전점수 계산중...")

    # BallTree는 [lat, lon] 순서, 라디안 단위 필요
    grid_rad = np.radians(grid[[LAT_COL, LON_COL]].values)
    tree = BallTree(grid_rad, metric="haversine")

    node_ids = list(G.nodes)
    node_coords = np.radians(
        [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in node_ids]
    )

    # k=1 : 가장 가까운 격자 1개만 조회
    _, idx = tree.query(node_coords, k=1)

    scores = grid[SCORE_COL].values

    for i, node in enumerate(node_ids):
        G.nodes[node]["safety_score"] = scores[idx[i][0]]

    print("완료")
    return G


# 모든 엣지에 safe_weight 생성
def attach_safe_weights(G, alpha=ALPHA_DEFAULT):
    print(f"안전 weight 생성중... (alpha={alpha})")

    for u, v, key, data in G.edges(keys=True, data=True):
        score1 = G.nodes[u]["safety_score"]
        score2 = G.nodes[v]["safety_score"]
        avg_score = (score1 + score2) / 2

        time = data["travel_time"]
        safety_penalty = (100 - avg_score) / 100  # 0 ~ 1 범위

        # 시간을 기본값으로 하고, 안전점수가 낮을수록 페널티를 더함
        data["safe_weight"] = time * (1 + alpha * safety_penalty)

    print("완료")
    return G


# 경로 요약 (거리/시간/좌표)
# 나중에 UI 연동을 위해 구조화된 dict로 반환
def summarize_route(G, route):
    gdf = ox.routing.route_to_gdf(G, route)
    coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route]

    return {
        "nodes": route,
        "distance_m": float(gdf["length"].sum()),
        "time_min": float(gdf["travel_time"].sum() / 60),
        "coords": coords,
    }


# 출발/도착 좌표를 받아
# 최단경로/안전경로를 모두 계산하고
# 추천 경로까지 판단해서 반환
def find_route(G, orig_lat, orig_lon, dest_lat, dest_lon, alpha=ALPHA_DEFAULT):
    G = attach_safe_weights(G, alpha=alpha)

    orig_node = ox.distance.nearest_nodes(G, X=orig_lon, Y=orig_lat)
    dest_node = ox.distance.nearest_nodes(G, X=dest_lon, Y=dest_lat)

    fast_route = ox.shortest_path(G, orig_node, dest_node, weight="travel_time")
    safe_route = ox.shortest_path(G, orig_node, dest_node, weight="safe_weight")

    fast = summarize_route(G, fast_route)
    safe = summarize_route(G, safe_route)

    if fast["time_min"] > 0:
        time_increase = (safe["time_min"] - fast["time_min"]) / fast["time_min"]
    else:
        time_increase = 0

    recommended = "safe" if time_increase <= TIME_INCREASE_THRESHOLD else "fast"

    return {
        "fast": fast,
        "safe": safe,
        "time_increase_ratio": time_increase,
        "recommended": recommended,
    }


## 시각화 (Folium 기반 인터랙티브 지도)
# 파랑 실선 : 최단경로
# 초록 대시선 : 안전경로
# -> 회색 도로망 이미지 대신 실제 지도 타일(도로/건물/지명) 위에 경로를 그려서
#    훨씬 구체적으로 보이고, Streamlit에서 streamlit_folium.st_folium()으로
#    그대로 렌더링할 수 있음
def visualize(fast_route, safe_route, safety_grid=None):
    fast_coords = fast_route["coords"]
    safe_coords = safe_route["coords"]

    start_lat, start_lon = fast_coords[0]
    end_lat, end_lon = fast_coords[-1]

    m = folium.Map(
        location=[(start_lat + end_lat) / 2, (start_lon + end_lon) / 2],
        zoom_start=15,
        tiles=MAP_TILES,
        control_scale=True,
    )

    # 최단 경로 (파란 실선)
    folium.PolyLine(
        fast_coords,
        color="#1f77ff",
        weight=5,
        opacity=0.85,
        tooltip=f"최단 경로: {fast_route['distance_m']:.0f}m / {fast_route['time_min']:.1f}분",
    ).add_to(m)

    # 안전 경로 (초록 대시선 - 최단경로와 겹쳐도 구분되도록)
    folium.PolyLine(
        safe_coords,
        color="#2ca02c",
        weight=5,
        opacity=0.9,
        dash_array="8,6",
        tooltip=f"안전 경로: {safe_route['distance_m']:.0f}m / {safe_route['time_min']:.1f}분",
    ).add_to(m)

    # 출발/도착 마커
    folium.Marker(
        location=[start_lat, start_lon],
        popup=folium.Popup("<b>출발지</b>", max_width=200),
        icon=folium.Icon(color="black", icon="play", prefix="fa"),
    ).add_to(m)

    folium.Marker(
        location=[end_lat, end_lon],
        popup=folium.Popup("<b>도착지</b>", max_width=200),
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
    ).add_to(m)
    

    # 범례
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background-color: white; padding: 10px 14px; border-radius: 8px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 13px;">
        <b>범례</b><br>
        <span style="color:#1f77ff;">━━</span> 최단 경로<br>
        <span style="color:#2ca02c;">┅┅</span> 안전 경로
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


# 실행부
if __name__ == "__main__":
    G = load_graph()
    grid = load_safety_grid()
    G = attach_safety_scores(G, grid)

    print("출발지 좌표를 입력하세요 (예: 37.5404, 127.0700)")
    orig_lat = float(input("출발지 위도: "))
    orig_lon = float(input("출발지 경도: "))

    print("\n도착지 좌표를 입력하세요 (예: 37.5485, 127.0815)")
    dest_lat = float(input("도착지 위도: "))
    dest_lon = float(input("도착지 경도: "))

    result = find_route(G, orig_lat, orig_lon, dest_lat, dest_lon, alpha=ALPHA_DEFAULT)
    
    print()
    print("===== 최단경로 =====")
    print(f"총 거리 : {result['fast']['distance_m']:.0f} m")
    print(f"총 시간 : {result['fast']['time_min']:.1f} 분")

    print()
    print("===== 안전경로 =====")
    print(f"총 거리 : {result['safe']['distance_m']:.0f} m")
    print(f"총 시간 : {result['safe']['time_min']:.1f} 분")

    print()
    print(f"시간 증가율 : {result['time_increase_ratio']*100:.1f}%")
    print(f"추천 경로 : {result['recommended']}")

    route_map = visualize(result["fast"], result["safe"], safety_grid=grid)
    route_map.save(MAP_OUTPUT_PATH)
    print(f"\n지도 저장 완료: {MAP_OUTPUT_PATH} (브라우저로 열어서 확인)")
import os
import numpy as np
import osmnx as ox
import pandas as pd
import folium
from sklearn.neighbors import BallTree
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# 설정값
place = "Gwangjin-gu, Seoul, South Korea"
graph_path = "gwangjin.graphml"

# 최종 safety_score CSV 경로로 변경
grid_path = "data/processed/safety_score_result.csv"

# ===== 최종 CSV 스키마 (safety_score_result.csv 기준) =====
GRID_ID_COL = "grid_id"
ROW_COL = "row"
COL_COL = "col"
LAT_COL = "center_lat"
LON_COL = "center_lng"
GRID_SIZE_COL = "grid_size_m"
GRID_AREA_COL = "grid_area_m2"
CCTV_COUNT_COL = "cctv_count"
STREETLIGHT_COUNT_COL = "streetlight_count"
EMERGENCY_BELL_COUNT_COL = "emergency_bell_count"
POLICE_STATION_COUNT_COL = "police_station_count"
POLICE_SUBSTATION_COUNT_COL = "police_substation_count"
POLICE_BOX_COUNT_COL = "police_box_count"
TOTAL_FACILITY_COUNT_COL = "total_facility_count"
SCORE_COL = "safety_score"
GRADE_COL = "score_grade"
GRADE_COLOR_COL = "grade_color"

# 안전 가중치 튜닝 파라미터
# 전에 패널티가 너무 적었기 때문에 알파값 크게 조정(테스트 후 수정필요)
ALPHA_DEFAULT = 12

# 안전경로 추천 임계값 (최단경로 대비 시간 증가율)
TIME_INCREASE_THRESHOLD = 0.15

# 지도 시각화에 사용할 타일
# "CartoDB positron" : 깔끔하고 UI에 얹기 좋음
MAP_TILES = "CartoDB positron"

# 결과 지도를 저장할 경로 (테스트 및 확인용)
MAP_OUTPUT_PATH = "outputs/route_map.html"

# 지오코딩에 사용할 지역명 접미사 (광진구 내 주소/장소명 정확도를 높이기 위함)
GEOCODE_REGION_HINT = "광진구, 서울"


# 그래프 다운로드 (없으면 다운로드, 있으면 재사용)
# 설정값에 추가
WALK_SPEED_KMH = 4.5  # 성인 평균 도보 속도 (필요시 4~5 사이로 조정)
WALK_SPEED_MPS = WALK_SPEED_KMH * 1000 / 3600


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

    # 도보 속도 기준으로 travel_time 직접 계산 
    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get("length", 0)
        data["travel_time"] = length / WALK_SPEED_MPS

    return G


# safety_score_result.csv 읽기 (최종 스키마)
def load_safety_grid():
    grid = pd.read_csv(grid_path, encoding="utf-8-sig")

    required = [LAT_COL, LON_COL, SCORE_COL]
    missing = [c for c in required if c not in grid.columns]
    if missing:
        raise ValueError(f"{grid_path}에 다음 컬럼이 없습니다: {missing}")

    optional = [
        GRID_ID_COL, ROW_COL, COL_COL, GRID_SIZE_COL,
        CCTV_COUNT_COL, STREETLIGHT_COUNT_COL, EMERGENCY_BELL_COUNT_COL,
        POLICE_STATION_COUNT_COL, POLICE_SUBSTATION_COUNT_COL, POLICE_BOX_COUNT_COL,
        GRADE_COL, GRADE_COLOR_COL,
    ]
    missing_optional = [c for c in optional if c not in grid.columns]
    if missing_optional:
        print(f"참고: 다음 컬럼은 없어서 무시함 : {missing_optional}")

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

# **이 함수는 항상 위도/경도(lat, lon)만 받음
# 주소 -> 좌표 변환(geocode_address)이나 지도 클릭 좌표 추출은 UI/입력 계층에서만(이 함수에 들어오면 안됨)
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

    folium.PolyLine(
        fast_coords,
        color="#1f77ff",
        weight=5,
        opacity=0.85,
        tooltip=f"최단 경로: {fast_route['distance_m']:.0f}m / {fast_route['time_min']:.1f}분",
    ).add_to(m)

    folium.PolyLine(
        safe_coords,
        color="#2ca02c",
        weight=5,
        opacity=0.9,
        dash_array="8,6",
        tooltip=f"안전 경로: {safe_route['distance_m']:.0f}m / {safe_route['time_min']:.1f}분",
    ).add_to(m)

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


# 입력 계층: 주소/장소명(위경도값이 아닌 텍스트) -> 좌표 변환 (find_route()와는 분리)
_geolocator = Nominatim(user_agent="gwangjin_safety_route")


def geocode_address(address: str):
    """주소 또는 장소명을 (위도, 경도)로 변환. 실패 시 None 반환."""
    try:
        location = _geolocator.geocode(f"{address}, {GEOCODE_REGION_HINT}", timeout=5)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"지오코딩 실패: {e}")
        return None

    if location is None:
        print(f"'{address}' 주소/장소를 찾을 수 없습니다.")
        return None

    return location.latitude, location.longitude


def get_coords_from_user(label: str):
    """
    CLI 테스트용 입력 함수.
    '위도,경도' 형태로 입력하면 좌표로 바로 파싱하고
    그 외 문자열은 주소/장소명으로 간주해 지오코딩함
    (Streamlit에서는 이 함수 대신 st_folium 클릭 좌표를 그대로 find_route()에 넘기면 됨)
    """
    raw = input(f"{label} 입력 (예: '37.5404,127.0700' 또는 '건대입구역'): ").strip()

    if "," in raw:
        parts = raw.split(",")
        if len(parts) == 2:
            try:
                lat, lon = float(parts[0].strip()), float(parts[1].strip())
                return lat, lon
            except ValueError:
                pass  # 좌표 파싱 실패 -> 주소로 취급

    result = geocode_address(raw)
    if result is None:
        raise ValueError(f"{label} 좌표를 확인할 수 없습니다. 다시 시도해주세요.")

    lat, lon = result
    print(f"  -> '{raw}' 를 좌표 ({lat:.6f}, {lon:.6f}) 로 변환함")
    return lat, lon


# 실행부
if __name__ == "__main__":
    G = load_graph()
    grid = load_safety_grid()
    G = attach_safety_scores(G, grid)

    print("출발지를 입력하세요 (좌표 또는 주소/장소명 모두 가능)")
    orig_lat, orig_lon = get_coords_from_user("출발지")

    print("\n도착지를 입력하세요 (좌표 또는 주소/장소명 모두 가능)")
    dest_lat, dest_lon = get_coords_from_user("도착지")

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
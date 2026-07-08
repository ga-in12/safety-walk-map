import os
import numpy as np
import osmnx as ox
import pandas as pd
import matplotlib.pyplot as plt
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


## 시각화
# 회색 : 전체 도로
# 파랑 : 최단경로
# 초록 : 안전경로
def visualize(G, fast_route, safe_route):
    fig, ax = ox.plot_graph(
        G,
        node_size=0,
        edge_color="lightgray",
        bgcolor="white",
        show=False,
        close=False,
    )

    ox.plot_graph_route(
        G,
        fast_route,
        ax=ax,
        route_color="blue",
        route_linewidth=4,
        node_size=0,
        show=False,
        close=False,
    )

    ox.plot_graph_route(
        G,
        safe_route,
        ax=ax,
        route_color="green",
        route_linewidth=4,
        node_size=0,
        show=False,
        close=False,
    )

    plt.title("Blue : Shortest Route   Green : Safest Route")
    plt.show()


# 실행부
if __name__ == "__main__":
    G = load_graph()
    grid = load_safety_grid()
    G = attach_safety_scores(G, grid)

    orig_lat, orig_lon = 37.5404, 127.0700
    dest_lat, dest_lon = 37.5485, 127.0815

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

    visualize(G, result["fast"]["nodes"], result["safe"]["nodes"])
import osmnx as ox
import os

# 1. 그래프 다운로드 
place = "Gwangjin-gu, Seoul, South Korea"
graph_path = "gwangjin.graphml"

if os.path.exists(graph_path):
    G = ox.load_graphml(graph_path)
    print("저장된 그래프 불러옴")
else:
    G = ox.graph_from_place(place, network_type="walk")  # 운전이면 "drive"로 수정가능
    ox.save_graphml(G, graph_path)
    print("그래프 새로 다운로드 및 저장")

print(f"노드 수: {len(G.nodes)}, 엣지 수: {len(G.edges)}")

# 2. 속도/소요시간 속성 추가 (travel_time weight 쓰려면 필수)
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)

# 3. 출발지/도착지 좌표 -> 가장 가까운 노드로 변환
# (lat, lon) 예시: 건대입구역 ~ 어린이대공원
orig_lat, orig_lon = 37.5404, 127.0700   # 출발지
dest_lat, dest_lon = 37.5485, 127.0815   # 도착지

orig_node = ox.distance.nearest_nodes(G, X=orig_lon, Y=orig_lat)
dest_node = ox.distance.nearest_nodes(G, X=dest_lon, Y=dest_lat)

print(f"출발 노드: {orig_node}, 도착 노드: {dest_node}")

# 4. 최단경로 탐색 (소요시간 기준)
route = ox.shortest_path(G, orig_node, dest_node, weight="travel_time")

if route is None:
    print("경로를 찾을 수 없습니다. (연결되지 않은 구간일 수 있음)")
else:
    print(f"경로 노드 수: {len(route)}")

    # 5. 경로 정보(거리, 시간) 계산
    edge_lengths = ox.routing.route_to_gdf(G, route)["length"]
    edge_times = ox.routing.route_to_gdf(G, route)["travel_time"]

    total_length_m = edge_lengths.sum()
    total_time_s = edge_times.sum()

    print(f"총 거리: {total_length_m:.0f} m")
    print(f"총 소요시간: {total_time_s/60:.1f} 분")

    # 6. 시각화
    ox.plot_graph_route(G, route, route_color="red", route_linewidth=4, node_size=0)
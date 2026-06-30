import osmnx as ox
import matplotlib.pyplot as plt

print("광진구 보행자 도로망 데이터를 불러오는 중입니다. 잠시만 기다려주세요...")

# 1. 광진구 보행자 도로망(network_type='walk') 데이터 불러오기
place = 'Gwangjin-gu, Seoul, South Korea'
G = ox.graph_from_place(place, network_type='walk')

print("데이터 불러오기 완료! 지도를 화면에 띄웁니다.")
print(f"노드 수: {len(G.nodes)}, 엣지 수: {len(G.edges)}")

# 2. 불러온 도로망 데이터를 화면에 선(Edge)과 점(Node)으로 시각화하기
fig, ax = ox.plot_graph(G)
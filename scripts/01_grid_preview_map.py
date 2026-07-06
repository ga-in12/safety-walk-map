# 광진구 격자점 생성 및 folium 지도 시각화
# -> 안전지수 계산 전에, 격자 간격이 적당한지 눈으로 확인하기 위한 스크립트
# -> 실제 광진구 경계 폴리곤으로 필터링

import folium
import numpy as np
import pandas as pd
from pathlib import Path

# =========================
# 0. 저장 폴더 설정
# =========================
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)

processed_dir = Path("data/processed")
processed_dir.mkdir(parents=True, exist_ok=True)


# =========================
# 1. 광진구 실제 경계 폴리곤
# 좌표 순서: (경도, 위도)
# =========================
gwangjin_polygon = [
    (127.08068541280403, 37.56906425519017), (127.08553261581505, 37.56856310839328),
    (127.09327554832984, 37.566762290300666), (127.1015990771266, 37.57076342290955),
    (127.10304174249214, 37.57076342290955), (127.10627148043552, 37.568124945986824),
    (127.10545359063936, 37.56685230388649), (127.10407152037101, 37.55958871940823),
    (127.10325742736646, 37.5572251707506), (127.11270952006532, 37.55702358575743),
    (127.11519584981606, 37.557533180704915), (127.11600943681239, 37.55580061507081),
    (127.11600200349189, 37.55053147511706), (127.11418412219375, 37.54474592090681),
    (127.1116764203608, 37.540669955324965), (127.10484130265957, 37.53120327509912),
    (127.10087519791962, 37.524841220167055), (127.0943611414465, 37.523984206117525),
    (127.08639455667742, 37.52161824624356), (127.07968915919895, 37.52077294752823),
    (127.07496309841329, 37.52091052765938), (127.0690698130372, 37.522279423505026),
    (127.05867359288398, 37.52629974922568), (127.06896218881212, 37.544361436565524),
    (127.07580697427795, 37.556641581290656), (127.07421053024362, 37.55724769712085),
    (127.08068541280403, 37.56906425519017)
]


# =========================
# 2. 광진구 경계의 위도/경도 범위 구하기
# =========================
lngs = [p[0] for p in gwangjin_polygon]
lats = [p[1] for p in gwangjin_polygon]

lat_min, lat_max = min(lats), max(lats)
lng_min, lng_max = min(lngs), max(lngs)

center_lat = (lat_min + lat_max) / 2
center_lng = (lng_min + lng_max) / 2


# =========================
# 3. 점이 광진구 polygon 내부에 있는지 확인하는 함수
# =========================
def point_in_polygon(lng, lat, poly):
    """
    점이 polygon 내부에 있는지 판별하는 함수
    lng: 경도
    lat: 위도
    poly: [(경도, 위도), ...] 형태의 폴리곤 좌표 리스트
    """
    n = len(poly)
    inside = False
    j = n - 1

    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]

        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside

        j = i

    return inside


# =========================
# 4. 격자 간격 설정
# =========================
grid_interval_m = 500

# 위도 1도는 약 111km
lat_step = grid_interval_m / 111000

# 경도 1도는 위도에 따라 달라짐
lng_step = grid_interval_m / (111000 * np.cos(np.radians(center_lat)))


# =========================
# 5. 격자점 생성
# =========================
lat_points = np.arange(lat_min, lat_max, lat_step)
lng_points = np.arange(lng_min, lng_max, lng_step)

grid_points = []

for lat in lat_points:
    for lng in lng_points:
        if point_in_polygon(lng, lat, gwangjin_polygon):
            grid_points.append((lat, lng))

print(f"격자 간격: {grid_interval_m}m")
print(f"격자점 개수: {len(grid_points)}개")
print(f"위도 방향 후보 개수: {len(lat_points)}")
print(f"경도 방향 후보 개수: {len(lng_points)}")


# =========================
# 6. 격자점 CSV 저장
# =========================
grid_data = pd.DataFrame(grid_points, columns=["위도", "경도"])
grid_data.insert(0, "grid_id", range(len(grid_data)))

grid_csv_path = processed_dir / "gwangjin_grid_points.csv"

grid_data.to_csv(
    grid_csv_path,
    index=False,
    encoding="utf-8-sig"
)

print(f"격자점 CSV 저장 완료: {grid_csv_path}")


# =========================
# 7. folium 지도 생성
# =========================
m = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=14,
    tiles="CartoDB Voyager"
)


# =========================
# 8. 광진구 경계선 표시
# folium은 [위도, 경도] 순서
# =========================
folium.Polygon(
    locations=[[lat, lng] for lng, lat in gwangjin_polygon],
    color="gray",
    weight=3,
    fill=True,
    fill_color="lightblue",
    fill_opacity=0.12,
    tooltip="광진구 경계"
).add_to(m)


# =========================
# 9. 격자점 표시
# =========================
for i in range(len(grid_data)):
    row = grid_data.iloc[i]

    folium.CircleMarker(
        location=[row["위도"], row["경도"]],
        radius=3,
        color="crimson",
        fill=True,
        fill_color="crimson",
        fill_opacity=0.8,
        tooltip=f"grid_id: {row['grid_id']}"
    ).add_to(m)


# =========================
# 10. 예시로 가운데 격자점에 500m 반경 표시
# =========================
sample_index = len(grid_data) // 2
sample_row = grid_data.iloc[sample_index]

folium.Circle(
    location=[sample_row["위도"], sample_row["경도"]],
    radius=500,
    color="red",
    weight=2,
    fill=False,
    tooltip="500m 계산 반경 예시"
).add_to(m)


# =========================
# 11. 지도 저장
# =========================
output_path = output_dir / "gwangjin_grid_preview.html"

m.save(output_path)

print(f"지도 저장 완료: {output_path}")
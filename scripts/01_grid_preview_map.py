# 광진구 격자점 생성 + folium 지도 시각화 + 안전시설물 표시
# -> 안전지수 계산 전에, 광진구 지도 위에서 격자 간격과 시설 분포를 확인하기 위한 스크립트

import folium
import numpy as np
import pandas as pd
from pathlib import Path


# =========================
# 0. 경로 설정
# =========================

# 안전시설 통합 데이터 경로
input_path = Path("data/raw/광진구_안전시설_통합.csv")

# 결과 저장 폴더
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)

# 처리 데이터 저장 폴더
processed_dir = Path("data/processed")
processed_dir.mkdir(parents=True, exist_ok=True)


# =========================
# 1. 안전시설 데이터 불러오기
# =========================

facilities_data = pd.read_csv(input_path, encoding="utf-8-sig")

print("시설 데이터 확인")
print(facilities_data.head())
print("시설 데이터 개수:", len(facilities_data))
print("시설유형 목록:", facilities_data["시설유형"].unique())


# =========================
# 2. 광진구 실제 경계 폴리곤
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
# 3. 광진구 경계 범위 구하기
# =========================

lngs = [p[0] for p in gwangjin_polygon]
lats = [p[1] for p in gwangjin_polygon]

lat_min, lat_max = min(lats), max(lats)
lng_min, lng_max = min(lngs), max(lngs)

# 지도 중심 좌표
center_lat = (lat_min + lat_max) / 2
center_lng = (lng_min + lng_max) / 2


# =========================
# 4. 점이 광진구 내부에 있는지 확인하는 함수
# =========================

def point_in_polygon(lng, lat, poly):
    """
    점이 폴리곤 내부에 있는지 확인하는 함수

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

        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside

        j = i

    return inside


# =========================
# 5. 격자 간격 설정
# =========================

# 격자점 사이 간격
# 500이면 500m마다 점 생성
# 250이면 250m마다 점 생성
grid_interval_m = 500

# 위도 1도는 약 111km
lat_step = grid_interval_m / 111000

# 경도 1도는 위도에 따라 달라짐
lng_step = grid_interval_m / (111000 * np.cos(np.radians(center_lat)))


# =========================
# 6. 광진구 내부 격자점 생성
# =========================

lat_points = np.arange(lat_min, lat_max, lat_step)
lng_points = np.arange(lng_min, lng_max, lng_step)

grid_points = []

for lat in lat_points:
    for lng in lng_points:

        # 광진구 폴리곤 내부에 있는 점만 저장
        if point_in_polygon(lng, lat, gwangjin_polygon):
            grid_points.append((lat, lng))

print(f"격자 간격: {grid_interval_m}m")
print(f"격자점 개수: {len(grid_points)}개")
print(f"위도 방향 후보 개수: {len(lat_points)}")
print(f"경도 방향 후보 개수: {len(lng_points)}")


# =========================
# 7. 격자점 CSV 저장
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
# 8. 시설유형별 지도 표시 스타일 설정
# =========================

facility_color_dict = {
    "CCTV": "blue",
    "가로등": "orange",
    "비상벨": "red",
    "경찰서": "purple"
}

# 혹시 예상하지 못한 시설유형이 있으면 회색으로 표시
default_facility_color = "gray"


# =========================
# 9. folium 지도 생성
# =========================

m = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=14,
    tiles="CartoDB Voyager"
)


# =========================
# 10. 광진구 경계선 표시
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
# 11. 격자점 레이어 만들기
# =========================

grid_layer = folium.FeatureGroup(name="격자점")

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
    ).add_to(grid_layer)

grid_layer.add_to(m)


# =========================
# 12. 시설물 레이어 만들기
# 시설유형별로 따로 레이어를 만들어서 지도에서 켜고 끌 수 있게 함
# =========================

for facility_type in facilities_data["시설유형"].unique():

    # 특정 시설유형만 선택
    one_type_data = facilities_data[
        facilities_data["시설유형"] == facility_type
    ]

    # 시설유형별 레이어
    facility_layer = folium.FeatureGroup(name=f"{facility_type}")

    # 색상 설정
    marker_color = facility_color_dict.get(facility_type, default_facility_color)

    for i in range(len(one_type_data)):
        row = one_type_data.iloc[i]

        # 위도/경도 결측치가 있으면 건너뛰기
        if pd.isna(row["위도"]) or pd.isna(row["경도"]):
            continue

        # 팝업 내용 만들기
        popup_text = f"""
        <b>시설유형:</b> {row['시설유형']}<br>
        <b>시설명:</b> {row.get('시설명', '')}<br>
        <b>주소:</b> {row.get('주소', '')}<br>
        <b>위도:</b> {row['위도']}<br>
        <b>경도:</b> {row['경도']}
        """

        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=4,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=facility_type
        ).add_to(facility_layer)

    facility_layer.add_to(m)


# =========================
# 13. 예시로 가운데 격자점에 500m 반경 표시
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
# 14. 범례 추가
# =========================

legend_html = """
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 170px;
    background-color: white;
    border: 2px solid gray;
    z-index: 9999;
    font-size: 14px;
    padding: 10px;
">
<b>지도 범례</b><br>
<span style="color:crimson;">●</span> 격자점<br>
<span style="color:blue;">●</span> CCTV<br>
<span style="color:orange;">●</span> 가로등<br>
<span style="color:red;">●</span> 비상벨<br>
<span style="color:purple;">●</span> 경찰서<br>
<span style="color:gray;">━</span> 광진구 경계<br>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))


# =========================
# 15. 레이어 컨트롤 추가
# =========================

folium.LayerControl().add_to(m)


# =========================
# 16. 지도 저장
# =========================

output_path = output_dir / "gwangjin_grid_facilities_preview.html"

m.save(output_path)

print(f"시설물 포함 지도 저장 완료: {output_path}")
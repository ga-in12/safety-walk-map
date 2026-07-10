# 광진구 격자별 안전점수 계산 + Folium 히트맵 생성
# 기존 단일점 안전지수 계산 코드를 "격자점 여러 개"에 반복 적용하는 버전

import folium
import numpy as np
import pandas as pd
from pathlib import Path
from haversine import haversine


# =========================================================
# 0. 경로 설정
# =========================================================

# 안전시설 통합 데이터
input_path = Path("data/raw/광진구_안전시설_통합.csv")

# 이전 단계에서 만든 광진구 격자점 데이터
grid_input_path = Path("data/processed/gwangjin_grid_points.csv")

# 처리 결과 저장 폴더
processed_dir = Path("data/processed")
processed_dir.mkdir(parents=True, exist_ok=True)

# 지도 결과 저장 폴더
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)


# =========================================================
# 1. 데이터 불러오기
# =========================================================

facilities_data = pd.read_csv(input_path, encoding="utf-8-sig")
grid_data = pd.read_csv(grid_input_path, encoding="utf-8-sig")

print("시설 데이터 개수:", len(facilities_data))
print("격자점 개수:", len(grid_data))
print("격자점 데이터 확인")
print(grid_data.head())


# =========================================================
# 2. 광진구 실제 경계 폴리곤
# 좌표 순서: (경도, 위도)
# 지도에 경계 표시용으로 사용
# =========================================================

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


# =========================================================
# 3. 지도 중심 좌표 계산
# =========================================================

lngs = [p[0] for p in gwangjin_polygon]
lats = [p[1] for p in gwangjin_polygon]

center_lat = (min(lats) + max(lats)) / 2
center_lng = (min(lngs) + max(lngs)) / 2


# =========================================================
# 4. 안전지수 계산 설정
# =========================================================

# 반경 500m 안의 시설을 세기
radius_km = 0.5

# 시설유형별 가중치
# 총합 100점
safety_weight_dict = {
    "CCTV": 35,
    "가로등": 30,
    "비상벨": 20,
    "경찰서": 15
}

# 시설유형별 만점 기준 개수
# 예: CCTV가 50개 이상이면 CCTV 점수는 35점 만점
max_count_dict = {
    "CCTV": 50,
    "가로등": 100,
    "비상벨": 20,
    "경찰서": 2
}


# =========================================================
# 5. 거리 계산 함수
# =========================================================

def haversine_distance(lat1, lng1, lat2, lng2):
    """
    위도/경도를 이용해서 두 지점 사이의 거리(km)를 계산하는 함수
    """
    return haversine((lat1, lng1), (lat2, lng2), unit="km")


def add_km_columns(target_lat, target_lng, facilities_data):
    """
    하나의 격자점을 기준으로 모든 시설과의 거리(km)를 계산해서
    km 컬럼을 추가한 데이터프레임을 반환하는 함수
    """
    facilities_data = facilities_data.copy()

    if "km" in facilities_data.columns:
        facilities_data = facilities_data.drop("km", axis=1)

    km_list = []

    for i in range(len(facilities_data)):
        facility_lat = facilities_data.iloc[i]["위도"]
        facility_lng = facilities_data.iloc[i]["경도"]

        distance = haversine_distance(
            target_lat,
            target_lng,
            facility_lat,
            facility_lng
        )

        km_list.append(distance)

    facilities_data["km"] = km_list

    return facilities_data


# =========================================================
# 6. 안전점수 계산 함수
# =========================================================

def calculate_safety_score(facility_counts, safety_weight_dict, max_count_dict):
    """
    시설유형별 개수를 이용해서 안전점수를 계산하는 함수

    facility_counts 예시:
    CCTV      50
    가로등     80
    비상벨     12
    경찰서      1
    """

    safety_score = 0

    # 기존 코드보다 안정적인 방식
    # facility_counts에 없는 시설은 0개로 계산
    for facility in safety_weight_dict.keys():

        num = facility_counts.get(facility, 0)
        weight = safety_weight_dict[facility]
        max_num = max_count_dict[facility]

        ratio = num / max_num

        # 만점 기준 이상이면 1로 고정
        if ratio >= 1:
            ratio = 1

        safety_score = safety_score + ratio * weight

    return safety_score


def convert_score_to_grade(safety_score):
    """
    안전점수를 A~E 등급으로 변환하는 함수
    """
    if safety_score >= 85:
        return "A"
    elif safety_score >= 70:
        return "B"
    elif safety_score >= 55:
        return "C"
    elif safety_score >= 40:
        return "D"
    else:
        return "E"


# =========================================================
# 7. 모든 격자점에 대해 안전점수 계산
# =========================================================

result_list = []

for i in range(len(grid_data)):

    # 현재 격자점 정보 가져오기
    grid_id = grid_data.iloc[i]["grid_id"]
    target_lat = grid_data.iloc[i]["위도"]
    target_lng = grid_data.iloc[i]["경도"]

    # 현재 격자점을 기준으로 모든 시설과의 거리 계산
    facilities_km_data = add_km_columns(
        target_lat,
        target_lng,
        facilities_data
    )

    # 500m 이내 시설만 선택
    under_radius_data = facilities_km_data[
        facilities_km_data["km"] <= radius_km
    ]

    # 500m 이내 시설유형별 개수 세기
    facility_counts = under_radius_data["시설유형"].value_counts()

    # 안전점수 계산
    safety_score = calculate_safety_score(
        facility_counts,
        safety_weight_dict,
        max_count_dict
    )

    # 안전등급 계산
    safety_grade = convert_score_to_grade(safety_score)

    # 결과 한 줄 저장
    result_list.append({
        "grid_id": grid_id,
        "위도": target_lat,
        "경도": target_lng,
        "반경_km": radius_km,
        "CCTV개수": facility_counts.get("CCTV", 0),
        "가로등개수": facility_counts.get("가로등", 0),
        "비상벨개수": facility_counts.get("비상벨", 0),
        "경찰서개수": facility_counts.get("경찰서", 0),
        "전체시설개수": len(under_radius_data),
        "안전점수": safety_score,
        "안전등급": safety_grade
    })

    # 진행상황 출력
    print(f"{i + 1}/{len(grid_data)} 계산 완료 - grid_id: {grid_id}, 점수: {safety_score:.1f}, 등급: {safety_grade}")


# 리스트를 데이터프레임으로 변환
safety_grid_data = pd.DataFrame(result_list)

print("격자별 안전점수 결과 확인")
print(safety_grid_data.head())


# =========================================================
# 8. safety_grid.csv 저장
# =========================================================

safety_grid_output_path = processed_dir / "safety_grid.csv"

safety_grid_data.to_csv(
    safety_grid_output_path,
    index=False,
    encoding="utf-8-sig"
)

print("격자별 안전점수 CSV 저장 완료:", safety_grid_output_path)


# =========================================================
# 9. Folium 히트맵 지도 만들기
# =========================================================

# 등급별 색깔
grade_color_dict = {
    "A": "green",
    "B": "yellowgreen",
    "C": "yellow",
    "D": "orange",
    "E": "red"
}

# 시설유형별 색깔
facility_color_dict = {
    "CCTV": "blue",
    "가로등": "orange",
    "비상벨": "red",
    "경찰서": "purple"
}

# 지도 생성
m = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=14,
    tiles="CartoDB Voyager"
)


# =========================================================
# 10. 광진구 경계선 표시
# =========================================================

folium.Polygon(
    locations=[[lat, lng] for lng, lat in gwangjin_polygon],
    color="gray",
    weight=3,
    fill=True,
    fill_color="lightblue",
    fill_opacity=0.08,
    tooltip="광진구 경계"
).add_to(m)


# =========================================================
# 11. 격자 히트맵 레이어 표시
# =========================================================

# 격자 한 칸 크기
# 이전에 격자 간격을 500m로 만들었기 때문에, 시각화도 500m x 500m 정도로 표현
cell_size_km = 0.5

# 위도/경도 1도의 km 거리
km_per_lat_degree = haversine(
    (center_lat, center_lng),
    (center_lat + 1, center_lng),
    unit="km"
)

km_per_lng_degree = haversine(
    (center_lat, center_lng),
    (center_lat, center_lng + 1),
    unit="km"
)

# 사각형 반 칸 크기
half_cell_lat = (cell_size_km / 2) / km_per_lat_degree
half_cell_lng = (cell_size_km / 2) / km_per_lng_degree


heatmap_layer = folium.FeatureGroup(name="안전등급 히트맵")

for i in range(len(safety_grid_data)):

    row = safety_grid_data.iloc[i]

    lat = row["위도"]
    lng = row["경도"]
    grade = row["안전등급"]
    score = row["안전점수"]

    color = grade_color_dict.get(grade, "gray")

    # 사각형 꼭짓점 좌표
    # folium.Rectangle은 [[남서쪽], [북동쪽]] 좌표 사용
    bounds = [
        [lat - half_cell_lat, lng - half_cell_lng],
        [lat + half_cell_lat, lng + half_cell_lng]
    ]

    tooltip_text = f"""
    grid_id: {row['grid_id']}<br>
    안전점수: {score:.1f}<br>
    안전등급: {grade}<br>
    CCTV: {row['CCTV개수']}개<br>
    가로등: {row['가로등개수']}개<br>
    비상벨: {row['비상벨개수']}개<br>
    경찰서: {row['경찰서개수']}개<br>
    전체시설: {row['전체시설개수']}개
    """

    folium.Rectangle(
        bounds=bounds,
        color=color,
        weight=1,
        fill=True,
        fill_color=color,
        fill_opacity=0.45,
        tooltip=tooltip_text
    ).add_to(heatmap_layer)

heatmap_layer.add_to(m)


# =========================================================
# 12. 격자점 표시 레이어
# =========================================================

grid_layer = folium.FeatureGroup(name="격자점")

for i in range(len(safety_grid_data)):

    row = safety_grid_data.iloc[i]

    folium.CircleMarker(
        location=[row["위도"], row["경도"]],
        radius=2,
        color="black",
        fill=True,
        fill_color="black",
        fill_opacity=0.8,
        tooltip=f"grid_id: {row['grid_id']}"
    ).add_to(grid_layer)

grid_layer.add_to(m)


# =========================================================
# 13. 시설물 표시 레이어
# =========================================================

for facility_type in facilities_data["시설유형"].unique():

    one_type_data = facilities_data[
        facilities_data["시설유형"] == facility_type
    ]

    facility_layer = folium.FeatureGroup(name=f"{facility_type}")

    marker_color = facility_color_dict.get(facility_type, "gray")

    for i in range(len(one_type_data)):

        row = one_type_data.iloc[i]

        if pd.isna(row["위도"]) or pd.isna(row["경도"]):
            continue

        popup_text = f"""
        <b>시설유형:</b> {row['시설유형']}<br>
        <b>시설명:</b> {row.get('시설명', '')}<br>
        <b>주소:</b> {row.get('주소', '')}<br>
        <b>위도:</b> {row['위도']}<br>
        <b>경도:</b> {row['경도']}
        """

        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=3,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=facility_type
        ).add_to(facility_layer)

    facility_layer.add_to(m)


# =========================================================
# 14. 예시 500m 계산 반경 원 표시
# =========================================================

sample_index = len(safety_grid_data) // 2
sample_row = safety_grid_data.iloc[sample_index]

folium.Circle(
    location=[sample_row["위도"], sample_row["경도"]],
    radius=500,
    color="black",
    weight=2,
    fill=False,
    tooltip="500m 계산 반경 예시"
).add_to(m)


# =========================================================
# 15. 범례 추가
# =========================================================

legend_html = """
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 190px;
    background-color: white;
    border: 2px solid gray;
    z-index: 9999;
    font-size: 14px;
    padding: 10px;
">
<b>안전등급 범례</b><br>
<span style="color:green;">■</span> A 등급<br>
<span style="color:yellowgreen;">■</span> B 등급<br>
<span style="color:yellow;">■</span> C 등급<br>
<span style="color:orange;">■</span> D 등급<br>
<span style="color:red;">■</span> E 등급<br>
<hr>
<span style="color:black;">●</span> 격자점<br>
<span style="color:blue;">●</span> CCTV<br>
<span style="color:orange;">●</span> 가로등<br>
<span style="color:red;">●</span> 비상벨<br>
<span style="color:purple;">●</span> 경찰서<br>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))


# =========================================================
# 16. 레이어 컨트롤 추가
# =========================================================

folium.LayerControl().add_to(m)


# =========================================================
# 17. 지도 저장
# =========================================================

heatmap_output_path = output_dir / "gwangjin_safety_heatmap.html"

m.save(heatmap_output_path)

print("격자별 안전 히트맵 저장 완료:", heatmap_output_path)
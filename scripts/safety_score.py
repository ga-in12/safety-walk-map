"""
광진구 500m 격자별 안전점수 계산 및 Folium 지도 생성

추가된 기능
- 격자에 마우스 커서를 올리면 안전점수와 시설 유형별 개수가 툴팁으로 표시됨
- 격자를 클릭해도 같은 정보를 팝업으로 확인할 수 있음
- CCTV·가로등·비상벨은 시설 영향값의 90백분위수를 만점 기준으로 자동 계산
- 경찰서·파출소·지구대는 시설 1개의 완전한 영향값 1.0을 만점 기준으로 설정
- 전체 격자를 20%씩 나누어 A~E 5등급으로 분류
- 결과 CSV, 지도 HTML, 격자 GeoJSON, 시설물 GeoJSON 저장
"""

from pathlib import Path
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Geod
from shapely.geometry import box, mapping


# =========================================================
# 1. 경로 설정
# =========================================================

facility_path = Path(
    "data/raw/광진구_주변지역_안전시설_통합.csv"
)

boundary_dir = Path(
    "data/raw/boundary/lgldong"
)

shp_file = (
    boundary_dir
    / "admstr_zone_lgldong_bndry_24.shp"
)

processed_dir = Path("data/processed")
output_dir = Path("outputs")

processed_dir.mkdir(parents=True, exist_ok=True)
output_dir.mkdir(parents=True, exist_ok=True)


# =========================================================
# 2. 기본 설정값
# =========================================================

# 격자 한 칸의 가로·세로 길이
cell_size_m = 500

# 격자 밖 인접 시설을 반영할 최대 거리(가리감쇠)
# 격자 경계에서 50m 이상 떨어진 시설은 해당 격자 점수에 반영하지 않음
adjacent_buffer_m = 50

# 광진구 중심 좌표
center_lat = 37.5384
center_lng = 127.0822


# 시설별 안전점수 가중치: 합계 100
safety_weight_dict = {
    "CCTV": 30,
    "가로등": 40,
    "비상벨": 5,
    "경찰서": 3,
    "파출소": 12,
    "지구대": 10,
}


# 시설별 만점 기준을 정할 백분위수
# 90백분위수 = 해당 시설 영향값이 상위 10%에 들어가는 지점
# 즉, 시설별로 "상위 10% 수준"에 도달하면 해당 시설 점수를 만점 처리함
saturation_percentile = 90

# 여러 개 설치되는 밀집형 시설
dense_facility_types = {
    "CCTV",
    "가로등",
    "비상벨",
}

# 지역별로 드물게 존재하는 희소형 시설
sparse_facility_types = {
    "경찰서",
    "파출소",
    "지구대",
}

# 전체 격자의 시설별 영향값을 계산한 뒤 자동으로 채워짐
max_count_dict = {}

# 안전등급별 색상
grade_color_dict = {
    "A": "green",
    "B": "yellowgreen",
    "C": "yellow",
    "D": "orange",
    "E": "red",
}

# 시설물 마커 색상
facility_color_dict = {
    "CCTV": "green",
    "가로등": "orange",
    "비상벨": "red",
    "경찰서": "navy",
    "파출소": "blue",
    "지구대": "deepskyblue",
}

# 전체 격자 점수를 계산한 뒤 채워지는 상대평가 기준값
grade_cutoffs = {}


# =========================================================
# 3. 법정동 경계 불러오기
# =========================================================

if not shp_file.exists():
    raise FileNotFoundError(
        f"법정동 경계 SHP 파일을 찾을 수 없습니다: {shp_file}"
    )

all_boundary_gdf = gpd.read_file(
    shp_file,
    encoding="cp949",
)

if all_boundary_gdf.crs is None:
    raise ValueError("법정동 경계 파일에 좌표계 정보가 없습니다.")

if "COL_ADM_SE" not in all_boundary_gdf.columns:
    raise KeyError(
        "경계 파일에 'COL_ADM_SE' 컬럼이 없습니다. "
        "실제 시군구 코드 컬럼명을 확인하세요."
    )

# 광진구 시군구 코드: 11215
adm_code = (
    all_boundary_gdf["COL_ADM_SE"]
    .astype(str)
    .str.replace(".0", "", regex=False)
    .str.zfill(5)
)

gwangjin_dong_boundary_gdf = all_boundary_gdf[
    adm_code == "11215"
].copy()

if gwangjin_dong_boundary_gdf.empty:
    raise ValueError(
        "COL_ADM_SE가 11215인 광진구 경계를 찾지 못했습니다."
    )

# 광진구에 속한 여러 동을 하나의 Polygon 또는 MultiPolygon으로 합침
gwangjin_polygon = gwangjin_dong_boundary_gdf.union_all()

# 원래 경계 좌표계의 광진구 전체 GeoDataFrame
gwangjin_boundary_original_gdf = gpd.GeoDataFrame(
    {"name": ["광진구"]},
    geometry=[gwangjin_polygon],
    crs=gwangjin_dong_boundary_gdf.crs,
)

# Folium 표시용 위도·경도 좌표계
gwangjin_boundary_4326_gdf = (
    gwangjin_boundary_original_gdf
    .to_crs(epsg=4326)
)

gwangjin_polygon_4326 = (
    gwangjin_boundary_4326_gdf.geometry.iloc[0]
)

print("[광진구 경계 불러오기 완료]")
print("원본 좌표계:", gwangjin_boundary_original_gdf.crs)
print("Folium 좌표계:", gwangjin_boundary_4326_gdf.crs)


# =========================================================
# 4. 시설물 데이터 불러오기 및 정리
# =========================================================

if not facility_path.exists():
    raise FileNotFoundError(
        f"시설물 CSV 파일을 찾을 수 없습니다: {facility_path}"
    )

facility_data = pd.read_csv(
    facility_path,
    encoding="utf-8-sig",
)

required_facility_columns = {
    "시설유형",
    "위도",
    "경도",
}

missing_columns = (
    required_facility_columns
    - set(facility_data.columns)
)

if missing_columns:
    raise KeyError(
        f"시설물 CSV에 필요한 컬럼이 없습니다: {sorted(missing_columns)}"
    )

# 위도·경도를 숫자로 변환하고 좌표가 없는 행은 제외
facility_data["위도"] = pd.to_numeric(
    facility_data["위도"],
    errors="coerce",
)
facility_data["경도"] = pd.to_numeric(
    facility_data["경도"],
    errors="coerce",
)
facility_data["시설유형"] = (
    facility_data["시설유형"]
    .astype(str)
    .str.strip()
)

before_drop_count = len(facility_data)
facility_data = facility_data.dropna(
    subset=["위도", "경도"]
).copy()

print("[시설물 데이터 불러오기 완료]")
print("전체 행 수:", before_drop_count)
print("유효 좌표 행 수:", len(facility_data))
print("시설유형:", facility_data["시설유형"].unique())

known_facility_types = set(safety_weight_dict)
unknown_facility_types = sorted(
    set(facility_data["시설유형"].unique())
    - known_facility_types
)

if unknown_facility_types:
    print(
        "[주의] 점수 계산에서 제외되는 미등록 시설유형:",
        unknown_facility_types,
    )

# 시설 위치를 Point geometry로 변환
facility_gdf_4326 = gpd.GeoDataFrame(
    facility_data.copy(),
    geometry=gpd.points_from_xy(
        facility_data["경도"],
        facility_data["위도"],
    ),
    crs="EPSG:4326",
)

# 격자와 시설 사이 거리를 m 단위로 계산하기 위해 EPSG:5186으로 변환
facility_gdf_5186 = facility_gdf_4326.to_crs(
    epsg=5186
)


# =========================================================
# 5. 500m를 위도·경도 변화량으로 변환
# =========================================================

geod = Geod(ellps="WGS84")

# 광진구 중심에서 북쪽으로 1m 이동한 좌표
north_lng, north_lat, _ = geod.fwd(
    center_lng,
    center_lat,
    0,
    1,
)

# 광진구 중심에서 동쪽으로 1m 이동한 좌표
east_lng, east_lat, _ = geod.fwd(
    center_lng,
    center_lat,
    90,
    1,
)

lat_per_1m = north_lat - center_lat
lng_per_1m = east_lng - center_lng

cell_size_lat = cell_size_m * lat_per_1m
cell_size_lng = cell_size_m * lng_per_1m


# =========================================================
# 6. 격자점 생성
# =========================================================

# total_bounds 순서:
# min_lng, min_lat, max_lng, max_lat
min_lng, min_lat, max_lng, max_lat = (
    gwangjin_boundary_4326_gdf.total_bounds
)

lat_list = np.arange(
    min_lat,
    max_lat + cell_size_lat,
    cell_size_lat,
)

lng_list = np.arange(
    min_lng,
    max_lng + cell_size_lng,
    cell_size_lng,
)

# (중심 위도, 중심 경도, 행 번호, 열 번호)
point_list = []

for row_index, lat in enumerate(lat_list):
    for col_index, lng in enumerate(lng_list):
        point_list.append(
            (lat, lng, row_index, col_index)
        )

print("[전체 후보 격자점 개수]", len(point_list))


# =========================================================
# 7. 계산 함수
# =========================================================

def make_cell_polygon(point_lat, point_lng):
    """격자 중심점을 기준으로 500m × 500m 사각형 Polygon을 만든다."""

    cell_min_lat = point_lat - cell_size_lat / 2
    cell_max_lat = point_lat + cell_size_lat / 2
    cell_min_lng = point_lng - cell_size_lng / 2
    cell_max_lng = point_lng + cell_size_lng / 2

    return box(
        cell_min_lng,
        cell_min_lat,
        cell_max_lng,
        cell_max_lat,
    )


def counting_facility(cell_polygon, facility_df):
    """한 격자 안에 들어 있는 시설을 유형별로 센다."""

    facility_count_dict = {
        "CCTV": 0,
        "가로등": 0,
        "비상벨": 0,
        "경찰서": 0,
        "파출소": 0,
        "지구대": 0,
    }

    cell_min_lng, cell_min_lat, cell_max_lng, cell_max_lat = (
        cell_polygon.bounds
    )

    # 현재 격자 범위 안에 있는 행만 한 번에 선택
    inside_mask = (
        facility_df["위도"].between(
            cell_min_lat,
            cell_max_lat,
            inclusive="both",
        )
        & facility_df["경도"].between(
            cell_min_lng,
            cell_max_lng,
            inclusive="both",
        )
    )

    facility_counts = (
        facility_df.loc[inside_mask, "시설유형"]
        .value_counts()
    )

    for facility_type in facility_count_dict:
        facility_count_dict[facility_type] = int(
            facility_counts.get(facility_type, 0)
        )

    return facility_count_dict


def calculate_distance_weight(distance_m):
    """격자 경계에서 가까울수록 높은 영향값을 반환한다."""

    return max(
        0.0,
        1 - distance_m / adjacent_buffer_m,
    )


def calculate_facility_influence(
    cell_polygon,
    facility_gdf,
):
    """
    안전점수 계산용 시설 영향값을 구한다.

    격자 내부 시설은 1.0으로 반영하고,
    격자 밖 50m 이내 시설은 격자 경계와 가까울수록 크게 반영한다.
    """

    facility_influence_dict = {
        "CCTV": 0.0,
        "가로등": 0.0,
        "비상벨": 0.0,
        "경찰서": 0.0,
        "파출소": 0.0,
        "지구대": 0.0,
    }

    # 위도·경도 격자를 거리 계산이 가능한 미터 좌표계로 변환
    cell_polygon_5186 = gpd.GeoSeries(
        [cell_polygon],
        crs="EPSG:4326",
    ).to_crs(
        epsg=5186
    ).iloc[0]

    # 격자 경계 바깥 50m까지 확장
    expanded_cell_5186 = cell_polygon_5186.buffer(
        adjacent_buffer_m
    )

    # 원래 격자 또는 확장 영역 안에 있는 시설만 선택
    nearby_facility_gdf = facility_gdf[
        facility_gdf.geometry.intersects(
            expanded_cell_5186
        )
    ]

    for _, facility in nearby_facility_gdf.iterrows():
        facility_type = facility["시설유형"]

        if facility_type not in facility_influence_dict:
            continue

        facility_point = facility.geometry

        # 원래 격자 내부 시설은 100% 반영
        if cell_polygon_5186.covers(facility_point):
            influence = 1.0

        # 격자 밖 시설은 경계와의 거리에 따라 0~1 사이로 반영
        else:
            distance_m = cell_polygon_5186.distance(
                facility_point
            )

            influence = calculate_distance_weight(
                distance_m
            )

        facility_influence_dict[
            facility_type
        ] += influence

    return facility_influence_dict


def calculate_safety_score_cell(facility_influence_dict):
    """시설별 거리감쇠 영향값과 가중치로 안전점수를 계산한다."""

    safety_score = 0.0

    for facility_type, weight in safety_weight_dict.items():
        influence = facility_influence_dict[facility_type]
        max_count = max_count_dict[facility_type]

        ratio = min(influence / max_count, 1)
        safety_score += weight * ratio

    return float(safety_score)


def define_grade(safety_score):
    """전체 격자 점수의 상대적 위치에 따라 A~E 등급을 반환한다."""

    if safety_score >= grade_cutoffs["A"]:
        return "A"
    if safety_score >= grade_cutoffs["B"]:
        return "B"
    if safety_score >= grade_cutoffs["C"]:
        return "C"
    if safety_score >= grade_cutoffs["D"]:
        return "D"
    return "E"


# =========================================================
# 8. 모든 격자의 안전점수 계산
# =========================================================

result_columns = [
    "grid_id",
    "row",
    "col",
    "center_lat",
    "center_lng",
    "grid_size_m",
    "grid_area_m2",
    "cctv_count",
    "streetlight_count",
    "emergency_bell_count",
    "police_station_count",
    "police_substation_count",
    "police_box_count",
    "total_facility_count",
    "safety_score",
    "score_grade",
    "grade_color",
]

# 1차 계산 결과를 임시로 저장함
# 이 단계에서는 시설별 영향값만 계산하고 안전점수는 아직 계산하지 않음
raw_grid_rows = []
total_point_count = len(point_list)

for point_number, (
    point_lat,
    point_lng,
    row_index,
    col_index,
) in enumerate(point_list, start=1):

    print(
        f"\r격자 계산 중(1차: 시설 영향값): "
        f"{point_number}/{total_point_count} "
        f"({point_number / total_point_count * 100:.1f}%)",
        end="",
        flush=True,
    )

    cell_polygon = make_cell_polygon(
        point_lat,
        point_lng,
    )

    # 광진구 경계와 전혀 겹치지 않는 격자는 제외
    if not cell_polygon.intersects(
        gwangjin_polygon_4326
    ):
        continue

    # CSV와 지도에는 실제 격자 내부 시설 개수를 저장
    facility_count_dict = counting_facility(
        cell_polygon,
        facility_data,
    )

    # 안전점수 계산에는 격자 밖 50m 이내 시설의 거리감쇠 영향도 반영
    facility_influence_dict = calculate_facility_influence(
        cell_polygon,
        facility_gdf_5186,
    )

    raw_grid_rows.append(
        {
            "grid_id": point_number,
            "row": row_index,
            "col": col_index,
            "center_lat": point_lat,
            "center_lng": point_lng,
            "grid_size_m": cell_size_m,
            "grid_area_m2": cell_size_m**2,
            "cctv_count": facility_count_dict["CCTV"],
            "streetlight_count": facility_count_dict["가로등"],
            "emergency_bell_count": facility_count_dict["비상벨"],
            "police_station_count": facility_count_dict["경찰서"],
            "police_substation_count": facility_count_dict["지구대"],
            "police_box_count": facility_count_dict["파출소"],
            "total_facility_count": sum(
                facility_count_dict.values()
            ),
            # 최종 CSV에는 넣지 않을 내부 계산용 값
            "_facility_influence": facility_influence_dict,
        }
    )

print("\n1차 pass 완료")

if not raw_grid_rows:
    raise RuntimeError(
        "광진구 경계와 겹치는 격자가 하나도 생성되지 않았습니다."
    )


# ---------------------------------------------------------
# 시설별 만점 기준 자동 계산
# ---------------------------------------------------------
# 밀집형 시설:
# 전체 격자 영향값 분포의 90백분위수를 만점 기준으로 사용
#
# 희소형 시설:
# 시설 한 개가 격자 내부에 완전히 포함된 영향값인 1.0을
# 만점 기준으로 사용

for facility_type in safety_weight_dict:

    # CCTV, 가로등, 비상벨과 같은 밀집형 시설
    if facility_type in dense_facility_types:

        influence_values = [
            row["_facility_influence"][facility_type]
            for row in raw_grid_rows
        ]

        percentile_value = float(
            np.percentile(
                influence_values,
                saturation_percentile,
            )
        )

        # 해당 시설이 대부분 격자에 없어서
        # 90백분위수가 0이 되는 경우 처리
        if percentile_value <= 0:

            positive_values = [
                value
                for value in influence_values
                if value > 0
            ]

            # 시설 영향값이 하나라도 있으면
            # 가장 작은 양수값을 임시 만점 기준으로 사용
            if positive_values:
                percentile_value = float(
                    min(positive_values)
                )

            # 데이터 전체에 해당 시설이 전혀 없으면
            # 0으로 나누는 것을 막기 위해 1.0 사용
            else:
                percentile_value = 1.0

        max_count_dict[facility_type] = (
            percentile_value
        )

    # 경찰서, 파출소, 지구대와 같은 희소형 시설
    elif facility_type in sparse_facility_types:

        # 시설 한 개가 격자 내부에 존재하는 경우
        # 영향값이 1.0이므로 이를 만점 기준으로 설정
        max_count_dict[facility_type] = 1.0

    # 혹시 시설 분류 목록에 빠진 유형이 있으면 오류 발생
    else:
        raise ValueError(
            f"시설 분류가 지정되지 않았습니다: "
            f"{facility_type}"
        )


print("[시설별 만점 기준]")

for facility_type, max_count in (
    max_count_dict.items()
):
    if facility_type in dense_facility_types:
        calculation_method = (
            f"{saturation_percentile}백분위수"
        )
    else:
        calculation_method = (
            "희소시설 1개 영향값"
        )

    print(
        f"- {facility_type}: "
        f"{max_count:.3f} "
        f"({calculation_method})"
    )
    
# ---------------------------------------------------------
# 2차 pass: 시설별 만점 기준으로 안전점수 계산
# ---------------------------------------------------------

result_rows = []

for raw_row in raw_grid_rows:

    facility_influence_dict = (
        raw_row["_facility_influence"]
    )

    # 원본 raw_grid_rows를 직접 변경하지 않도록 복사
    result_row = {
        key: value
        for key, value in raw_row.items()
        if key != "_facility_influence"
    }

    result_row["safety_score"] = (
        calculate_safety_score_cell(
            facility_influence_dict
        )
    )

    result_rows.append(result_row)


# ---------------------------------------------------------
# 일반적인 5등급 상대평가 기준 계산
# ---------------------------------------------------------
# 전체 격자를 20%씩 다섯 구간으로 나눔.
# A: 상위 20%, B: 다음 20%, C: 중간 20%, D: 다음 20%, E: 하위 20%
all_safety_scores = [
    row["safety_score"]
    for row in result_rows
]

grade_cutoffs["A"] = float(
    np.percentile(all_safety_scores, 80)
)
grade_cutoffs["B"] = float(
    np.percentile(all_safety_scores, 60)
)
grade_cutoffs["C"] = float(
    np.percentile(all_safety_scores, 40)
)
grade_cutoffs["D"] = float(
    np.percentile(all_safety_scores, 20)
)

print("[5등급 기준값]", grade_cutoffs)

# 3차 pass: 등급과 색상 추가
for cell_result_dict in result_rows:
    safety_grade = define_grade(
        cell_result_dict["safety_score"]
    )

    cell_result_dict["score_grade"] = safety_grade
    cell_result_dict["grade_color"] = (
        grade_color_dict[safety_grade]
    )

result_df = pd.DataFrame(
    result_rows,
    columns=result_columns,
)

print("[최종 격자 개수]", len(result_df))


# =========================================================
# 9. Folium 지도 함수
# =========================================================

def make_gwangjin_map():
    """광진구 중심 지도와 광진구 경계선을 만든다."""

    map_obj = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=13,
        control_scale=True,
    )

    folium.GeoJson(
        data=gwangjin_boundary_4326_gdf,
        name="광진구 경계",
        style_function=lambda _: {
            "color": "black",
            "weight": 2,
            "fillOpacity": 0,
        },
    ).add_to(map_obj)

    return map_obj


def make_grid_information_html(row):
    """격자 툴팁과 팝업에 들어갈 HTML 문자열을 만든다."""

    return f"""
    <div style="
        min-width: 190px;
        font-size: 13px;
        line-height: 1.55;
    ">
        <div style="font-size: 14px; margin-bottom: 4px;">
            <b>격자 {int(row['grid_id'])}번</b>
        </div>
        안전등급: <b>{row['score_grade']}</b><br>
        안전점수: <b>{row['safety_score']:.1f}점</b><br>
        <hr style="margin: 5px 0; border: 0; border-top: 1px solid #bbbbbb;">
        CCTV: {int(row['cctv_count'])}개<br>
        가로등: {int(row['streetlight_count'])}개<br>
        비상벨: {int(row['emergency_bell_count'])}개<br>
        경찰서: {int(row['police_station_count'])}개<br>
        파출소: {int(row['police_box_count'])}개<br>
        지구대: {int(row['police_substation_count'])}개<br>
        <b>전체 시설: {int(row['total_facility_count'])}개</b>
    </div>
    """


def add_grid_cells_with_safety_color(
    map_obj,
    grid_result_df,
    boundary_polygon,
):
    """
    안전등급 색상으로 격자를 표시한다.

    마우스를 격자에 올리면 시설물별 개수를 툴팁으로 표시하고,
    격자를 클릭하면 같은 내용을 팝업으로 표시한다.
    """

    grid_layer = folium.FeatureGroup(
        name="안전등급 격자",
        show=True,
    )

    for _, row in grid_result_df.iterrows():
        cell_polygon = make_cell_polygon(
            row["center_lat"],
            row["center_lng"],
        )

        clipped_polygon = cell_polygon.intersection(
            boundary_polygon
        )

        if clipped_polygon.is_empty:
            continue

        information_html = make_grid_information_html(row)

        # 커서를 올렸을 때 나타나는 정보창
        grid_tooltip = folium.Tooltip(
            text=information_html,
            sticky=True,
            direction="top",
            opacity=0.95,
            style=(
                "background-color: white; "
                "color: #222222; "
                "border: 1px solid #777777; "
                "border-radius: 5px; "
                "box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25); "
                "padding: 7px;"
            ),
        )

        # 클릭했을 때 고정해서 볼 수 있는 정보창
        grid_popup = folium.Popup(
            html=information_html,
            max_width=260,
        )

        grade_color = row["grade_color"]

        folium.GeoJson(
            data=mapping(clipped_polygon),
            name=f"격자 {int(row['grid_id'])}",
            style_function=(
                lambda _, color=grade_color: {
                    "fillColor": color,
                    "color": "gray",
                    "weight": 0.6,
                    "fillOpacity": 0.5,
                }
            ),
            highlight_function=lambda _: {
                "color": "black",
                "weight": 2,
                "fillOpacity": 0.7,
            },
            tooltip=grid_tooltip,
            popup=grid_popup,
            smooth_factor=0,
        ).add_to(grid_layer)

    grid_layer.add_to(map_obj)
    return map_obj


def add_grid_point_cross_markers(
    map_obj,
    grid_result_df,
):
    """실제로 사용된 격자의 중심점에 + 표시를 추가한다."""

    point_layer = folium.FeatureGroup(
        name="격자 중심점",
        show=False,
    )

    for _, row in grid_result_df.iterrows():
        folium.Marker(
            location=[
                row["center_lat"],
                row["center_lng"],
            ],
            icon=folium.DivIcon(
                html="""
                <div style="
                    pointer-events: none;
                    font-size: 18px;
                    font-weight: bold;
                    color: black;
                    width: 20px;
                    height: 20px;
                    line-height: 20px;
                    text-align: center;
                ">+</div>
                """,
                icon_size=(20, 20),
                icon_anchor=(10, 10),
            ),
        ).add_to(point_layer)

    point_layer.add_to(map_obj)
    return map_obj



def add_facility_circle_markers(
    map_obj,
    facility_df,
):
    """
    같은 좌표에 있는 시설물을 하나의 원형 마커로 묶어 표시한다.

    마커를 클릭하면 해당 좌표의 시설유형별 개수와
    전체 시설 개수를 확인할 수 있다.
    """

    facility_layer = folium.FeatureGroup(
        name="안전시설",
        show=True,
    )

    # 위도·경도별로 시설물 묶기
    grouped_facility = (
        facility_df
        .groupby(
            [
                "위도",
                "경도",
            ],
            dropna=False,
        )
        .agg(
            전체시설개수=(
                "시설유형",
                "size",
            ),

            시설유형별개수=(
                "시설유형",
                lambda x: x.value_counts().to_dict(),
            ),

            시설명목록=(
                "시설명",
                lambda x: list(
                    x.dropna()
                    .astype(str)
                    .unique()
                ),
            ),
        )
        .reset_index()
    )

    for _, facility in grouped_facility.iterrows():

        facility_type_count_dict = (
            facility["시설유형별개수"]
        )

        total_facility_count = int(
            facility["전체시설개수"]
        )

        # 시설유형별 개수 HTML 만들기
        facility_type_count_html = ""

        for facility_type, count in (
            facility_type_count_dict.items()
        ):
            facility_type_count_html += (
                f"{facility_type}: "
                f"<b>{count}개</b><br>"
            )

        # 시설명이 너무 길어지는 것을 막기 위해
        # 최대 10개까지만 표시
        facility_name_list = (
            facility["시설명목록"]
        )

        displayed_facility_names = (
            facility_name_list[:10]
        )

        facility_name_html = "<br>".join(
            displayed_facility_names
        )

        if len(facility_name_list) > 10:
            facility_name_html += (
                f"<br>외 "
                f"{len(facility_name_list) - 10}개"
            )

        popup_html = f"""
        <div style="
            min-width: 220px;
            font-size: 13px;
            line-height: 1.55;
        ">
            <b>해당 위치 시설 정보</b><br>
            <hr style="
                margin: 5px 0;
                border: 0;
                border-top: 1px solid #bbbbbb;
            ">

            {facility_type_count_html}

            <b>전체 시설: {total_facility_count}개</b><br>

            <hr style="
                margin: 5px 0;
                border: 0;
                border-top: 1px solid #bbbbbb;
            ">

            위도: {facility['위도']}<br>
            경도: {facility['경도']}<br>

            <br>
            <b>시설명</b><br>
            {facility_name_html}
        </div>
        """

        # 마커 색상 결정
        #
        # 시설유형이 하나뿐이면 해당 시설 색상 사용
        # 여러 시설유형이 섞여 있으면 보라색 사용
        facility_types = list(
            facility_type_count_dict.keys()
        )

        if len(facility_types) == 1:

            marker_color = (
                facility_color_dict.get(
                    facility_types[0],
                    "gray",
                )
            )

        else:

            marker_color = "purple"

        # 시설 개수가 많을수록 원을 조금 크게 표시
        marker_radius = min(
            3 + total_facility_count * 0.7,
            13,
        )

        tooltip_text = (
            f"이 위치에 시설 "
            f"{total_facility_count}개"
        )

        folium.CircleMarker(
            location=[
                facility["위도"],
                facility["경도"],
            ],
            radius=marker_radius,
            color=marker_color,
            weight=1,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.9,
            tooltip=tooltip_text,
            popup=folium.Popup(
                popup_html,
                max_width=320,
            ),
        ).add_to(facility_layer)

    facility_layer.add_to(map_obj)

    return map_obj



def add_grade_legend(map_obj):
    """지도 왼쪽 아래에 A~E 등급 색상 범례를 추가한다."""

    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background-color: white;
        border: 1px solid #777777;
        border-radius: 5px;
        padding: 10px 12px;
        font-size: 13px;
        line-height: 1.6;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
    ">
        <b>안전등급</b><br>
        <span style="color: green;">■</span> A<br>
        <span style="color: yellowgreen;">■</span> B<br>
        <span style="color: #d4c500;">■</span> C<br>
        <span style="color: orange;">■</span> D<br>
        <span style="color: red;">■</span> E
    </div>
    """

    map_obj.get_root().html.add_child(
        folium.Element(legend_html)
    )

    return map_obj


# =========================================================
# 10. 최종 지도 만들기
# =========================================================

gwangjin_map = make_gwangjin_map()

# 격자를 먼저 그려야 시설물 마커가 격자 위에 보임
add_grid_cells_with_safety_color(
    gwangjin_map,
    result_df,
    gwangjin_polygon_4326,
)

add_grid_point_cross_markers(
    gwangjin_map,
    result_df,
)

add_facility_circle_markers(
    gwangjin_map,
    facility_data,
)

add_grade_legend(gwangjin_map)

folium.LayerControl(
    collapsed=False
).add_to(gwangjin_map)


# =========================================================
# 11. 결과 저장
# =========================================================

html_output_path = (
    output_dir
    / "gwangjin_safety_map.html"
)

csv_output_path = (
    processed_dir
    / "safety_score_result.csv"
)

grid_geojson_output_path = (
    output_dir
    / "gwangjin_safety_grid.geojson"
)

facility_geojson_output_path = (
    output_dir
    / "gwangjin_facilities.geojson"
)

# 지도 HTML 저장
gwangjin_map.save(html_output_path)

# 격자 계산 결과 CSV 저장
result_df.to_csv(
    csv_output_path,
    index=False,
    encoding="utf-8-sig",
)

# 격자 Polygon을 geometry 컬럼으로 만들어 GeoJSON 저장
geometries = []

for _, row in result_df.iterrows():
    cell_polygon = make_cell_polygon(
        row["center_lat"],
        row["center_lng"],
    )

    clipped_polygon = cell_polygon.intersection(
        gwangjin_polygon_4326
    )

    geometries.append(clipped_polygon)

result_gdf = gpd.GeoDataFrame(
    result_df.copy(),
    geometry=geometries,
    crs="EPSG:4326",
)

result_gdf.to_file(
    grid_geojson_output_path,
    driver="GeoJSON",
    encoding="utf-8",
)

# 시설물도 Point geometry를 만들어 GeoJSON 저장
facility_gdf = gpd.GeoDataFrame(
    facility_data.copy(),
    geometry=gpd.points_from_xy(
        facility_data["경도"],
        facility_data["위도"],
    ),
    crs="EPSG:4326",
)

facility_gdf.to_file(
    facility_geojson_output_path,
    driver="GeoJSON",
    encoding="utf-8",
)

print("\n[저장 완료]")
print("지도 HTML:", html_output_path)
print("결과 CSV:", csv_output_path)
print("격자 GeoJSON:", grid_geojson_output_path)
print("시설물 GeoJSON:", facility_geojson_output_path)

# 저장된 최종 지도를 브라우저에서 열기
gwangjin_map.show_in_browser()
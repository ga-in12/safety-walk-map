"""
광진구 500m 격자별 안전점수 계산 및 Folium 지도 생성

추가된 기능
- 격자에 마우스 커서를 올리면 안전점수와 시설 유형별 개수가 툴팁으로 표시됨
- 격자를 클릭해도 같은 정보를 팝업으로 확인할 수 있음
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

# 광진구 중심 좌표
center_lat = 37.5384
center_lng = 127.0822

# 시설별 안전점수 가중치: 합계 100
safety_weight_dict = {
    "CCTV": 35,
    "가로등": 25,
    "비상벨": 15,
    "경찰서": 3,
    "파출소": 12,
    "지구대": 10,
}

# 시설별 만점 기준 개수
max_count_dict = {
    "CCTV": 40,
    "가로등": 80,
    "비상벨": 30,
    "경찰서": 1,
    "파출소": 1,
    "지구대": 1,
}

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


def calculate_safety_score_cell(facility_count_dict):
    """시설별 개수와 가중치로 한 격자의 안전점수를 계산한다."""

    safety_score = 0.0

    for facility_type, weight in safety_weight_dict.items():
        count = facility_count_dict[facility_type]
        max_count = max_count_dict[facility_type]

        ratio = min(count / max_count, 1)
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

result_rows = []
total_point_count = len(point_list)

# 1차 pass: 모든 격자의 안전점수부터 계산
for point_number, (
    point_lat,
    point_lng,
    row_index,
    col_index,
) in enumerate(point_list, start=1):

    print(
        f"\r격자 계산 중(1차: 점수): "
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

    facility_count_dict = counting_facility(
        cell_polygon,
        facility_data,
    )

    safety_score = calculate_safety_score_cell(
        facility_count_dict
    )

    result_rows.append(
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
            "safety_score": safety_score,
        }
    )

print("\n1차 pass 완료")

if not result_rows:
    raise RuntimeError(
        "광진구 경계와 겹치는 격자가 하나도 생성되지 않았습니다."
    )

# 상대평가 등급 컷 계산
all_safety_scores = [
    row["safety_score"]
    for row in result_rows
]

grade_cutoffs["A"] = float(
    np.percentile(all_safety_scores, 90)
)
grade_cutoffs["B"] = float(
    np.percentile(all_safety_scores, 65)
)
grade_cutoffs["C"] = float(
    np.percentile(all_safety_scores, 35)
)
grade_cutoffs["D"] = float(
    np.percentile(all_safety_scores, 10)
)

print("등급 컷 기준값:", grade_cutoffs)

# 2차 pass: 등급과 색상 추가
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
    """시설물의 위치를 유형별 색상이 다른 원형 마커로 표시한다."""

    facility_layer = folium.FeatureGroup(
        name="안전시설",
        show=True,
    )

    for _, facility in facility_df.iterrows():
        facility_type = facility["시설유형"]

        marker_color = facility_color_dict.get(
            facility_type,
            "gray",
        )

        marker_tooltip = facility_type

        if "시설명" in facility_df.columns:
            facility_name = facility.get("시설명")
            if pd.notna(facility_name):
                marker_tooltip = (
                    f"{facility_type}: {facility_name}"
                )

        folium.CircleMarker(
            location=[
                facility["위도"],
                facility["경도"],
            ],
            radius=2.5,
            color=marker_color,
            weight=1,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.85,
            tooltip=marker_tooltip,
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
# =========================================================
# 광진구 경계 기반 500m 격자 생성
# + 격자 polygon 안 시설 개수 계산
# + 경계 격자 면적 보정
# + 자투리 격자 제거 없음
# + 안전점수 계산
# + Folium 지도 생성
#
# 핵심:
# - 500m x 500m 격자를 만든다.
# - 광진구 경계와 겹치는 부분만 잘라서 사용한다.
# - 경계 때문에 잘린 작은 격자도 제거하지 않는다.
# - 잘린 격자는 실제 면적비율로 시설 개수를 보정한다.
#
# 보정개수 = 실제개수 / area_ratio
# area_ratio = 실제 격자 면적 / 250000
# =========================================================

import json
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import folium

from shapely.geometry import box, Polygon
from shapely.ops import unary_union


# =========================================================
# 0. 경로 설정
# =========================================================

# 현재 파일 위치 예시:
# safety-walk-map/scripts/final_safety_score_polygon_area_corrected_no_drop.py
# BASE_DIR = safety-walk-map 폴더
BASE_DIR = Path(__file__).resolve().parents[1]

# 시설물 통합 CSV
facility_path = BASE_DIR / "data" / "raw" / "광진구_안전시설_통합.csv"

# 광진구 경계 SHP 폴더
boundary_dir = BASE_DIR / "data" / "raw" / "boundary" / "lgldong"

# 저장 폴더
processed_dir = BASE_DIR / "data" / "processed"
output_dir = BASE_DIR / "outputs"

processed_dir.mkdir(parents=True, exist_ok=True)
output_dir.mkdir(parents=True, exist_ok=True)


# =========================================================
# 1. 설정값
# =========================================================

# 격자 한 칸 크기: 500m x 500m
cell_size_m = 500

# 500m x 500m 전체 격자 면적
full_cell_area_m2 = cell_size_m * cell_size_m  # 250,000m²

# 경계선 근처 좌표 오차 허용 거리
# 지도 표시/검사용으로 경계 근처 시설까지 포함
facility_boundary_tolerance_m = 100

# 시설유형별 가중치
safety_weight_dict = {
    "CCTV": 35,
    "가로등": 30,
    "비상벨": 20,
    "경찰서": 15
}

# 시설유형별 만점 기준 개수
max_count_dict = {
    "CCTV": 50,
    "가로등": 100,
    "비상벨": 20,
    "경찰서": 2
}

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


# =========================================================
# 2. 시작 전 파일 확인
# =========================================================

print("프로젝트 루트:", BASE_DIR)

print("\n시설물 파일 경로:", facility_path)
print("시설물 파일 존재 여부:", facility_path.exists())

print("\n경계 폴더 경로:", boundary_dir)
print("경계 폴더 존재 여부:", boundary_dir.exists())

if not facility_path.exists():
    raise FileNotFoundError(
        f"시설물 파일을 찾지 못했습니다: {facility_path}"
    )

if not boundary_dir.exists():
    raise FileNotFoundError(
        f"경계 폴더를 찾지 못했습니다: {boundary_dir}"
    )

# boundary_dir 안의 shp 파일 자동 찾기
shp_files = list(boundary_dir.glob("*.shp"))

print("\n찾은 SHP 파일:")
for file in shp_files:
    print("-", file.name)

if len(shp_files) == 0:
    raise FileNotFoundError(
        "data/raw/boundary/lgldong 폴더 안에 .shp 파일이 없습니다."
    )

boundary_path = shp_files[0]

print("\n사용할 경계 파일:", boundary_path)


# =========================================================
# 3. SHP 파일 읽기 함수
# =========================================================

def read_shp_file(shp_path):
    """
    SHP 파일을 읽는 함수.
    한글 인코딩 문제를 줄이기 위해 여러 인코딩을 순서대로 시도함.
    """

    encoding_list = ["cp949", "euc-kr", "utf-8", None]

    last_error = None

    for enc in encoding_list:
        try:
            if enc is None:
                gdf = gpd.read_file(shp_path)
            else:
                gdf = gpd.read_file(shp_path, encoding=enc)

            print(f"\nSHP 읽기 성공 - encoding: {enc}")
            return gdf

        except Exception as e:
            last_error = e
            print(f"SHP 읽기 실패 - encoding: {enc}")

    raise last_error


# =========================================================
# 4. 광진구 경계 만들기
# =========================================================

def load_gwangjin_boundary(boundary_path):
    """
    법정동 경계 SHP에서 광진구에 해당하는 동만 골라
    하나의 광진구 경계 polygon으로 합치는 함수.

    광진구 법정동 코드는 보통 11215로 시작함.
    """

    boundary = read_shp_file(boundary_path)

    print("\n경계 파일 컬럼 목록:")
    print(boundary.columns)

    print("\n경계 파일 앞부분:")
    print(boundary.head())

    print("\n원본 CRS:", boundary.crs)

    # CRS가 없으면 좌표값 범위를 보고 추정
    if boundary.crs is None:
        minx, miny, maxx, maxy = boundary.total_bounds

        # 좌표가 경도/위도처럼 보이면 EPSG:4326
        if 120 <= minx <= 140 and 30 <= miny <= 45:
            boundary = boundary.set_crs(epsg=4326)
            print("CRS가 없어 EPSG:4326으로 설정했습니다.")
        else:
            # 행정구역 SHP는 보통 미터 단위 좌표계라서 EPSG:5179로 가정
            boundary = boundary.set_crs(epsg=5179)
            print("CRS가 없어 EPSG:5179로 설정했습니다.")

    # 거리, 면적 계산용 미터 좌표계로 변환
    boundary = boundary.to_crs(epsg=5179)

    # geometry 깨짐 방지
    boundary["geometry"] = boundary["geometry"].buffer(0)

    gwangjin = None

    # 코드 컬럼 후보
    code_cols = [
        "adm_cd",
        "ADM_CD",
        "bjd_cd",
        "BJD_CD",
        "법정동코드",
        "법정동코",
        "EMD_CD",
        "emd_cd",
        "CODE",
        "code"
    ]

    # 이름 컬럼 후보
    name_cols = [
        "adm_nm",
        "ADM_NM",
        "bjd_nm",
        "BJD_NM",
        "법정동명",
        "행정구역명",
        "EMD_NM",
        "emd_nm",
        "name",
        "NAME"
    ]

    # 1순위: 코드 컬럼에서 11215로 시작하는 값 찾기
    for col in code_cols:
        if col in boundary.columns:
            temp = boundary[
                boundary[col].astype(str).str.startswith("11215")
            ]

            if len(temp) > 0:
                gwangjin = temp.copy()
                print("\n광진구 필터링 기준 컬럼:", col)
                print("선택된 행 개수:", len(gwangjin))
                break

    # 2순위: 이름 컬럼에서 광진구 포함 값 찾기
    if gwangjin is None:
        for col in name_cols:
            if col in boundary.columns:
                temp = boundary[
                    boundary[col].astype(str).str.contains("광진구", na=False)
                ]

                if len(temp) > 0:
                    gwangjin = temp.copy()
                    print("\n광진구 필터링 기준 컬럼:", col)
                    print("선택된 행 개수:", len(gwangjin))
                    break

    # 3순위: 모든 문자형 컬럼에서 광진구 포함 값 찾기
    if gwangjin is None:
        for col in boundary.columns:
            if col == "geometry":
                continue

            temp = boundary[
                boundary[col].astype(str).str.contains("광진구", na=False)
            ]

            if len(temp) > 0:
                gwangjin = temp.copy()
                print("\n광진구 필터링 기준 컬럼:", col)
                print("선택된 행 개수:", len(gwangjin))
                break

    if gwangjin is None or len(gwangjin) == 0:
        raise ValueError(
            "광진구 행을 찾지 못했습니다. "
            "터미널에 출력된 컬럼 목록과 앞부분 데이터를 확인해야 합니다."
        )

    print("\n광진구로 선택된 데이터 일부:")
    print(gwangjin.head())

    # geometry 재보정
    gwangjin["geometry"] = gwangjin["geometry"].buffer(0)

    # 광진구 동 polygon들을 하나로 합치기
    gwangjin_boundary = gwangjin.dissolve()

    # dissolve 후에도 geometry 보정
    gwangjin_boundary["geometry"] = gwangjin_boundary["geometry"].buffer(0)

    print("\n광진구 경계 생성 완료")
    print("광진구 경계 개수:", len(gwangjin_boundary))
    print("광진구 경계 CRS:", gwangjin_boundary.crs)

    return gwangjin_boundary


boundary_gdf = load_gwangjin_boundary(boundary_path)
boundary_poly = boundary_gdf.geometry.iloc[0]

print("\n광진구 경계 불러오기 완료")
print("경계 bounds:", boundary_poly.bounds)


# =========================================================
# 5. 시설물 데이터 불러오기
# =========================================================

facilities = pd.read_csv(facility_path, encoding="utf-8-sig")

print("\n시설물 데이터 컬럼:")
print(facilities.columns)

required_cols = ["시설유형", "위도", "경도"]

for col in required_cols:
    if col not in facilities.columns:
        raise ValueError(f"시설물 CSV에 '{col}' 컬럼이 없습니다.")

# 위도/경도 숫자 변환
facilities["위도"] = pd.to_numeric(facilities["위도"], errors="coerce")
facilities["경도"] = pd.to_numeric(facilities["경도"], errors="coerce")

# 위도/경도 없는 행 제거
facilities = facilities.dropna(subset=["위도", "경도"]).copy()

# 시설유형 공백 제거
facilities["시설유형"] = facilities["시설유형"].astype(str).str.strip()

# 시설물 고유 ID 생성
# 경계선 위 시설이 두 격자에 걸릴 때 중복 계산 방지용
facilities = facilities.reset_index(drop=True)
facilities["facility_id"] = facilities.index + 1

print("\n시설물 데이터 개수:", len(facilities))
print("시설유형 목록:")
print(facilities["시설유형"].value_counts())

# GeoDataFrame으로 변환
# CSV는 위도/경도이므로 EPSG:4326
facilities_gdf = gpd.GeoDataFrame(
    facilities,
    geometry=gpd.points_from_xy(facilities["경도"], facilities["위도"]),
    crs="EPSG:4326"
)

# 미터 좌표계로 변환
facilities_gdf = facilities_gdf.to_crs(epsg=5179)


# =========================================================
# 6. 시설물이 광진구 경계 안에 있는지 검사
# =========================================================

facilities_gdf["inside_gwangjin"] = facilities_gdf.geometry.within(boundary_poly)

# 경계 근처 오차 허용
boundary_with_tolerance = boundary_poly.buffer(facility_boundary_tolerance_m)

facilities_gdf["inside_or_near_gwangjin"] = facilities_gdf.geometry.within(
    boundary_with_tolerance
)

outside_facilities = facilities_gdf[
    facilities_gdf["inside_or_near_gwangjin"] == False
].copy()

inside_or_near_count = int(facilities_gdf["inside_or_near_gwangjin"].sum())

print("\n광진구 경계 안 또는 근처 시설 수:", inside_or_near_count)
print("경계 밖으로 의심되는 시설 수:", len(outside_facilities))

if inside_or_near_count == 0:
    raise ValueError(
        "광진구 경계 안 또는 근처로 판정된 시설물이 0개입니다. "
        "경계 SHP의 CRS 또는 광진구 필터링이 잘못되었을 수 있습니다."
    )

# 경계 밖 의심 시설 저장
if len(outside_facilities) > 0:
    outside_facilities_4326 = outside_facilities.to_crs(epsg=4326).copy()

    outside_facilities_4326["위도_변환확인"] = outside_facilities_4326.geometry.y
    outside_facilities_4326["경도_변환확인"] = outside_facilities_4326.geometry.x

    outside_output_path = processed_dir / "outside_suspicious_facilities.csv"

    outside_facilities_4326.drop(columns="geometry").to_csv(
        outside_output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("경계 밖 의심 시설 CSV 저장 완료:", outside_output_path)

# 지도 표시용으로는 경계 안 또는 근처 시설을 사용
# 실제 점수 계산은 뒤에서 격자 polygon과 만나는 시설만 카운트됨
facilities_for_score = facilities_gdf[
    facilities_gdf["inside_or_near_gwangjin"] == True
].copy()


# =========================================================
# 7. polygon 형태만 남기는 함수
# =========================================================
# intersection 결과가 아주 드물게 GeometryCollection, LineString, Point가 될 수 있음.
# 지도에 색칠 가능한 것은 Polygon 또는 MultiPolygon임.
# 자투리 polygon은 제거하지 않음.
# 단, 면적이 0인 선/점은 색칠할 면적 자체가 없으므로 제외함.
# =========================================================

def keep_polygon_part(geom):
    """
    Polygon 또는 MultiPolygon만 반환.
    GeometryCollection 안에 polygon이 섞여 있으면 polygon 부분만 합쳐서 반환.
    선/점만 있으면 빈 Polygon 반환.
    """

    if geom.is_empty:
        return Polygon()

    if geom.geom_type in ["Polygon", "MultiPolygon"]:
        return geom

    if geom.geom_type == "GeometryCollection":
        polygon_parts = []

        for part in geom.geoms:
            if part.geom_type in ["Polygon", "MultiPolygon"]:
                polygon_parts.append(part)

        if len(polygon_parts) == 0:
            return Polygon()

        return unary_union(polygon_parts)

    return Polygon()


# =========================================================
# 8. 광진구 500m 격자 polygon 만들기
# =========================================================

minx, miny, maxx, maxy = boundary_poly.bounds

grid_cells = []
grid_id = 0

x_list = np.arange(minx, maxx, cell_size_m)
y_list = np.arange(miny, maxy, cell_size_m)

for x in x_list:
    for y in y_list:

        # 원래 500m x 500m 사각형
        raw_cell = box(
            x,
            y,
            x + cell_size_m,
            y + cell_size_m
        )

        # 광진구 경계와 겹치는 부분만 남기기
        clipped_cell = raw_cell.intersection(boundary_poly)

        # polygon 부분만 남기기
        clipped_cell = keep_polygon_part(clipped_cell)

        # 광진구와 아예 안 겹치면 제외
        if clipped_cell.is_empty:
            continue

        # 면적이 0이면 선/점이라서 지도에 색칠할 수 없음
        # 자투리 polygon은 제거하지 않음
        cell_area_m2 = clipped_cell.area

        if cell_area_m2 <= 0:
            continue

        # 전체 500m x 500m 격자 대비 실제 면적 비율
        area_ratio = cell_area_m2 / full_cell_area_m2

        # 계산 오차로 1보다 살짝 커지는 경우 방지
        area_ratio = min(area_ratio, 1)

        grid_id += 1
        this_grid_id = f"G{grid_id:04d}"

        grid_cells.append({
            "grid_id": this_grid_id,
            "cell_area_m2": cell_area_m2,
            "full_cell_area_m2": full_cell_area_m2,
            "area_ratio": area_ratio,
            "is_boundary_cell": area_ratio < 0.999,
            "geometry": clipped_cell
        })


grid_cells_gdf = gpd.GeoDataFrame(
    grid_cells,
    geometry="geometry",
    crs="EPSG:5179"
)

print("\n생성된 격자 cell 개수:", len(grid_cells_gdf))

if len(grid_cells_gdf) == 0:
    raise ValueError(
        "생성된 격자가 0개입니다. 광진구 경계 polygon 또는 cell_size_m을 확인해야 합니다."
    )

print("\n격자 면적 비율 요약:")
print(grid_cells_gdf["area_ratio"].describe())

print("\n경계 때문에 잘린 격자 수:")
print(grid_cells_gdf["is_boundary_cell"].value_counts())


# =========================================================
# 9. 격자 대표점 CSV 저장
# =========================================================
# 주의:
# 이 대표점은 계산용이 아님.
# 지도에서 격자 위치를 확인하거나 CSV에 위도/경도를 저장하기 위한 용도임.
# 실제 시설 개수 계산은 아래 10번에서 격자 polygon 기준으로 진행함.
# =========================================================

grid_points_gdf = grid_cells_gdf.copy()
grid_points_gdf["geometry"] = grid_points_gdf.geometry.representative_point()

grid_points_4326 = grid_points_gdf.to_crs(epsg=4326).copy()

grid_points_csv = pd.DataFrame({
    "grid_id": grid_points_4326["grid_id"],
    "위도": grid_points_4326.geometry.y,
    "경도": grid_points_4326.geometry.x,
    "cell_area_m2": grid_points_4326["cell_area_m2"].round(2),
    "full_cell_area_m2": grid_points_4326["full_cell_area_m2"],
    "area_ratio": grid_points_4326["area_ratio"].round(6),
    "is_boundary_cell": grid_points_4326["is_boundary_cell"]
})

grid_points_output_path = processed_dir / "gwangjin_grid_points_area_corrected_no_drop.csv"

grid_points_csv.to_csv(
    grid_points_output_path,
    index=False,
    encoding="utf-8-sig"
)

print("격자 대표점 CSV 저장 완료:", grid_points_output_path)


# =========================================================
# 10. 격자 polygon 안 시설 개수 세기
# =========================================================
# 핵심:
# - 실제 지도에 색칠되는 polygon 안 시설만 센다.
# - predicate="intersects" 사용.
# - 시설 점이 격자 경계선 위에 딱 걸친 경우도 포함하기 위해서.
# - 단, 같은 시설이 여러 격자에 잡히면 facility_id 기준으로 하나만 남김.
# =========================================================

joined_raw = gpd.sjoin(
    facilities_for_score[["facility_id", "시설유형", "geometry"]],
    grid_cells_gdf[["grid_id", "geometry"]],
    how="inner",
    predicate="intersects"
)

print("\n격자 polygon과 매칭된 시설 수 - 중복 제거 전:", len(joined_raw))

# 경계선 위 시설이 여러 격자와 매칭될 경우 중복 제거
# 같은 시설이 여러 격자에 잡히면 grid_id가 빠른 격자 하나에만 배정
joined = (
    joined_raw
    .sort_values(["facility_id", "grid_id"])
    .drop_duplicates(subset=["facility_id"], keep="first")
    .copy()
)

print("격자 polygon과 매칭된 시설 수 - 중복 제거 후:", len(joined))

# 어떤 격자에 어떤 시설유형이 몇 개 들어갔는지 표로 만들기
if len(joined) > 0:
    count_table = (
        joined
        .groupby(["grid_id", "시설유형"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
else:
    count_table = pd.DataFrame({"grid_id": grid_cells_gdf["grid_id"]})

# 필요한 시설유형 컬럼이 없으면 0으로 추가
for facility_type in safety_weight_dict.keys():
    if facility_type not in count_table.columns:
        count_table[facility_type] = 0

# 격자 polygon에 시설 개수 붙이기
safety_grid = grid_cells_gdf.merge(
    count_table,
    on="grid_id",
    how="left"
)

# NaN을 0으로 채우기
for facility_type in safety_weight_dict.keys():
    safety_grid[facility_type] = safety_grid[facility_type].fillna(0).astype(int)


# =========================================================
# 11. 경계 격자 면적 보정
# =========================================================
# 자투리 격자 제거 안 함.
# 대신 잘린 격자는 면적비율로 시설 개수를 보정함.
#
# 보정개수 = 실제개수 / area_ratio
#
# 예:
# area_ratio = 0.5
# CCTV 실제개수 = 10
# CCTV 보정개수 = 10 / 0.5 = 20
# =========================================================

for facility_type in safety_weight_dict.keys():
    corrected_col = f"{facility_type}보정개수"

    safety_grid[corrected_col] = np.where(
        safety_grid["area_ratio"] > 0,
        safety_grid[facility_type] / safety_grid["area_ratio"],
        0
    )


# =========================================================
# 12. 안전점수 / 안전등급 계산
# =========================================================

def calculate_safety_score(row):
    """
    한 격자 polygon 안에 들어있는 시설 개수를 이용해 안전점수 계산.
    단, 광진구 경계 때문에 잘린 격자는 면적비율로 보정한 시설 개수를 사용함.
    """

    score = 0

    for facility_type, weight in safety_weight_dict.items():

        # 실제 개수가 아니라 면적 보정 개수 사용
        corrected_count_col = f"{facility_type}보정개수"
        count = row[corrected_count_col]

        max_count = max_count_dict[facility_type]

        ratio = count / max_count

        # 만점 기준 이상이면 1로 고정
        if ratio > 1:
            ratio = 1

        score += ratio * weight

    return score


def convert_score_to_grade(score):
    """
    안전점수를 A~E 등급으로 변환
    """

    if score >= 85:
        return "A"
    elif score >= 70:
        return "B"
    elif score >= 55:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "E"


safety_grid["안전점수"] = safety_grid.apply(calculate_safety_score, axis=1)
safety_grid["안전등급"] = safety_grid["안전점수"].apply(convert_score_to_grade)

# 실제 시설 개수
safety_grid["CCTV개수"] = safety_grid["CCTV"]
safety_grid["가로등개수"] = safety_grid["가로등"]
safety_grid["비상벨개수"] = safety_grid["비상벨"]
safety_grid["경찰서개수"] = safety_grid["경찰서"]

safety_grid["전체시설개수"] = (
    safety_grid["CCTV개수"]
    + safety_grid["가로등개수"]
    + safety_grid["비상벨개수"]
    + safety_grid["경찰서개수"]
)

# 면적 보정 시설 개수
safety_grid["전체시설보정개수"] = (
    safety_grid["CCTV보정개수"]
    + safety_grid["가로등보정개수"]
    + safety_grid["비상벨보정개수"]
    + safety_grid["경찰서보정개수"]
)

print("\n안전등급 분포:")
print(safety_grid["안전등급"].value_counts().sort_index())

print("\n안전점수 요약:")
print(safety_grid["안전점수"].describe())


# =========================================================
# 13. 안전점수 CSV 저장
# =========================================================

safety_grid_points = safety_grid.copy()
safety_grid_points["geometry"] = safety_grid_points.geometry.representative_point()
safety_grid_points_4326 = safety_grid_points.to_crs(epsg=4326).copy()

safety_csv = pd.DataFrame({
    "grid_id": safety_grid_points_4326["grid_id"],
    "대표점_위도": safety_grid_points_4326.geometry.y,
    "대표점_경도": safety_grid_points_4326.geometry.x,

    "cell_size_m": cell_size_m,
    "cell_area_m2": safety_grid_points_4326["cell_area_m2"].round(2),
    "full_cell_area_m2": safety_grid_points_4326["full_cell_area_m2"],
    "area_ratio": safety_grid_points_4326["area_ratio"].round(6),
    "is_boundary_cell": safety_grid_points_4326["is_boundary_cell"],

    "계산방식": "격자 polygon 안 실제 시설 개수 + 경계 격자 면적 보정 + 자투리 격자 제거 없음",

    "CCTV개수": safety_grid_points_4326["CCTV개수"],
    "가로등개수": safety_grid_points_4326["가로등개수"],
    "비상벨개수": safety_grid_points_4326["비상벨개수"],
    "경찰서개수": safety_grid_points_4326["경찰서개수"],
    "전체시설개수": safety_grid_points_4326["전체시설개수"],

    "CCTV보정개수": safety_grid_points_4326["CCTV보정개수"].round(2),
    "가로등보정개수": safety_grid_points_4326["가로등보정개수"].round(2),
    "비상벨보정개수": safety_grid_points_4326["비상벨보정개수"].round(2),
    "경찰서보정개수": safety_grid_points_4326["경찰서보정개수"].round(2),
    "전체시설보정개수": safety_grid_points_4326["전체시설보정개수"].round(2),

    "안전점수": safety_grid_points_4326["안전점수"].round(2),
    "안전등급": safety_grid_points_4326["안전등급"]
})

safety_output_path = processed_dir / "safety_grid_area_corrected_no_drop.csv"

safety_csv.to_csv(
    safety_output_path,
    index=False,
    encoding="utf-8-sig"
)

print("안전점수 CSV 저장 완료:", safety_output_path)


# =========================================================
# 14. 안전등급 격자 GeoJSON 저장
# =========================================================

safety_grid_4326 = safety_grid.to_crs(epsg=4326).copy()

# GeoJSON에 들어갈 숫자 컬럼 반올림
round_cols = [
    "cell_area_m2",
    "area_ratio",
    "안전점수",
    "CCTV보정개수",
    "가로등보정개수",
    "비상벨보정개수",
    "경찰서보정개수",
    "전체시설보정개수"
]

for col in round_cols:
    if col in safety_grid_4326.columns:
        safety_grid_4326[col] = safety_grid_4326[col].round(6)

grid_geojson_output_path = processed_dir / "gwangjin_safety_grid_cells_area_corrected_no_drop.geojson"

safety_grid_4326.to_file(
    grid_geojson_output_path,
    driver="GeoJSON"
)

print("안전등급 격자 GeoJSON 저장 완료:", grid_geojson_output_path)


# =========================================================
# 15. 시설-격자 매칭 결과 CSV 저장
# =========================================================
# 어떤 시설이 어떤 격자에 들어갔는지 확인할 때 사용
# =========================================================

if len(joined) > 0:
    joined_for_save = joined.merge(
        facilities_gdf.drop(columns="geometry"),
        on=["facility_id", "시설유형"],
        how="left"
    )

    facility_grid_match_output_path = processed_dir / "facility_grid_match_area_corrected_no_drop.csv"

    joined_for_save.drop(columns=["index_right"], errors="ignore").to_csv(
        facility_grid_match_output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print("시설-격자 매칭 CSV 저장 완료:", facility_grid_match_output_path)


# =========================================================
# 16. Folium 지도 만들기
# =========================================================

# 지도 중심점 계산
center_point_5179 = boundary_poly.centroid

center_point_4326 = gpd.GeoSeries(
    [center_point_5179],
    crs="EPSG:5179"
).to_crs(epsg=4326).iloc[0]

center_lat = center_point_4326.y
center_lng = center_point_4326.x

m = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=14,
    tiles="CartoDB Voyager"
)


# =========================================================
# 17. 광진구 경계 표시
# =========================================================

boundary_4326 = boundary_gdf.to_crs(epsg=4326)

folium.GeoJson(
    data=json.loads(boundary_4326.to_json()),
    name="광진구 경계",
    style_function=lambda feature: {
        "color": "black",
        "weight": 3,
        "fill": False
    },
    tooltip="광진구 경계"
).add_to(m)


# =========================================================
# 18. 안전등급 격자 polygon 표시
# =========================================================

def style_grid_cell(feature):
    grade = feature["properties"].get("안전등급", "E")
    color = grade_color_dict.get(grade, "gray")

    return {
        "color": color,
        "weight": 1,
        "fillColor": color,
        "fillOpacity": 0.45
    }


grid_geojson_data = json.loads(safety_grid_4326.to_json())

folium.GeoJson(
    data=grid_geojson_data,
    name="안전등급 격자 - 면적 보정 / 자투리 제거 없음",
    style_function=style_grid_cell,
    tooltip=folium.GeoJsonTooltip(
        fields=[
            "grid_id",
            "안전점수",
            "안전등급",

            "cell_area_m2",
            "full_cell_area_m2",
            "area_ratio",
            "is_boundary_cell",

            "CCTV개수",
            "가로등개수",
            "비상벨개수",
            "경찰서개수",
            "전체시설개수",

            "CCTV보정개수",
            "가로등보정개수",
            "비상벨보정개수",
            "경찰서보정개수",
            "전체시설보정개수"
        ],
        aliases=[
            "격자ID",
            "안전점수",
            "안전등급",

            "실제 격자면적㎡",
            "원래 격자면적㎡",
            "면적비율",
            "경계 잘림 여부",

            "CCTV 실제",
            "가로등 실제",
            "비상벨 실제",
            "경찰서 실제",
            "전체시설 실제",

            "CCTV 보정",
            "가로등 보정",
            "비상벨 보정",
            "경찰서 보정",
            "전체시설 보정"
        ],
        localize=True
    )
).add_to(m)


# =========================================================
# 19. 격자 대표점 표시
# =========================================================

grid_point_layer = folium.FeatureGroup(name="격자 대표점")

for _, row in safety_csv.iterrows():
    folium.CircleMarker(
        location=[row["대표점_위도"], row["대표점_경도"]],
        radius=2,
        color="black",
        fill=True,
        fill_color="black",
        fill_opacity=0.8,
        tooltip=(
            f"{row['grid_id']} / "
            f"{row['안전등급']}등급 / "
            f"{row['안전점수']:.1f}점 / "
            f"면적비율 {row['area_ratio']}"
        )
    ).add_to(grid_point_layer)

grid_point_layer.add_to(m)


# =========================================================
# 20. 시설물 표시
# =========================================================

facilities_for_map = facilities_for_score.to_crs(epsg=4326).copy()

for facility_type in facilities_for_map["시설유형"].unique():

    one_type = facilities_for_map[
        facilities_for_map["시설유형"] == facility_type
    ].copy()

    facility_layer = folium.FeatureGroup(name=f"시설물 - {facility_type}")

    marker_color = facility_color_dict.get(facility_type, "gray")

    for _, row in one_type.iterrows():

        lat = row.geometry.y
        lng = row.geometry.x

        popup_text = f"""
        <b>시설유형:</b> {row.get('시설유형', '')}<br>
        <b>시설명:</b> {row.get('시설명', '')}<br>
        <b>주소:</b> {row.get('주소', '')}<br>
        <b>위도:</b> {lat}<br>
        <b>경도:</b> {lng}
        """

        folium.CircleMarker(
            location=[lat, lng],
            radius=3,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.8,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=facility_type
        ).add_to(facility_layer)

    facility_layer.add_to(m)


# =========================================================
# 21. 경계 밖 의심 시설 표시
# =========================================================

if len(outside_facilities) > 0:

    outside_map = outside_facilities.to_crs(epsg=4326).copy()
    outside_layer = folium.FeatureGroup(name="경계 밖 의심 시설")

    for _, row in outside_map.iterrows():

        lat = row.geometry.y
        lng = row.geometry.x

        popup_text = f"""
        <b>경계 밖 의심 시설</b><br>
        <b>시설유형:</b> {row.get('시설유형', '')}<br>
        <b>시설명:</b> {row.get('시설명', '')}<br>
        <b>주소:</b> {row.get('주소', '')}<br>
        <b>위도:</b> {lat}<br>
        <b>경도:</b> {lng}
        """

        folium.CircleMarker(
            location=[lat, lng],
            radius=5,
            color="black",
            fill=True,
            fill_color="white",
            fill_opacity=1,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip="경계 밖 의심 시설"
        ).add_to(outside_layer)

    outside_layer.add_to(m)


# =========================================================
# 22. 범례 추가
# =========================================================

legend_html = """
<div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 300px;
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
<b>계산 기준</b><br>
500m x 500m 격자 polygon 안 시설 개수<br>
경계에 잘린 격자는 면적비율로 시설 개수 보정<br>
보정개수 = 실제개수 / 면적비율<br>
자투리 격자 제거 안 함<br>
반경 원 계산 사용 안 함<br>
<hr>
<span style="color:black;">●</span> 격자 대표점<br>
<span style="color:blue;">●</span> CCTV<br>
<span style="color:orange;">●</span> 가로등<br>
<span style="color:red;">●</span> 비상벨<br>
<span style="color:purple;">●</span> 경찰서<br>
<span style="color:black;">○</span> 경계 밖 의심 시설<br>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))


# =========================================================
# 23. 레이어 컨트롤 + 지도 저장
# =========================================================

folium.LayerControl().add_to(m)

map_output_path = output_dir / "gwangjin_safety_grid_map_area_corrected.html"

m.save(map_output_path)

print("\n지도 저장 완료:", map_output_path)
print("완료!")
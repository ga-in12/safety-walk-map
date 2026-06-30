"""
안전지수 산출 골격 코드 (safety_index_skeleton.py)

[이 코드가 하는 일]
1. 데이터 파트가 만들어줄 통합 시설 CSV(facilities_clean.csv)를 입력으로 받는다.
2. 광진구 지역을 격자(grid)로 잘게 쪼갠다.
3. 각 격자점마다 "반경 1km 안에 CCTV/가로등/비상벨/경찰시설이 몇 개 있는지" 센다.
4. 센 개수를 0~1 점수로 정규화한다 (CCTV는 30대 넘게 나올 수 있고 경찰서는 1개만 있어도 의미가 크기 때문).
5. 정규화한 값에 가중치를 곱해서 더한 뒤 0~100점 안전점수(safety_score)를 만든다.
6. 점수를 A~E 등급으로 바꾼다.
7. 최종 결과를 safety_grid.csv로 저장한다. -> 이 파일을 UI 담당(지도/히트맵)과 경로 담당이 가져다 씀.

[UI 담당 코드와 맞춘 부분]
UI 친구가 쓰는 표준 컬럼명: "위도", "경도", "시설유형", "주소"
여기에 안전지수 계산을 위해 "count" 컬럼 하나만 추가로 요구함.
  - CCTV: count = 카메라대수
  - 가로등/비상벨/파출소/지구대/경찰서: count = 1 (한 행 = 시설 1개)

데이터 파트가 통합 CSV를 줄 때 컬럼명이 이 5개(위도, 경도, 시설유형, 주소, count)로
맞춰져 있으면, 아래 INPUT_PATH 한 줄만 바꿔서 바로 실행하면 됨.
"""

import math
import numpy as np
import pandas as pd


# ============================================================
# 0. 컬럼명 설정 (UI 담당 코드의 STANDARD_COLUMNS와 동일하게 맞춤)
# ============================================================
# UI 코드의 STANDARD_COLUMNS = {"lat": "위도", "lng": "경도", "type": "시설유형", "address": "주소"}
# 여기에 count만 추가로 사용함
LAT_COL = "위도"
LNG_COL = "경도"
TYPE_COL = "시설유형"
ADDRESS_COL = "주소"
COUNT_COL = "count"


# ============================================================
# 1. 시설유형 이름 통일 매핑
# ============================================================
# 데이터 파트/UI 파트가 주는 시설유형 한글 표기를
# 우리 계산 코드에서 쓸 영어 키워드로 바꿔주는 사전.
# (UI 코드의 FIXED_FACILITY_TYPE에서 쓰는 이름과 동일하게 맞춤: "CCTV", "가로등", "비상벨", "파출소", "지구대", "경찰서")
TYPE_NORMALIZE_MAP = {
    "CCTV": "cctv",
    "가로등": "streetlight",
    "비상벨": "bell",
    "파출소": "police",
    "지구대": "police",   # 파출소/지구대는 성격이 비슷해서 같은 그룹(police)으로 묶음
    "경찰서": "police",
}


# ============================================================
# 2. 정규화 기준값 (CAP)
# ============================================================
# 의미: "이 숫자 이상이면 만점(1.0)으로 본다"는 기준선.
# 예) cctv 기준값이 30이면, 반경 1km 안에 카메라 30대 이상이면 cctv_norm = 1.0
#     15대면 15/30 = 0.5
# 이 숫자는 확정값이 아니라 프로토타입용 임시 기준이고, 실제 데이터 분포를 보고 나중에 조정하면 됨.
CAPS = {
    "cctv": 30,
    "streetlight": 60,
    "bell": 10,
    "police": 2,
}


# ============================================================
# 3. 가중치 (WEIGHTS)
# ============================================================
# 안전점수 공식에서 각 시설이 점수에 얼마나 영향을 주는지 정하는 값.
# 모두 양수인 이유: 지금은 "있으면 좋은" 시설들만 다루고 있어서 (CCTV, 가로등, 비상벨, 경찰시설)
# 나중에 범죄/사고 데이터가 들어오면 음수 가중치(감점)로 따로 추가하면 됨.
WEIGHTS = {
    "cctv": 20,
    "streetlight": 15,
    "bell": 10,
    "police": 15,
}


# ============================================================
# 4. 입력 데이터 검증 및 정리
# ============================================================
def validate_facilities(df: pd.DataFrame) -> pd.DataFrame:
    """
    [목적]
    데이터 파트가 준 시설 CSV를 안전지수 계산이 가능한 깨끗한 상태로 만든다.

    [입력]
    df: "위도", "경도", "시설유형" 컬럼이 들어있는 원본 DataFrame
        ("주소", "count"는 있으면 쓰고 없으면 자동으로 채움)

    [하는 일]
    1) 필수 컬럼(위도, 경도, 시설유형)이 있는지 확인 -> 없으면 에러를 띄워서 바로 알아챌 수 있게 함
    2) 위도/경도를 숫자로 변환 (혹시 문자로 들어왔을 경우 대비)
    3) count 컬럼이 없으면 전부 1로 채움 (가로등/비상벨/경찰서처럼 "한 행 = 시설 1개"인 경우)
    4) 위도/경도가 비어있는 행은 제거 (좌표 없으면 거리 계산 자체가 불가능하기 때문)
    5) 시설유형 이름을 cctv / streetlight / bell / police 로 통일

    [출력]
    계산 가능한 상태로 정리된 DataFrame
    """

    # 필수 컬럼 체크: 이게 없으면 애초에 계산을 시작할 수 없으므로 바로 에러로 알려줌
    required_cols = [LAT_COL, LNG_COL, TYPE_COL]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"필수 컬럼이 없습니다: {col} (데이터 파트에 컬럼명 확인 요청 필요)")

    df = df.copy()  # 원본 보호용 복사본

    # 위도/경도를 숫자형으로 변환. 변환 안 되는 값(문자 등)은 NaN으로 바뀜 (errors="coerce")
    df[LAT_COL] = pd.to_numeric(df[LAT_COL], errors="coerce")
    df[LNG_COL] = pd.to_numeric(df[LNG_COL], errors="coerce")

    # count 컬럼이 아예 없는 CSV라면(예: 가로등 원본) 기본값 1을 채움
    if COUNT_COL not in df.columns:
        df[COUNT_COL] = 1

    # count도 숫자로 변환하고, 빈 값이면 1로 채움 (시설 1개로 취급)
    df[COUNT_COL] = pd.to_numeric(df[COUNT_COL], errors="coerce")
    df[COUNT_COL] = df[COUNT_COL].fillna(1)

    # 위도/경도가 없는 행은 지도에 찍을 수도, 거리 계산도 할 수 없으므로 제거
    df = df.dropna(subset=[LAT_COL, LNG_COL])

    # "CCTV", "가로등" 같은 한글 표기를 "cctv", "streetlight" 같은 내부 키워드로 통일
    # 매핑에 없는 값은 원래 값 그대로 둠 (나중에 새로운 시설유형이 추가돼도 에러 안 나게)
    df[TYPE_COL] = df[TYPE_COL].map(TYPE_NORMALIZE_MAP).fillna(df[TYPE_COL])

    return df


# ============================================================
# 5. 평가 지점(격자) 생성
# ============================================================
def create_grid_from_facilities(df: pd.DataFrame, grid_step: float = 0.003) -> pd.DataFrame:
    """
    [목적]
    안전점수를 계산할 기준 위치(격자점)들을 만든다.
    안전지수는 시설 하나하나에 매기는 게 아니라 "지역의 각 위치"에 매기는 것이기 때문에
    먼저 점수를 매길 좌표 목록이 필요함.

    [입력]
    df: 위도/경도가 정리된 시설 DataFrame (이 데이터의 좌표 범위를 기준으로 격자를 만듦)
    grid_step: 격자 간격 (위도/경도 단위). 0.003 정도가 대략 300m 안팎 간격이라 테스트용으로 적당함.
               숫자가 작을수록 촘촘해지지만 계산 시간이 늘어남.

    [출력]
    grid_id, 위도, 경도 컬럼을 가진 DataFrame (각 행 = 평가할 위치 하나)
    """

    # 시설들이 분포한 좌표 범위(최소/최대)를 구해서 그 범위 안에서만 격자를 만듦
    lat_min, lat_max = df[LAT_COL].min(), df[LAT_COL].max()
    lng_min, lng_max = df[LNG_COL].min(), df[LNG_COL].max()

    grid_points = []
    grid_id = 0

    # np.arange로 grid_step 간격의 위도/경도 후보값 목록을 만듦
    lat_values = np.arange(lat_min, lat_max, grid_step)
    lng_values = np.arange(lng_min, lng_max, grid_step)

    # 위도 x 경도 모든 조합 = 격자점 하나하나
    for lat in lat_values:
        for lng in lng_values:
            grid_points.append({
                "grid_id": f"grid_{grid_id}",
                LAT_COL: lat,
                LNG_COL: lng,
            })
            grid_id += 1

    return pd.DataFrame(grid_points)


# ============================================================
# 6. 두 좌표 사이 거리 계산 (Haversine 공식)
# ============================================================
def haversine(lat1, lng1, lat2, lng2):
    """
    [목적]
    위도/경도로 표현된 두 지점 사이의 실제 거리를 km 단위로 계산한다.
    지구는 평면이 아니라 둥글기 때문에 단순 좌표 차이로는 거리를 정확히 잴 수 없어서
    Haversine이라는 공식을 사용함 (지리 데이터에서 거리 계산할 때 표준적으로 쓰는 방식).

    [입력]
    lat1, lng1: 기준점 위도/경도
    lat2, lng2: 비교할 지점 위도/경도

    [출력]
    두 지점 사이 거리 (km)
    """
    R = 6371  # 지구 반지름 (km), 고정값

    # 도(degree) 단위를 라디안(radian) 단위로 변환 (삼각함수 계산을 위해 필요)
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


# ============================================================
# 7. 특정 지점 기준, 특정 시설유형의 반경 내 개수(count 합) 계산
# ============================================================
def count_one_type_nearby(
    target_lat: float,
    target_lng: float,
    facilities: pd.DataFrame,
    facility_type: str,
    radius_km: float = 1.0,
) -> float:
    """
    [목적]
    기준 위치(target_lat, target_lng) 하나를 받아서,
    그 위치 주변 radius_km(기본 1km) 안에 있는 특정 시설유형(facility_type)의
    count 합계를 구한다.

    예) count_one_type_nearby(37.5485, 127.1030, facilities, "cctv", 1.0)
        -> 이 위치 1km 안에 있는 CCTV 카메라 총 대수

    [입력]
    target_lat, target_lng: 기준 위치 좌표
    facilities: 검증 완료된 시설 DataFrame
    facility_type: "cctv" / "streetlight" / "bell" / "police" 중 하나
    radius_km: 반경 (기본 1km)

    [출력]
    해당 시설유형의 반경 내 count 합계 (숫자)
    """

    # 전체 시설 중에서 해당 시설유형만 필터링
    target_df = facilities[facilities[TYPE_COL] == facility_type]

    # 해당 시설유형 데이터가 아예 없으면(아직 데이터 파트가 안 줬으면) 0으로 처리
    if target_df.empty:
        return 0

    total = 0
    # 필터링된 시설들을 하나씩 돌면서 기준점과의 거리를 재고, 반경 안에 있으면 count를 더함
    for _, row in target_df.iterrows():
        distance = haversine(target_lat, target_lng, row[LAT_COL], row[LNG_COL])
        if distance <= radius_km:
            total += row[COUNT_COL]

    return total


# ============================================================
# 8. 모든 격자점에 반경 집계 적용
# ============================================================
def add_nearby_counts(grid: pd.DataFrame, facilities: pd.DataFrame, radius_km: float = 1.0) -> pd.DataFrame:
    """
    [목적]
    격자점 전체에 대해 시설유형별로 "반경 1km 안 개수" 컬럼을 만든다.
    (예: cctv_count_1km, streetlight_count_1km, bell_count_1km, police_count_1km)

    [입력]
    grid: create_grid_from_facilities()로 만든 격자점 DataFrame
    facilities: 검증 완료된 시설 DataFrame
    radius_km: 반경 (기본 1km)

    [출력]
    시설유형별 반경 내 개수 컬럼이 추가된 grid DataFrame
    """
    grid = grid.copy()

    # WEIGHTS에 정의된 시설유형들(cctv, streetlight, bell, police)에 대해 각각 계산
    for facility_type in WEIGHTS.keys():
        col_name = f"{facility_type}_count_1km"

        # grid의 각 행(=각 격자점)마다 count_one_type_nearby를 호출해서 값을 채움
        grid[col_name] = grid.apply(
            lambda row: count_one_type_nearby(
                row[LAT_COL], row[LNG_COL], facilities, facility_type, radius_km=radius_km
            ),
            axis=1,
        )

    return grid


# ============================================================
# 9. 정규화 (0~1로 변환)
# ============================================================
def add_normalized_scores(grid: pd.DataFrame) -> pd.DataFrame:
    """
    [목적]
    시설 개수는 단위가 제각각이라 (CCTV는 수십 대, 경찰서는 1~2개) 그대로 더하면
    숫자가 큰 시설(CCTV)이 점수를 거의 독점해버림.
    그래서 CAPS 기준값으로 나눠서 모든 시설을 0~1 사이 값으로 맞춘다.

    [입력]
    grid: add_nearby_counts()를 거친 DataFrame (예: cctv_count_1km 등이 있는 상태)

    [출력]
    각 시설유형별 정규화 컬럼(예: cctv_norm)이 추가된 DataFrame
    """
    grid = grid.copy()

    for facility_type, cap in CAPS.items():
        count_col = f"{facility_type}_count_1km"
        norm_col = f"{facility_type}_norm"

        # 혹시 해당 시설 데이터가 아직 없어서 컬럼 자체가 없으면 0으로 만들어둠 (에러 방지)
        if count_col not in grid.columns:
            grid[count_col] = 0

        # count를 cap으로 나누고, 1을 넘지 않도록 clip(최댓값 제한)
        grid[norm_col] = (grid[count_col] / cap).clip(0, 1)

    return grid


# ============================================================
# 10. 안전점수 계산
# ============================================================
def add_safety_score(grid: pd.DataFrame) -> pd.DataFrame:
    """
    [목적]
    정규화된 시설 점수에 가중치를 곱해서 최종 안전점수(0~100)를 만든다.

    [공식]
    안전점수 = 50 (기본 점수)
             + cctv_norm * cctv 가중치
             + streetlight_norm * 가로등 가중치
             + bell_norm * 비상벨 가중치
             + police_norm * 경찰시설 가중치

    50점에서 시작하는 이유: 아무 시설 정보가 없을 때 점수가 무조건 0이 되면
    "위험하다"는 잘못된 인상을 주기 때문에, 중립값(보통)으로 시작함.

    [입력]
    grid: add_normalized_scores()를 거친 DataFrame

    [출력]
    safety_score 컬럼(0~100)이 추가된 DataFrame
    """
    grid = grid.copy()
    grid["safety_score"] = 50  # 기본 점수(중립)에서 시작

    for facility_type, weight in WEIGHTS.items():
        norm_col = f"{facility_type}_norm"
        if norm_col not in grid.columns:
            grid[norm_col] = 0
        grid["safety_score"] += grid[norm_col] * weight

    # 혹시 계산상 100 넘거나 0 밑으로 내려가는 걸 방지 (clip으로 범위 고정)
    grid["safety_score"] = grid["safety_score"].clip(0, 100)

    return grid


# ============================================================
# 11. A~E 등급 변환
# ============================================================
def score_to_grade(score: float) -> str:
    """
    [목적]
    숫자 점수만으로는 직관적으로 와닿지 않으므로, 등급(A~E)으로 바꿔서
    지도에서 색깔로 바로 표현할 수 있게 한다.

    점수 80 이상 -> A (매우 안전)
    점수 65 이상 -> B (안전)
    점수 50 이상 -> C (보통)
    점수 35 이상 -> D (주의)
    그 미만      -> E (위험)
    """
    if score >= 80:
        return "A"
    elif score >= 65:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 35:
        return "D"
    else:
        return "E"


def add_grade(grid: pd.DataFrame) -> pd.DataFrame:
    """safety_score 컬럼을 기준으로 grade 컬럼을 추가하는 함수"""
    grid = grid.copy()
    grid["grade"] = grid["safety_score"].apply(score_to_grade)
    return grid


# ============================================================
# 12. 전체 파이프라인을 한 번에 실행하는 함수
# ============================================================
def build_safety_grid(
    facilities: pd.DataFrame,
    grid_step: float = 0.003,
    radius_km: float = 1.0,
) -> pd.DataFrame:
    """
    [목적]
    위에서 만든 모든 단계(검증 -> 격자생성 -> 반경집계 -> 정규화 -> 점수화 -> 등급화)를
    순서대로 한 번에 실행해주는 함수. 실제로 사용할 때는 이 함수 하나만 호출하면 됨.

    [입력]
    facilities: 데이터 파트가 준 원본 시설 DataFrame (위도, 경도, 시설유형, [주소], [count])
    grid_step: 격자 간격
    radius_km: 집계 반경

    [출력]
    grid_id, 위도, 경도, 시설별 개수/정규화값, safety_score, grade가 모두 담긴 최종 DataFrame
    """
    facilities = validate_facilities(facilities)
    grid = create_grid_from_facilities(facilities, grid_step=grid_step)
    grid = add_nearby_counts(grid, facilities, radius_km=radius_km)
    grid = add_normalized_scores(grid)
    grid = add_safety_score(grid)
    grid = add_grade(grid)
    return grid


# ============================================================
# 13. 실행부 (이 파일을 직접 실행했을 때 동작하는 부분)
# ============================================================
if __name__ == "__main__":
    # ---- 데이터 파트가 통합 CSV를 준 "이후"에는 이 경로만 바꿔서 그대로 실행하면 됨 ----
    INPUT_PATH = "facilities_clean.csv"   # 위도, 경도, 시설유형, [주소], [count] 컬럼이 있어야 함
    OUTPUT_PATH = "safety_grid.csv"       # UI/경로 담당에게 넘길 최종 산출물

    facilities = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

    safety_grid = build_safety_grid(
        facilities,
        grid_step=0.003,
        radius_km=1.0,
    )

    safety_grid.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print("안전지수 산출 완료:", OUTPUT_PATH)
    print(safety_grid.head())


# ============================================================
# [참고] 지금 당장 CCTV 데이터만으로 테스트하고 싶다면 (데이터 파트 결과물 오기 전)
# ============================================================
# 아래처럼 CCTV 원본을 임시로 표준 형식(위도/경도/시설유형/주소/count)으로 바꿔서
# build_safety_grid()에 그대로 넣어보면 코드가 정상 작동하는지 미리 확인할 수 있음.
#
# import pandas as pd
#
# cctv_raw = pd.read_csv(
#     "/kaggle/input/datasets/shinyoug/map-info/CCTV_.csv",
#     encoding="cp949"
# )
#
# facilities_test = pd.DataFrame({
#     "위도": cctv_raw["WGS84위도"],
#     "경도": cctv_raw["WGS84경도"],
#     "시설유형": "CCTV",
#     "주소": cctv_raw["소재지도로명주소"],
#     "count": cctv_raw["카메라대수"],   # CCTV는 카메라대수를 count로 사용
# })
#
# safety_grid_test = build_safety_grid(facilities_test, grid_step=0.003, radius_km=1.0)
# display(safety_grid_test.head())
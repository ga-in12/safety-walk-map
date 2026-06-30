"""
안전지수 산출 스켈레톤 코드

이 파일의 목적:
- 데이터 파트가 아직 최종 데이터를 완성하지 않았어도
  안전지수 계산 흐름을 미리 만들어두기 위한 코드입니다.

전체 흐름:
1. 시설 데이터 불러오기
2. 위도/경도/시설유형/count 컬럼 정리
3. 광진구 범위에 격자점 생성
4. 각 격자점 기준 반경 1km 안 시설 개수 계산
5. 시설 개수를 0~1 사이 값으로 정규화
6. 가중치를 적용해 safety_score 계산
7. safety_score를 A~E 등급으로 변환
8. data/processed/safety_grid.csv 저장

나중에 데이터 파트가 facilities_clean.csv를 주면
그 파일만 data/processed 폴더에 넣고 실행하면 됩니다.
"""

from pathlib import Path
import math
import numpy as np
import pandas as pd


# ============================================================
# 0. 경로 설정
# ============================================================

# 현재 파일 위치: scripts/safety_index_skeleton.py
# 프로젝트 루트: SAFETY-WALK-MAP
PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# 데이터 파트가 나중에 만들어줄 최종 통합 시설 데이터
FACILITIES_CLEAN_PATH = PROCESSED_DIR / "facilities_clean.csv"

# 안전지수 파트가 최종적으로 만들어낼 결과 파일
OUTPUT_PATH = PROCESSED_DIR / "safety_grid.csv"


# ============================================================
# 1. 표준 컬럼명 설정
# ============================================================

"""
UI 담당 코드에서 쓰는 컬럼명과 맞추기 위해
한글 컬럼명을 기준으로 사용합니다.

필수 컬럼:
- 위도
- 경도
- 시설유형

추가 컬럼:
- 주소
- count

count는 개수 또는 영향량입니다.
예:
- CCTV: 카메라대수
- 가로등: 1
- 비상벨: 1
- 경찰서/파출소/지구대: 1
"""

LAT_COL = "위도"
LNG_COL = "경도"
TYPE_COL = "시설유형"
ADDRESS_COL = "주소"
COUNT_COL = "count"


# ============================================================
# 2. 시설유형 이름 통일
# ============================================================

"""
데이터마다 시설 이름이 다르게 들어올 수 있습니다.

예:
- CCTV, cctv, 씨씨티비
- 파출소, 지구대, 경찰서

계산할 때는 이름이 통일되어 있어야 하므로
아래 딕셔너리를 이용해서 내부 계산용 이름으로 바꿉니다.
"""

TYPE_NORMALIZE_MAP = {
    "CCTV": "cctv",
    "cctv": "cctv",
    "씨씨티비": "cctv",

    "가로등": "streetlight",
    "streetlight": "streetlight",

    "비상벨": "bell",
    "안전비상벨": "bell",
    "bell": "bell",

    "파출소": "police",
    "지구대": "police",
    "경찰서": "police",
    "police": "police",
}


# ============================================================
# 3. 안전지수 계산 기준값과 가중치
# ============================================================

"""
CAPS:
- 시설 개수를 0~1 사이로 바꾸기 위한 기준값입니다.

예:
CCTV 기준값이 30이면,
반경 1km 안 CCTV가 15대일 때 15 / 30 = 0.5
반경 1km 안 CCTV가 30대 이상이면 1.0으로 처리합니다.

WEIGHTS:
- 안전점수에 얼마나 반영할지 정하는 값입니다.

현재는 프로토타입 기준입니다.
나중에 데이터 분포나 교수님 피드백에 따라 조정하면 됩니다.
"""

CAPS = {
    "cctv": 30,
    "streetlight": 60,
    "bell": 10,
    "police": 2,
}

WEIGHTS = {
    "cctv": 20,
    "streetlight": 15,
    "bell": 10,
    "police": 15,
}


# ============================================================
# 4. 데이터 불러오기
# ============================================================

def load_facilities() -> pd.DataFrame:
    """
    시설 데이터를 불러오는 함수입니다.

    1순위:
    - data/processed/facilities_clean.csv
    - 데이터 파트가 최종적으로 만들어줄 통합 CSV입니다.

    2순위:
    - 아직 최종 데이터가 없으면 에러를 내지 않고
      테스트용 더미 데이터를 만들어서 코드 흐름만 확인합니다.
    """

    if FACILITIES_CLEAN_PATH.exists():
        print(f"[INFO] 최종 통합 시설 데이터 사용: {FACILITIES_CLEAN_PATH}")
        return pd.read_csv(FACILITIES_CLEAN_PATH, encoding="utf-8-sig")

    print("[WARNING] facilities_clean.csv가 아직 없습니다.")
    print("[WARNING] 테스트용 더미 데이터로 안전지수 계산 흐름만 확인합니다.")

    dummy_data = [
        {
            "위도": 37.5400,
            "경도": 127.0830,
            "시설유형": "CCTV",
            "주소": "테스트 주소 1",
            "count": 3,
        },
        {
            "위도": 37.5420,
            "경도": 127.0810,
            "시설유형": "가로등",
            "주소": "테스트 주소 2",
            "count": 1,
        },
        {
            "위도": 37.5370,
            "경도": 127.0850,
            "시설유형": "비상벨",
            "주소": "테스트 주소 3",
            "count": 1,
        },
        {
            "위도": 37.5390,
            "경도": 127.0795,
            "시설유형": "파출소",
            "주소": "테스트 주소 4",
            "count": 1,
        },
    ]

    return pd.DataFrame(dummy_data)


# ============================================================
# 5. 데이터 검증 및 정리
# ============================================================

def validate_facilities(df: pd.DataFrame) -> pd.DataFrame:
    """
    시설 데이터를 안전지수 계산에 사용할 수 있는 상태로 정리합니다.

    하는 일:
    1. 필수 컬럼 존재 여부 확인
    2. 위도/경도를 숫자형으로 변환
    3. count 컬럼이 없으면 기본값 1 생성
    4. 위도/경도가 없는 행 제거
    5. 시설유형 이름 통일
    """

    required_cols = [LAT_COL, LNG_COL, TYPE_COL]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"필수 컬럼이 없습니다: {col}")

    df = df.copy()

    # 위도/경도는 거리 계산에 쓰이므로 반드시 숫자여야 합니다.
    df[LAT_COL] = pd.to_numeric(df[LAT_COL], errors="coerce")
    df[LNG_COL] = pd.to_numeric(df[LNG_COL], errors="coerce")

    # count가 없으면 한 행을 시설 1개로 봅니다.
    if COUNT_COL not in df.columns:
        df[COUNT_COL] = 1

    df[COUNT_COL] = pd.to_numeric(df[COUNT_COL], errors="coerce")
    df[COUNT_COL] = df[COUNT_COL].fillna(1)

    # 위도/경도가 없으면 반경 계산이 불가능하므로 제거합니다.
    before_count = len(df)
    df = df.dropna(subset=[LAT_COL, LNG_COL])
    after_count = len(df)

    print(f"[INFO] 위도/경도 결측 제거: {before_count}행 -> {after_count}행")

    # 시설유형 이름 통일
    df[TYPE_COL] = df[TYPE_COL].map(TYPE_NORMALIZE_MAP).fillna(df[TYPE_COL])

    print("[INFO] 시설유형별 데이터 개수")
    print(df[TYPE_COL].value_counts())

    return df


# ============================================================
# 6. 격자점 생성
# ============================================================

def create_grid_from_facilities(df: pd.DataFrame, grid_step: float = 0.003) -> pd.DataFrame:
    """
    시설 데이터의 위도/경도 범위를 기준으로 격자점을 생성합니다.

    격자점이란?
    - 안전점수를 계산할 기준 위치입니다.
    - 지도 전체를 일정 간격의 점들로 나눈다고 생각하면 됩니다.

    grid_step:
    - 위도/경도 간격입니다.
    - 0.003은 테스트용입니다.
    - 값이 작을수록 더 촘촘한 지도가 되지만 계산 시간이 늘어납니다.
    """

    lat_min = df[LAT_COL].min()
    lat_max = df[LAT_COL].max()
    lng_min = df[LNG_COL].min()
    lng_max = df[LNG_COL].max()

    grid_points = []
    grid_id = 0

    lat_values = np.arange(lat_min, lat_max, grid_step)
    lng_values = np.arange(lng_min, lng_max, grid_step)

    for lat in lat_values:
        for lng in lng_values:
            grid_points.append(
                {
                    "grid_id": f"grid_{grid_id}",
                    LAT_COL: lat,
                    LNG_COL: lng,
                }
            )
            grid_id += 1

    grid = pd.DataFrame(grid_points)

    print(f"[INFO] 생성된 격자점 수: {len(grid)}개")

    return grid


# ============================================================
# 7. 거리 계산 함수
# ============================================================

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    두 좌표 사이 거리를 km 단위로 계산합니다.

    왜 필요한가?
    - '반경 1km 안에 시설이 있는지' 판단하려면
      기준점과 시설점 사이의 거리를 알아야 하기 때문입니다.
    """

    R = 6371  # 지구 반지름, 단위 km

    lat1 = math.radians(lat1)
    lng1 = math.radians(lng1)
    lat2 = math.radians(lat2)
    lng2 = math.radians(lng2)

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))

    return R * c


# ============================================================
# 8. 반경 안 시설 개수 계산
# ============================================================

def count_one_type_nearby(
    target_lat: float,
    target_lng: float,
    facilities: pd.DataFrame,
    facility_type: str,
    radius_km: float = 1.0,
) -> float:
    """
    특정 지점 주변 radius_km 안에 있는 특정 시설유형의 count 합계를 계산합니다.

    예:
    target_lat, target_lng = 어떤 격자점 위치
    facility_type = "cctv"
    radius_km = 1.0

    의미:
    - 이 격자점 주변 1km 안에 CCTV가 총 몇 대 있는지 계산합니다.
    """

    target_df = facilities[facilities[TYPE_COL] == facility_type]

    if target_df.empty:
        return 0

    total = 0

    for _, row in target_df.iterrows():
        distance = haversine(
            target_lat,
            target_lng,
            row[LAT_COL],
            row[LNG_COL],
        )

        if distance <= radius_km:
            total += row[COUNT_COL]

    return total


def add_nearby_counts(
    grid: pd.DataFrame,
    facilities: pd.DataFrame,
    radius_km: float = 1.0,
) -> pd.DataFrame:
    """
    모든 격자점에 대해 시설유형별 반경 내 개수를 계산합니다.

    결과 예:
    - cctv_count_1km
    - streetlight_count_1km
    - bell_count_1km
    - police_count_1km
    """

    grid = grid.copy()

    for facility_type in WEIGHTS.keys():
        col_name = f"{facility_type}_count_1km"

        print(f"[INFO] {col_name} 계산 중...")

        grid[col_name] = grid.apply(
            lambda row: count_one_type_nearby(
                row[LAT_COL],
                row[LNG_COL],
                facilities,
                facility_type,
                radius_km=radius_km,
            ),
            axis=1,
        )

    return grid


# ============================================================
# 9. 정규화
# ============================================================

def add_normalized_scores(grid: pd.DataFrame) -> pd.DataFrame:
    """
    시설 개수를 0~1 사이 값으로 바꿉니다.

    이유:
    - CCTV는 30대까지 나올 수 있고,
      경찰서는 1개만 있어도 의미가 큽니다.
    - 단위가 다른 값을 그대로 더하면 CCTV 숫자가 너무 크게 작용합니다.
    - 그래서 각 시설별 기준값을 두고 0~1 사이로 변환합니다.
    """

    grid = grid.copy()

    for facility_type, cap in CAPS.items():
        count_col = f"{facility_type}_count_1km"
        norm_col = f"{facility_type}_norm"

        if count_col not in grid.columns:
            grid[count_col] = 0

        grid[norm_col] = (grid[count_col] / cap).clip(0, 1)

    return grid


# ============================================================
# 10. 안전점수 계산
# ============================================================

def add_safety_score(grid: pd.DataFrame) -> pd.DataFrame:
    """
    정규화된 시설 점수에 가중치를 적용해서 안전점수를 계산합니다.

    현재 공식:
    safety_score =
        50
        + cctv_norm * 20
        + streetlight_norm * 15
        + bell_norm * 10
        + police_norm * 15

    50점에서 시작하는 이유:
    - 아무 시설이 없다고 바로 0점으로 두면 너무 극단적입니다.
    - 기본값을 보통 수준인 50점으로 두고,
      안전시설이 많을수록 점수가 올라가게 합니다.
    """

    grid = grid.copy()

    grid["safety_score"] = 50

    for facility_type, weight in WEIGHTS.items():
        norm_col = f"{facility_type}_norm"

        if norm_col not in grid.columns:
            grid[norm_col] = 0

        grid["safety_score"] += grid[norm_col] * weight

    # 점수는 0~100 사이로 제한합니다.
    grid["safety_score"] = grid["safety_score"].clip(0, 100)

    return grid


# ============================================================
# 11. A~E 등급 변환
# ============================================================

def score_to_grade(score: float) -> str:
    """
    안전점수를 A~E 등급으로 변환합니다.

    A: 매우 안전
    B: 안전
    C: 보통
    D: 주의
    E: 위험
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
    """
    safety_score 컬럼을 기준으로 grade 컬럼을 추가합니다.
    """

    grid = grid.copy()
    grid["grade"] = grid["safety_score"].apply(score_to_grade)
    return grid


# ============================================================
# 12. 전체 파이프라인 함수
# ============================================================

def build_safety_grid(
    facilities: pd.DataFrame,
    grid_step: float = 0.003,
    radius_km: float = 1.0,
) -> pd.DataFrame:
    """
    안전지수 산출 전체 과정을 한 번에 실행하는 함수입니다.

    입력:
    - facilities: 시설 데이터
    - grid_step: 격자 간격
    - radius_km: 주변 시설을 탐색할 반경

    출력:
    - 각 격자점별 안전점수와 등급이 포함된 DataFrame
    """

    facilities = validate_facilities(facilities)

    grid = create_grid_from_facilities(
        facilities,
        grid_step=grid_step,
    )

    grid = add_nearby_counts(
        grid,
        facilities,
        radius_km=radius_km,
    )

    grid = add_normalized_scores(grid)
    grid = add_safety_score(grid)
    grid = add_grade(grid)

    return grid


# ============================================================
# 13. 실행 부분
# ============================================================

def main():
    """
    이 파일을 직접 실행했을 때 작동하는 부분입니다.

    실행 방법:
    터미널에서 아래 명령어 입력

    python scripts/safety_index_skeleton.py
    """

    # processed 폴더가 없으면 자동으로 생성합니다.
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    facilities = load_facilities()

    safety_grid = build_safety_grid(
        facilities,
        grid_step=0.003,
        radius_km=1.0,
    )

    safety_grid.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("[DONE] 안전지수 산출 완료")
    print(f"[DONE] 저장 위치: {OUTPUT_PATH}")
    print()
    print(safety_grid.head())


if __name__ == "__main__":
    main()
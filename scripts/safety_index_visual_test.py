"""
실제 광진구 안전시설 통합 CSV를 이용한 안전지수 계산 실습 코드

목표:
- data/raw/광진구_안전시설_통합.csv 파일을 사용한다.
- 기준 위치 하나를 정한다.
- 기준 위치 주변 1km 안에 있는 CCTV, 가로등, 비상벨, 경찰시설 개수를 센다.
- 임시 안전점수와 A~E 등급을 계산한다.
- 결과 CSV와 시각화 이미지를 저장한다.

중요:
- 아직 광진구 전체 격자 계산은 하지 않는다.
- 지금은 안전지수 계산 원리를 확인하기 위한 단일 기준점 실습이다.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt


# ============================================================
# 0단계. 파일 경로 설정
# ============================================================

"""
현재 VS Code 화면 기준으로 CSV는 data/raw 폴더 안에 있다.

프로젝트 구조:
SAFETY-WALK-MAP
├─ data
│  ├─ raw
│  │  └─ 광진구_안전시설_통합.csv
│  └─ processed
├─ scripts
│  └─ safety_index_visual_test.py

따라서 파일 경로는 아래처럼 작성한다.
"""

input_path = Path("data/raw/광진구_안전시설_통합.csv")

output_csv_dir = Path("data/processed")
output_img_dir = Path("outputs")

output_csv_dir.mkdir(parents=True, exist_ok=True)
output_img_dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1단계. 실제 안전시설 통합 CSV 불러오기
# ============================================================

"""
CSV 파일을 pandas로 읽어온다.

encoding="utf-8-sig":
- 한글 CSV를 읽을 때 비교적 안전한 인코딩이다.
"""

facilities = pd.read_csv(input_path, encoding="utf-8-sig")

print("\n[1단계] 실제 광진구 안전시설 데이터 불러오기")
print("데이터 크기:", facilities.shape)
print(facilities.head())


# ============================================================
# 2단계. 필요한 컬럼 확인 및 count 컬럼 만들기
# ============================================================

"""
현재 CSV에는 다음 컬럼이 있다.
- 시설명
- 시설유형
- 주소
- 위도
- 경도

안전지수 계산에는 count가 필요하다.
그런데 이 통합 CSV에는 count 컬럼이 없으므로,
일단 한 행을 시설 1개로 보고 count = 1을 부여한다.

나중에 CCTV 카메라대수를 반영하려면,
CCTV 원본 데이터에서 카메라대수 컬럼을 살려서 count로 넣으면 된다.
"""

print("\n[2단계] 컬럼 확인")
print(facilities.columns.tolist())

facilities["count"] = 1

# 위도, 경도는 거리 계산에 쓰이므로 숫자형으로 변환한다.
facilities["위도"] = pd.to_numeric(facilities["위도"], errors="coerce")
facilities["경도"] = pd.to_numeric(facilities["경도"], errors="coerce")

# 위도/경도가 비어 있는 행은 거리 계산이 불가능하므로 제거한다.
before_len = len(facilities)
facilities = facilities.dropna(subset=["위도", "경도"])
after_len = len(facilities)

print("위도/경도 결측 제거:", before_len, "->", after_len)

print("\n시설유형별 개수")
print(facilities["시설유형"].value_counts())


# ============================================================
# 3단계. 안전지수를 계산할 기준 위치 하나 정하기
# ============================================================

"""
지금은 전체 격자를 계산하지 않고,
기준 위치 하나만 잡아서 안전지수 계산 원리를 확인한다.

이 기준점은 광진구 근처 임의 좌표이다.
나중에는 이 기준점이 여러 개가 되고,
그 여러 기준점이 격자칸의 중심점 역할을 하게 된다.
"""

target_lat = 37.5400
target_lng = 127.0820

print("\n[3단계] 안전지수를 계산할 기준 위치")
print("기준 위도:", target_lat)
print("기준 경도:", target_lng)


# ============================================================
# 4단계. 기준 위치와 각 시설 사이 거리 계산
# ============================================================

"""
반경 1km 안에 있는 시설을 찾으려면,
기준 위치와 각 시설 사이의 거리를 계산해야 한다.

정확한 지구 곡면 거리 계산식도 있지만,
지금은 학습용 실습이므로 서울 근처에서 사용할 수 있는 쉬운 근사식을 쓴다.

서울 근처 기준:
- 위도 1도 차이 ≈ 111km
- 경도 1도 차이 ≈ 88.8km

거리 계산:
1. 위도 차이를 km로 바꾼다.
2. 경도 차이를 km로 바꾼다.
3. 피타고라스 방식으로 직선거리를 계산한다.
"""

facilities["위도차이_km"] = (facilities["위도"] - target_lat) * 111
facilities["경도차이_km"] = (facilities["경도"] - target_lng) * 88.8

facilities["거리_km"] = np.sqrt(
    facilities["위도차이_km"] ** 2
    + facilities["경도차이_km"] ** 2
)

print("\n[4단계] 기준 위치와 각 시설 사이 거리 계산 결과")
print(facilities[["시설명", "시설유형", "주소", "count", "거리_km"]].head())


# ============================================================
# 5단계. 반경 1km 안에 있는 시설만 추출
# ============================================================

"""
안전지수 계산에는 기준 위치 주변 1km 안의 시설만 반영한다.

거리_km <= 1 인 시설만 near_facilities에 저장한다.
"""

near_facilities = facilities[facilities["거리_km"] <= 1].copy()

print("\n[5단계] 반경 1km 안에 들어온 시설")
print("반경 1km 안 시설 수:", len(near_facilities))
print(near_facilities[["시설명", "시설유형", "주소", "count", "거리_km"]].head(20))

print("\n반경 1km 안 시설유형별 개수")
print(near_facilities["시설유형"].value_counts())


# ============================================================
# 6단계. 시설유형별 count 합계 구하기
# ============================================================

"""
반경 1km 안 시설들을 시설유형별로 묶어서 count 합계를 구한다.

예:
CCTV 20개
가로등 50개
비상벨 5개
파출소 1개
"""

count_by_type = near_facilities.groupby("시설유형")["count"].sum()

print("\n[6단계] 반경 1km 안 시설유형별 count 합계")
print(count_by_type)


# ============================================================
# 7단계. 안전점수 계산에 쓸 값 꺼내기
# ============================================================

"""
경찰시설은 파출소, 지구대, 경찰서를 합쳐서 본다.

이유:
- 모두 치안 대응과 관련된 시설이므로
  안전지수 계산에서는 하나의 police_count로 묶는 것이 단순하다.
"""

cctv_count = count_by_type.get("CCTV", 0)
streetlight_count = count_by_type.get("가로등", 0)
bell_count = count_by_type.get("비상벨", 0)

police_count = (
    count_by_type.get("파출소", 0)
    + count_by_type.get("지구대", 0)
    + count_by_type.get("경찰서", 0)
)

print("\n[7단계] 점수 계산에 사용할 시설 개수")
print("CCTV 개수:", cctv_count)
print("가로등 개수:", streetlight_count)
print("비상벨 개수:", bell_count)
print("경찰시설 개수:", police_count)


# ============================================================
# 8단계. 시설 개수를 0~1 사이 점수로 변환
# ============================================================

"""
시설마다 개수 규모가 다르다.

예:
- 가로등은 수십 개 있을 수 있음
- 경찰서는 1개만 있어도 의미 있음

그래서 시설 개수를 그대로 더하지 않고,
각 시설별 기준값으로 나누어 0~1 사이 점수로 바꾼다.

현재 기준값은 임시값이다.
나중에 전체 데이터 분포를 보고 조정할 수 있다.
"""

cctv_score = min(cctv_count / 30, 1)
streetlight_score = min(streetlight_count / 60, 1)
bell_score = min(bell_count / 10, 1)
police_score = min(police_count / 2, 1)

print("\n[8단계] 0~1 사이로 변환한 시설 점수")
print("CCTV 점수:", cctv_score)
print("가로등 점수:", streetlight_score)
print("비상벨 점수:", bell_score)
print("경찰시설 점수:", police_score)


# ============================================================
# 9단계. 안전점수 계산
# ============================================================

"""
기본점수 50점에서 시작한다.

안전시설이 많을수록 점수를 더한다.

임시 공식:
안전점수 =
50
+ CCTV 점수 * 20
+ 가로등 점수 * 15
+ 비상벨 점수 * 10
+ 경찰시설 점수 * 15
"""

safety_score = (
    50
    + cctv_score * 20
    + streetlight_score * 15
    + bell_score * 10
    + police_score * 15
)

safety_score = min(safety_score, 100)

print("\n[9단계] 최종 안전점수")
print("safety_score:", safety_score)


# ============================================================
# 10단계. A~E 등급 변환
# ============================================================

"""
점수를 사람이 보기 쉬운 등급으로 바꾼다.

A: 80점 이상
B: 65점 이상
C: 50점 이상
D: 35점 이상
E: 35점 미만
"""

if safety_score >= 80:
    grade = "A"
elif safety_score >= 65:
    grade = "B"
elif safety_score >= 50:
    grade = "C"
elif safety_score >= 35:
    grade = "D"
else:
    grade = "E"

print("\n[10단계] 안전등급")
print("grade:", grade)


# ============================================================
# 11단계. 최종 결과표 만들기
# ============================================================

"""
최종 결과를 한 줄짜리 표로 만든다.

지금은 기준 위치 하나만 계산했기 때문에 결과가 한 줄이다.
나중에 격자칸 중심점 여러 개에 대해 반복하면 safety_grid.csv가 된다.
"""

result = pd.DataFrame([
    {
        "center_lat": target_lat,
        "center_lng": target_lng,
        "search_radius_m": 1000,
        "cctv_count_1km": cctv_count,
        "streetlight_count_1km": streetlight_count,
        "bell_count_1km": bell_count,
        "police_count_1km": police_count,
        "safety_score": safety_score,
        "tile_cost": 100 - safety_score,
        "grade": grade,
    }
])

print("\n[11단계] 최종 결과표")
print(result)


# ============================================================
# 12단계. 결과 CSV 저장
# ============================================================

"""
결과표를 CSV로 저장한다.

보고서에 넣을 수 있는 산출물:
- data/processed/safety_sample_real.csv
"""

output_csv_path = output_csv_dir / "safety_sample_real.csv"

result.to_csv(output_csv_path, index=False, encoding="utf-8-sig")

print("\n[12단계] 결과 CSV 저장 완료")
print("저장 위치:", output_csv_path)


# ============================================================
# 13단계. 보고서용 시각화 이미지 만들기
# ============================================================

"""
보고서에 넣기 위한 시각화 이미지이다.

보이는 것:
- 기준 위치
- 기준 위치 반경 1km 원
- 실제 광진구 안전시설 위치
- 반경 안 시설과 반경 밖 시설의 차이

주의:
- 이 그림은 실제 배경지도 위에 그린 것은 아니다.
- 위도/경도 좌표평면 위에 시설 분포를 단순 시각화한 것이다.
- 그래도 반경 탐색 개념을 설명하기에는 충분하다.
"""

# 한글 폰트 설정
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

plt.figure(figsize=(8, 8))

# 반경 밖 시설 표시
outside_facilities = facilities[facilities["거리_km"] > 1]

plt.scatter(
    outside_facilities["경도"],
    outside_facilities["위도"],
    s=8,
    alpha=0.15,
    label="반경 밖 시설"
)

# 반경 안 시설 표시
plt.scatter(
    near_facilities["경도"],
    near_facilities["위도"],
    s=18,
    alpha=0.8,
    label="반경 1km 안 시설"
)

# 기준 위치 표시
plt.scatter(
    target_lng,
    target_lat,
    s=180,
    marker="*",
    label="기준 위치"
)

# 1km 반경 원 그리기
circle_radius_lat = 1 / 111
circle_radius_lng = 1 / 88.8

theta = np.linspace(0, 2 * np.pi, 300)

circle_lng = target_lng + circle_radius_lng * np.cos(theta)
circle_lat = target_lat + circle_radius_lat * np.sin(theta)

plt.plot(
    circle_lng,
    circle_lat,
    linestyle="--",
    linewidth=2,
    label="1km 반경"
)

plt.title("기준 위치 반경 1km 내 안전시설 분포")
plt.xlabel("경도")
plt.ylabel("위도")
plt.grid(True)
plt.legend()
plt.axis("equal")

output_img_path = output_img_dir / "safety_radius_real_data.png"

plt.savefig(output_img_path, dpi=200, bbox_inches="tight")

print("\n[13단계] 시각화 이미지 저장 완료")
print("저장 위치:", output_img_path)

plt.show()

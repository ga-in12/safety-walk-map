import pandas as pd

# 1. CCTV
cctv_seoul = pd.read_csv(
    "CCTV정보_서울특별시(추가본).csv",
    encoding="cp949"
)

cctv_guri = pd.read_csv(
    "CCTV정보_경기구리시(추가본).csv",
    encoding="cp949"
)

cctv = pd.concat([cctv_seoul, cctv_guri], ignore_index=True)

# 2. 비상벨
bell_seoul = pd.read_csv(
    "안전비상벨위치정보_서울특별시(추가본).csv",
    encoding="cp949"
)

bell_guri = pd.read_csv(
    "안전비상벨위치정보_경기구리시(추가본).csv",
    encoding="cp949"
)

bell = pd.concat([bell_seoul, bell_guri], ignore_index=True)

# 3. 가로등
lamp = pd.read_csv(
    "서울특별시_가로등_위치_정보__추가본_(UTF-8).csv"
)

# 4. 경찰서/파출소
police = pd.read_csv(
    "장안1파출소(추가본).csv",
    skiprows=1
)

# 5. 저장
cctv.to_csv("추가본_CCTV.csv", index=False, encoding="utf-8-sig")
bell.to_csv("추가본_비상벨.csv", index=False, encoding="utf-8-sig")
lamp.to_csv("추가본_가로등.csv", index=False, encoding="utf-8-sig")
police.to_csv("추가본_경찰서파출소.csv", index=False, encoding="utf-8-sig")


print("\n=== CCTV ===")
print(cctv.columns.tolist())

print("\n=== 비상벨 ===")
print(bell.columns.tolist())

print("\n=== 가로등 ===")
print(lamp.columns.tolist())

print("\n=== 경찰서/파출소 ===")
print(police.columns.tolist())

# 6. 통합본

# CCTV
cctv_final = pd.DataFrame({
    "시설명": cctv["관리번호"].astype(str),
    "시설유형": "CCTV",
    "주소": cctv["소재지도로명주소"],
    "위도": cctv["WGS84위도"],
    "경도": cctv["WGS84경도"]
})

# 비상벨
bell_final = pd.DataFrame({
    "시설명": bell["안전비상벨관리번호"].astype(str),
    "시설유형": "안전비상벨",
    "주소": bell["소재지도로명주소"],
    "위도": bell["WGS84위도"],
    "경도": bell["WGS84경도"]
})

# 가로등
lamp_final = pd.DataFrame({
    "시설명": lamp["관리번호"].astype(str),
    "시설유형": "가로등",
    "주소": "",
    "위도": lamp["위도"],
    "경도": lamp["경도"]
})

# 경찰서/파출소
police_final = pd.DataFrame({
    "시설명": police["관서명"].astype(str),
    "시설유형": "경찰서/파출소",
    "주소": police["주소"],
    "위도": police["위도"],
    "경도": police["경도"]
})

# 합치기
final_df = pd.concat(
    [cctv_final, bell_final, lamp_final, police_final],
    ignore_index=True
)

# 광진구 포괄 네모칸 범위

MIN_LON = 127.05621791080974
MAX_LON = 127.11522557604522

MIN_LAT = 37.522513785515486
MAX_LAT = 37.57376442088234

final_df = final_df[
    (final_df["위도"] >= MIN_LAT) &
    (final_df["위도"] <= MAX_LAT) &
    (final_df["경도"] >= MIN_LON) &
    (final_df["경도"] <= MAX_LON)
]

final_df.to_csv(
    "추가본_v2_광진구필터.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\n통합 완료!")
print(final_df.head())
print(f"\n총 {len(final_df)}개 시설 저장")

print(final_df.isnull().sum())
print(final_df.duplicated().sum())

print(police_final)


# 가로등 데이터 "주소": ""  비어있는 행들 주소 컬럼 빈칸 데이터

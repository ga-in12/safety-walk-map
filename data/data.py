import pandas as pd

# CCTV 파일 읽기
cctv = pd.read_csv("CCTV정보_서울광진구_UTF8.csv")

# 필요한 컬럼만 추출
cctv_new = pd.DataFrame({
    "시설명": "CCTV",
    "시설유형": "CCTV",
    "주소": cctv["소재지도로명주소"],
    "위도": cctv["WGS84위도"],
    "경도": cctv["WGS84경도"]
})

# 결과 확인
print(cctv_new.head())


# 비상벨 파일 읽기
bell = pd.read_csv("안전비상벨위치정보_서울광진구_UTF8.csv")

# 필요한 컬럼만 추출
bell_new = pd.DataFrame({
    "시설명": "비상벨",
    "시설유형": "비상벨",
    "주소": bell["소재지도로명주소"],
    "위도": bell["WGS84위도"],
    "경도": bell["WGS84경도"]
})

# 결과 확인
print("\n=== 비상벨 ===")
print(bell_new.head())


# 가로등 파일 읽기
lamp = pd.read_csv("가로등위치정보_서울광진구_UTF8.csv")

# 필요한 컬럼만 추출
lamp_new = pd.DataFrame({
    "시설명": "가로등",
    "시설유형": "가로등",
    "주소": "",
    "위도": lamp["위도"],
    "경도": lamp["경도"]
})

# 결과 확인
print("\n=== 가로등 ===")
print(lamp_new.head())


# 경찰서/파출소 파일 읽기
police = pd.read_csv("경찰서지구대파출소_UTF8.csv")

# 필요한 컬럼만 추출
police.columns = ['시설명', '시설유형', '주소', '위도', '경도']

# 결과 확인
print("=== 경찰서/파출소 ===")
print(police.head())


all_data = pd.concat([
    cctv_new,
    bell_new,
    lamp_new,
    police
], ignore_index=True)

print(all_data.head())
print(len(all_data))

print(all_data.tail())


all_data = all_data.drop_duplicates()

all_data.to_csv(
    "광진구_안전시설_통합.csv",
    index=False,
    encoding="utf-8-sig"
)

print(all_data.shape)
print("중복 제거 후 통합 파일 저장 완료!")

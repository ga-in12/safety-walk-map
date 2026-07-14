import pandas as pd

# Ver1 통합 데이터 제거된 중복 2건 위치 확인 코드

cctv = pd.read_csv("CCTV정보.csv")
bell = pd.read_csv("안전비상벨위치정보.csv")
lamp = pd.read_csv("가로등위치정보.csv")
police = pd.read_csv("경찰서파출소정보.csv")

cctv_new = pd.DataFrame({
    "시설명": "CCTV",
    "시설유형": "CCTV",
    "주소": cctv["소재지도로명주소"],
    "위도": cctv["WGS84위도"],
    "경도": cctv["WGS84경도"]
})

bell_new = pd.DataFrame({
    "시설명": "비상벨",
    "시설유형": "비상벨",
    "주소": bell["소재지도로명주소"],
    "위도": bell["WGS84위도"],
    "경도": bell["WGS84경도"]
})

lamp_new = pd.DataFrame({
    "시설명": "가로등",
    "시설유형": "가로등",
    "주소": "",
    "위도": lamp["위도"],
    "경도": lamp["경도"]
})

police.columns = ["시설명", "시설유형", "주소", "위도", "경도"]

all_data = pd.concat(
    [cctv_new, bell_new, lamp_new, police],
    ignore_index=True
)

dup = all_data[all_data.duplicated(keep=False)]

print("중복 개수:", all_data.duplicated().sum())
print("\n중복 데이터:")
print(dup)
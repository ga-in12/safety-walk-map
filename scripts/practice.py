#단일점으로 1km내의 시설물들 세고, 안전지수 계산하기 

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from haversine import haversine

#경로 설정 
input_path = Path("data/raw/광진구_안전시설_통합.csv")


#데이터 불러오기
facilites_data = pd.read_csv(input_path, encoding = 'utf-8-sig')


#데이터 형태
'''
시설명  시설유형                          주소        위도         경도
0  CCTV  CCTV    서울특별시 광진구 광장로3길 22 (광장동)  37.54850  127.10300
1  CCTV  CCTV    서울특별시 광진구 아차산로 540 (광장동)  37.54244  127.10147
2  CCTV  CCTV  서울특별시 광진구 아차산로78길 53 (광장동)  37.55144  127.10983
3  CCTV  CCTV    서울특별시 광진구 아차산로 636 (광장동)  37.54891  127.10899
4  CCTV  CCTV    서울특별시 광진구 천호대로 809 (광장동)  37.54587  127.10359
'''


#단일점 설정
target_lat = 37.5400
target_lng = 127.0820

#단일점을 기준으로 500m 구역 검사 -> 원래 1km였는데 광진구는 면적이 좁으니까 500m로 계산
'''
[발상 아이디어]
1. 모든 시설에 대해 기준점과의 거리 게산 -> distance_km 컬럼 생성
2. distance_km <= 0.5인 시설만 선택
3. 그 시설들의 종류별 개수 세기
'''

#위도/경도를 이용해서 두 지점 사이의 거리(km)를 계산하는 함수
def haversine_distance(lat1, lng1, lat2, lng2):
    #지구가 둥글기 때문에 단순 뺄셈이 아닌 하버사인 공식 사용
    #라이브러리 사용
    return haversine((lat1, lng1), (lat2, lng2), unit = 'km')

#함수를 사용해서 facilities_data에 km칼럼 추가하기
#*현재는 단일점이지만, 추후에는 격자점이 여러개이므로 함수를 짠다
def add_km_columns(target_lat, target_lng, facilites_data):
   #원본데이터가 바로 바뀌는것을 막기 위해 복사본을 만든다
    facilites_data = facilites_data.copy()

   #이미 km칼럼이 존재한다면 삭제 //km는 하나의 지점을 기준으로 만들어지는 칼럼....
    if 'km' in facilites_data.columns:
        facilites_data = facilites_data.drop('km', axis =1)

    #각 시설과 target점 사이의 거리값을 저장할 리스트
    km_list = []

    #각 시설과 target점 사이의 거리 계산하고 리스트에 저장 
    #행개수만큼 반복 //시설 하나하나 계산하기 위함..
    for i in range(len(facilites_data)):
        #i번째 행(시설)의 위도, 경도 가져오기
        facility_lat = facilites_data.iloc[i]['위도'] #iloc = 번호로 꺼내는 방법
        facility_lng = facilites_data.iloc[i]['경도']

        #해당 시설과 target점의 거리 계산
        distance = haversine_distance(target_lat, target_lng, facility_lat, facility_lng)

        #리스트에 추가 
        km_list.append(distance)
    
    #해당 target점에서 모든 시설의 거리를 계산한 리스트를 만들었다면,, km칼럼으로 추가 
    facilites_data['km'] = km_list

    #km칼럼이 추가된 데이터 반환
    return facilites_data


#일단 단일점이니까.......// 원래는 격자수만큼 반복문 돌아서 실행
facilites_km_data = add_km_columns(target_lat, target_lng, facilites_data)

#데이터 확인(km잘 추가됐는지)
print('km추가 데이터 확인')
print(facilites_km_data.head())
print('''


      ''')


#facilites_km_data를 보고, km <= 0.5인 행번호만 셀렉해서 리스트 만들기 
under_500m_index = []
for i in range(len(facilites_km_data)):  
    if facilites_km_data.iloc[i]['km'] <= 0.5:
        under_500m_index.append(i) #행번호 추가 

#1km 이내 행만 선택
under_500m_data = facilites_km_data.iloc[under_500m_index]

print('[500m 이내 시셀 데이터 확인]')
print(under_500m_data.head())
print('500m 이내 시설 개수:', len(under_500m_data))
#어떤 시설들이 몇개 존재하는지 확인 
# 500m 이내 시설유형별 개수 세기
facility_counts = under_500m_data['시설유형'].value_counts() #시설유형 칼럼만 꺼내서 값이 몇번나왔는지 카운트
print('500m 이내 시설유형별 개수')
print(facility_counts)




'''
[500m 이내 시셀 데이터 확인]
     시설명  시설유형                          주소        위도         경도        km
26  CCTV  CCTV    서울특별시 광진구 구의로1길 26 (구의동)  37.53907  127.08680  0.435668
27  CCTV  CCTV  서울특별시 광진구 아차산로53길 77 (구의동)  37.54073  127.08608  0.368775
28  CCTV  CCTV       서울특별시 광진구 자양로26길 45-7  37.54162  127.08668  0.450236
29  CCTV  CCTV  서울특별시 광진구 광나루로36길 68 (구의동)  37.54217  127.08583  0.415035
30  CCTV  CCTV   서울특별시 광진구 자양로26길 14 (구의동)  37.54181  127.08488  0.324014

500m 이내 시설 개수: 264

500m 이내 시설유형별 개수
시설유형
가로등     129
CCTV     71
비상벨      63
경찰서       1
'''



#안전지수 계산하기

safety_score =0 

#가장 쉬운 안전공식: 안전지수 = CCTV 점수 + 가로등 점수 + 비상벨 점수 + 경찰시설 점수
# 안전지수 계산하기

# 1. 시설유형별 가중치 설정
# 총합이 100점이 되도록 설정
safety_weight_dict = {
    'CCTV': 35,
    '가로등': 30,
    '비상벨': 20,
    '경찰서': 15
}

# 2. 시설유형별 만점 기준 개수
# 이 개수 이상이면 해당 시설 점수는 만점 처리
max_count_dict = {
    'CCTV': 50,
    '가로등': 100,
    '비상벨': 20,
    '경찰서': 2
}


# 3. 안전지수 계산 함수
def calculate_safety_score(facility_counts, safety_weight_dict, max_count_dict):
    safety_score = 0
    detail_score = {}

    for facility_type, weight in safety_weight_dict.items():
        # 해당 시설 개수 가져오기
        # 없으면 0개로 처리
        count = facility_counts.get(facility_type, 0)

        # 해당 시설의 만점 기준 개수 가져오기
        max_count = max_count_dict[facility_type]

        # 실제 개수를 0~1 사이 비율로 변환
        ratio = count / max_count

        # 비율이 1보다 크면 1로 고정
        ratio = min(ratio, 1)

        # 시설별 점수 계산
        type_score = ratio * weight

        # 전체 안전지수에 더하기
        safety_score += type_score

        # 확인용 상세 결과 저장
        detail_score[facility_type] = {
            '개수': count,
            '만점기준개수': max_count,
            '비율': ratio,
            '점수': type_score
        }

    return safety_score, detail_score


# 4. 안전지수 계산 실행
safety_score, detail_score = calculate_safety_score(
    facility_counts,
    safety_weight_dict,
    max_count_dict
)

print('안전지수:', safety_score)
print('시설별 상세 점수')
print(detail_score)


#안전지수를 A~E 등급으로 바꾸기

'''
최종적으로 UI담당이나 경로 담당에게 넘길 수 있는 표를 만든다. 
현재는 단일 기준점이기때문에 결과도 한줄이지만, 그 결과가 여러 줄짜리 safety_grid.csv가 된다

'''

'''
matplot같은걸로 암튼
히트맵 구현하기... <- 이건 전에 안 했음!!
그 반경은 500m이지만 히트맵은 네모형태로 표시해야해서... 
A~E등급에 맞게 지도에 색깔 표ㅕ시하고, 주변에 어떤 시설이 있는지도 표시하는 과정
'''




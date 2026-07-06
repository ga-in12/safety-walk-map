#단일점으로 1km내의 시설물들 세고, 안전지수 계산하기 

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from haversine import haversine

#경로 설정 
input_path = Path("data/raw/광진구_안전시설_통합.csv") #입력 데이터 경로
processed_dir = Path("data/processed") #처리결과저장폴더
processed_dir.mkdir(parents = True, exist_ok = True)# processed 폴더가 없으면 자동으로 생성
output_dir = Path('outputs')
output_dir.mkdir(parents = True, exist_ok = True) 



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
print(type(facility_counts))
print(facility_counts)

print('''


      ''')

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

#안전지수 점수 계산
'''
해당 격자 500m이내에 존재하는 여러 시설물들의 개수를 보고,
1. 만점 기준 개수이상이면, 만점(cctv: 35, 가로등:30, 비상벨:20, 경찰서:15)으로 계산하고,
2. 만점 기준 개수 이하면, ratio * weight
'''

def calculate_safety_score(facility_counts, safety_weight_dict, max_count_dict):
    #초기화
    safety_score = 0

    #시설물들 하나씩 순회하기(시설물 이름, 개수)
    for (facility, num) in facility_counts.items():
        #해당 시설물의 num ratio랑 weight 곱해서 safety_score에 더하기
        weight = safety_weight_dict[facility] 
        #정규화 
        max_num = max_count_dict[facility]
        ratio = num/max_num 
        if ratio >= 1:
            ratio = 1
        
        safety_score = safety_score + ratio * weight
    
 

    #완성된 점수 리턴 
    return safety_score


#함수 적용
safety_score = calculate_safety_score(facility_counts, safety_weight_dict, max_count_dict)
print('안전점수:', safety_score)





#안전지수를 A~E 등급으로 바꾸기
def convert_score_to_grade(safety_score):
    if safety_score >= 85:
        return 'A'
    elif safety_score >= 70:
        return 'B'
    elif safety_score >= 55:
        return 'C'
    elif safety_score >= 40:
        return 'D'
    else:
        return 'E'

#안전등급 계산
safety_grade = convert_score_to_grade(safety_score)
print('안전등급:', safety_grade)




'''최종적으로 UI담당이나 경로 담당에게 넘길 수 있는 표를 만든다. 
현재는 단일 기준점이기때문에 결과도 한줄이지만, 그 결과가 여러 줄짜리 safety_grid.csv가 된다
'''
result_data = pd.DataFrame(
[{
'기준위도': target_lat,
    '기준경도': target_lng,
    '반경_km': 0.5,
    'CCTV개수': facility_counts.get('CCTV', 0),
    '가로등개수': facility_counts.get('가로등', 0),
    '비상벨개수': facility_counts.get('비상벨', 0),
    '경찰서개수': facility_counts.get('경찰서', 0),
    '안전점수': safety_score,
    '안전등급': safety_grade
}] #격자가 하나라서 한 행만 만들어짐
)


#result_data를 csv로 저장
#저장할 파일 경로 설정#단일점으로 1km내의 시설물들 세고, 안전지수 계산하기 

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from haversine import haversine

#경로 설정 
input_path = Path("data/raw/광진구_안전시설_통합.csv") #입력 데이터 경로
processed_dir = Path("data/processed") #처리결과저장폴더
processed_dir.mkdir(parents = True, exist_ok = True)# processed 폴더가 없으면 자동으로 생성
output_dir = Path('outputs')
output_dir.mkdir(parents = True, exist_ok = True) 



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
print(type(facility_counts))
print(facility_counts)

print('''


      ''')

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

#안전지수 점수 계산
'''
해당 격자 500m이내에 존재하는 여러 시설물들의 개수를 보고,
1. 만점 기준 개수이상이면, 만점(cctv: 35, 가로등:30, 비상벨:20, 경찰서:15)으로 계산하고,
2. 만점 기준 개수 이하면, ratio * weight
'''

def calculate_safety_score(facility_counts, safety_weight_dict, max_count_dict):
    #초기화
    safety_score = 0

    #시설물들 하나씩 순회하기(시설물 이름, 개수)
    for (facility, num) in facility_counts.items():
        #해당 시설물의 num ratio랑 weight 곱해서 safety_score에 더하기
        weight = safety_weight_dict[facility] 
        #정규화 
        max_num = max_count_dict[facility]
        ratio = num/max_num 
        if ratio >= 1:
            ratio = 1
        
        safety_score = safety_score + ratio * weight
    
 

    #완성된 점수 리턴 
    return safety_score


#함수 적용
safety_score = calculate_safety_score(facility_counts, safety_weight_dict, max_count_dict)
print('안전점수:', safety_score)





#안전지수를 A~E 등급으로 바꾸기
def convert_score_to_grade(safety_score):
    if safety_score >= 85:
        return 'A'
    elif safety_score >= 70:
        return 'B'
    elif safety_score >= 55:
        return 'C'
    elif safety_score >= 40:
        return 'D'
    else:
        return 'E'

#안전등급 계산
safety_grade = convert_score_to_grade(safety_score)
print('안전등급:', safety_grade)




'''최종적으로 UI담당이나 경로 담당에게 넘길 수 있는 표를 만든다. 
현재는 단일 기준점이기때문에 결과도 한줄이지만, 그 결과가 여러 줄짜리 safety_grid.csv가 된다
'''
result_data = pd.DataFrame(
[{
'기준위도': target_lat,
    '기준경도': target_lng,
    '반경_km': 0.5,
    'CCTV개수': facility_counts.get('CCTV', 0),
    '가로등개수': facility_counts.get('가로등', 0),
    '비상벨개수': facility_counts.get('비상벨', 0),
    '경찰서개수': facility_counts.get('경찰서', 0),
    '안전점수': safety_score,
    '안전등급': safety_grade
}] #격자가 하나라서 한 행만 만들어짐
)


#result_data를 csv로 저장
#저장할 파일 경로 설정
result_output_path = processed_dir/'safety_single_point.csv'

#csv파일로 저장 
result_data.to_csv(result_output_path, index = False, encoding = 'utf-8-sig')








'''
히트맵 구현하기... 
A~E등급에 맞게 지도에 색깔 표ㅕ시하고, 주변에 어떤 시설이 있는지도 표시하는 과정
'''

# =========================
# 단일점 기준 히트맵 시각화
# =========================

import matplotlib.patches as patches #patches = 네모, 원, 타원 같은 “도형”을 만들 때 쓰는 도구 모음

# 한글 깨짐 방지
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


# 1. 안전등급별 색깔 설정
grade_color_dict = {
    'A': 'green',
    'B': 'yellowgreen',
    'C': 'yellow',
    'D': 'orange',
    'E': 'red'
}


# 2. 시설유형별 색깔 설정
facility_color_dict = {
    'CCTV': 'blue',
    '가로등': 'gold',
    '비상벨': 'red',
    '경찰서': 'purple'
}


# 3. 시설유형별 점 모양 설정
marker_dict = {
    'CCTV': 'o',
    '가로등': '^',
    '비상벨': 's',
    '경찰서': '*'
}

#4. 지점 정보를 가지고 haversine을 이용해 위도/경도 1도의 km거리구하기

# 위도 1도 거리 -> 약 111km
km_per_lat_degree = haversine(
    (target_lat, target_lng),
    (target_lat + 1, target_lng),
    'km'
)

# 경도 1도 거리 -> 약 88km
km_per_lng_degree = haversine(
    (target_lat, target_lng),
    (target_lat, target_lng + 1),
    'km'
)


# 5. 히트맵 네모칸 크기 설정 // 111km = 1도 -> 1km = 1/111도
# 계산 반경이 500m이므로, 화면에는 1km x 1km 네모칸으로 표시
cell_size_km = 1.0 #km

#500m를 위도/경도로 변환햇을때!(*target지점 기준..)
half_cell_lat = (cell_size_km / 2) / km_per_lat_degree  #0.5km / 111km 
half_cell_lng = (cell_size_km / 2) / km_per_lng_degree #0.5km / 88km


# 6. 500m 계산 반경을 원으로 표시하기 위한 값 -> 지점을 중심으로 한 원의 반지름 = 500m
radius_km = 0.5

radius_lat = radius_km / km_per_lat_degree #0.5km / 111km
radius_lng = radius_km / km_per_lng_degree #0.5km / 88km




# 7. 그래프 만들기
fig, ax = plt.subplots(figsize=(8, 8)) #그림판 만들기


# 8. 안전등급 네모칸 도형 만들기
# 기준점을 중심으로 네모칸을 만들고, 안전등급 색으로 칠함
'''
[기본구조]
patches.Rectangle(
    (왼쪽아래 x좌표, 왼쪽아래 y좌표),
    사각형 가로길이,
    사각형 세로길이
)
'''
heatmap_cell = patches.Rectangle(
    (target_lng - half_cell_lng, target_lat - half_cell_lat),  # 왼쪽 아래 좌표
    2 * half_cell_lng,  # 네모 가로 길이
    2 * half_cell_lat,  # 네모 세로 길이
    facecolor=grade_color_dict[safety_grade], #네모칸 안쪽 색깔
    alpha=0.3,#투명도(살짝투명) *0 = 완전투명, 1 = 완전불투명
    edgecolor='black', #테두리색깔
    linewidth=2, #테두리 두께
    label=f'안전등급 {safety_grade}'
)

#patches.Restangel(...)은 네모칸 객체를 만든 것 뿐! 
ax.add_patch(heatmap_cell) #만든 네모칸을 그림판에 붙이기




# 9. 실제 시설을 센 500m 반경 표시
# 경도/위도 축 비율 때문에 완전한 원이 아니라 타원처럼 그려짐
search_circle = patches.Ellipse(
    (target_lng, target_lat), #타원의 중심좌표(경도, 위도)
    width=2 * radius_lng, #타원의 가로 지름 = (target기준으로 경도방향 500m를 치환한 값 X 2)
    height=2 * radius_lat, #타원의 세로 지름 
    fill=False, #테두리만 그리기
    edgecolor='black', #테두리 색깔
    linestyle='--', #테두리 타입 = 점선(계산 반경을 표시하는 용도이므로..)
    linewidth=2, #테두리 두께
    label='500m 계산 반경'
)

ax.add_patch(search_circle) #ax에 또 객체 하나 덧대서 올리기




# 10. 기준점 표시(또 ax위에 덧대서..)
ax.scatter(
    target_lng,
    target_lat,
    color='black',
    s=150,
    marker='X',
    label='기준점'
)



# 11. 500m 이내 시설물 표시
for facility_type in under_500m_data['시설유형'].unique():

    one_type_data = under_500m_data[
        under_500m_data['시설유형'] == facility_type
    ]

    ax.scatter(
        one_type_data['경도'],
        one_type_data['위도'],
        s=30,
        color=facility_color_dict.get(facility_type, 'gray'),
        marker=marker_dict.get(facility_type, 'o'),
        alpha=0.7,
        label=facility_type
    )


# 12. 화면 범위 설정
# 기준점 주변 700m 정도만 보이게 설정
view_range_km = 0.7

view_lat = view_range_km / km_per_lat_degree
view_lng = view_range_km / km_per_lng_degree

ax.set_xlim(target_lng - view_lng, target_lng + view_lng)
ax.set_ylim(target_lat - view_lat, target_lat + view_lat)


# 13. 제목, 축 이름, 범례
ax.set_title(f'단일 기준점 안전 히트맵 / 점수: {safety_score:.1f}, 등급: {safety_grade}')
ax.set_xlabel('경도')
ax.set_ylabel('위도')

ax.legend(loc='upper right')
ax.grid(True)

plt.show()


#히트맵 이미지 저장
#저장 경로 설정 
output_path = output_dir/ 'single_point_heatmap.png'
#저장 #fig라는 변수에 담긴 그림을 output+path위치에 저장해라 
fig.savefig(output_path,  
            dpi = 300, #해상도
            bbox_inches = 'tight') #그림 주변의 쓸데없는 여백을 줄여서 저장

result_output_path = processed_dir/'safety_single_point.csv'

#csv파일로 저장 
result_data.to_csv(result_output_path, index = False, encoding = 'utf-8-sig')








'''
히트맵 구현하기... 
A~E등급에 맞게 지도에 색깔 표ㅕ시하고, 주변에 어떤 시설이 있는지도 표시하는 과정
'''

# =========================
# 단일점 기준 히트맵 시각화
# =========================

import matplotlib.patches as patches #patches = 네모, 원, 타원 같은 “도형”을 만들 때 쓰는 도구 모음

# 한글 깨짐 방지
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


# 1. 안전등급별 색깔 설정
grade_color_dict = {
    'A': 'green',
    'B': 'yellowgreen',
    'C': 'yellow',
    'D': 'orange',
    'E': 'red'
}


# 2. 시설유형별 색깔 설정
facility_color_dict = {
    'CCTV': 'blue',
    '가로등': 'gold',
    '비상벨': 'red',
    '경찰서': 'purple'
}


# 3. 시설유형별 점 모양 설정
marker_dict = {
    'CCTV': 'o',
    '가로등': '^',
    '비상벨': 's',
    '경찰서': '*'
}

#4. 지점 정보를 가지고 haversine을 이용해 위도/경도 1도의 km거리구하기

# 위도 1도 거리 -> 약 111km
km_per_lat_degree = haversine(
    (target_lat, target_lng),
    (target_lat + 1, target_lng),
    'km'
)

# 경도 1도 거리 -> 약 88km
km_per_lng_degree = haversine(
    (target_lat, target_lng),
    (target_lat, target_lng + 1),
    'km'
)


# 5. 히트맵 네모칸 크기 설정 // 111km = 1도 -> 1km = 1/111도
# 계산 반경이 500m이므로, 화면에는 1km x 1km 네모칸으로 표시
cell_size_km = 1.0 #km

#500m를 위도/경도로 변환햇을때!(*target지점 기준..)
half_cell_lat = (cell_size_km / 2) / km_per_lat_degree  #0.5km / 111km 
half_cell_lng = (cell_size_km / 2) / km_per_lng_degree #0.5km / 88km


# 6. 500m 계산 반경을 원으로 표시하기 위한 값 -> 지점을 중심으로 한 원의 반지름 = 500m
radius_km = 0.5

radius_lat = radius_km / km_per_lat_degree #0.5km / 111km
radius_lng = radius_km / km_per_lng_degree #0.5km / 88km




# 7. 그래프 만들기
fig, ax = plt.subplots(figsize=(8, 8)) #그림판 만들기


# 8. 안전등급 네모칸 도형 만들기
# 기준점을 중심으로 네모칸을 만들고, 안전등급 색으로 칠함
'''
[기본구조]
patches.Rectangle(
    (왼쪽아래 x좌표, 왼쪽아래 y좌표),
    사각형 가로길이,
    사각형 세로길이
)
'''
heatmap_cell = patches.Rectangle(
    (target_lng - half_cell_lng, target_lat - half_cell_lat),  # 왼쪽 아래 좌표
    2 * half_cell_lng,  # 네모 가로 길이
    2 * half_cell_lat,  # 네모 세로 길이
    facecolor=grade_color_dict[safety_grade], #네모칸 안쪽 색깔
    alpha=0.3,#투명도(살짝투명) *0 = 완전투명, 1 = 완전불투명
    edgecolor='black', #테두리색깔
    linewidth=2, #테두리 두께
    label=f'안전등급 {safety_grade}'
)

#patches.Restangel(...)은 네모칸 객체를 만든 것 뿐! 
ax.add_patch(heatmap_cell) #만든 네모칸을 그림판에 붙이기




# 9. 실제 시설을 센 500m 반경 표시
# 경도/위도 축 비율 때문에 완전한 원이 아니라 타원처럼 그려짐
search_circle = patches.Ellipse(
    (target_lng, target_lat), #타원의 중심좌표(경도, 위도)
    width=2 * radius_lng, #타원의 가로 지름 = (target기준으로 경도방향 500m를 치환한 값 X 2)
    height=2 * radius_lat, #타원의 세로 지름 
    fill=False, #테두리만 그리기
    edgecolor='black', #테두리 색깔
    linestyle='--', #테두리 타입 = 점선(계산 반경을 표시하는 용도이므로..)
    linewidth=2, #테두리 두께
    label='500m 계산 반경'
)

ax.add_patch(search_circle) #ax에 또 객체 하나 덧대서 올리기




# 10. 기준점 표시(또 ax위에 덧대서..)
ax.scatter(
    target_lng,
    target_lat,
    color='black',
    s=150,
    marker='X',
    label='기준점'
)



# 11. 500m 이내 시설물 표시
for facility_type in under_500m_data['시설유형'].unique():

    one_type_data = under_500m_data[
        under_500m_data['시설유형'] == facility_type
    ]

    ax.scatter(
        one_type_data['경도'],
        one_type_data['위도'],
        s=30,
        color=facility_color_dict.get(facility_type, 'gray'),
        marker=marker_dict.get(facility_type, 'o'),
        alpha=0.7,
        label=facility_type
    )


# 12. 화면 범위 설정
# 기준점 주변 700m 정도만 보이게 설정
view_range_km = 0.7

view_lat = view_range_km / km_per_lat_degree
view_lng = view_range_km / km_per_lng_degree

ax.set_xlim(target_lng - view_lng, target_lng + view_lng)
ax.set_ylim(target_lat - view_lat, target_lat + view_lat)


# 13. 제목, 축 이름, 범례
ax.set_title(f'단일 기준점 안전 히트맵 / 점수: {safety_score:.1f}, 등급: {safety_grade}')
ax.set_xlabel('경도')
ax.set_ylabel('위도')

ax.legend(loc='upper right')
ax.grid(True)

plt.show()


#히트맵 이미지 저장
#저장 경로 설정 
output_path = output_dir/ 'single_point_heatmap.png'
#저장 #fig라는 변수에 담긴 그림을 output+path위치에 저장해라 
fig.savefig(output_path,  
            dpi = 300, #해상도
            bbox_inches = 'tight') #그림 주변의 쓸데없는 여백을 줄여서 저장

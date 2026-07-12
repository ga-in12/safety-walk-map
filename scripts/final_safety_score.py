'''
흐름

1. 광진구 안전시설 데이터 경로 설정
2. 법정동 경계 SHP 파일 불러오기
3. 전체 경계 중 광진구에 속한 동만 선택
4. 광진구 동 경계를 하나로 합치기
5. 미터 단위 경계와 위도·경도 단위 경계를 따로 만들기
6. Matplotlib으로 광진구 경계 확인
7. Folium 지도 위에 광진구 경계 표시
8. 이후 500m 격자 생성
'''

import numpy as np
import pandas as pd
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import folium
from pyproj import Geod
from shapely.geometry import box #4개의 모서리 숫자를 사각형 polygon객체 하나로 반환할때 쓰이
from shapely.geometry import box, mapping #지도그리기

################### 경로 설정 ###################

# 시설물 통합 CSV 경로
facility_path = Path(
    'data/raw/광진구_안전시설_통합.csv'
)

# 법정동 경계 파일 폴더
boundary_dir = Path(
    'data/raw/boundary/lgldong'
)

# 가공 데이터 저장 폴더
processed_dir = Path(
    'data/processed'
)

processed_dir.mkdir(
    parents=True,
    exist_ok=True
)

# 결과 지도와 이미지 저장 폴더
output_dir = Path(
    'outputs'
)

output_dir.mkdir(
    parents=True,
    exist_ok=True
)





################### 설정값 ###################
#all_boundary_gdf = 전국 동 경계 geoDataframe
#gwangjin_dong_boundary_gdf = 광진구 동 경계 geoDataframe
#gwangjin_boundary_5186_gdf = 광진구 동 합친 경계 geoDatframe(m단위)
#gwangjin_boundary_4326_gdf = 광진구 동 합친 경계 geoDataframe(위도/경도단위)
#gwangjin_map = 광진구 중심 기준으로 한 map + 
#               gwangjin_boundary_4326_gdf을 이용하여 광진구 경계까지 그림



#cell_size_m = 격자 한 칸의 가로·세로 길이(m)
#center_lat = 광진구 중심 위도
#center_lng = 광진구 중심 경도
#lat_per_1m= 1m당 위도 변화량(광진구 중심점 기준으로 변환)
#lng_per_1m= 1m당 경도 변화량 
#cell_size_lat= 격자 길이당 위도 변화량(500m)
#cell_size_lng= 격자 길이당 경도 변화량(500m)


#lat_list= 위도 지점 리스트
#lng_list= 경도 지점 리스트
#point_list = 격자점 튜플 리스트

#def make_cell_polygon(point_lat, point_lng)= 격자점 기준으로 하나의 사각형cell 반환(box)
#def counting_facility(cell_polygon, facility_data)= 해당 cell안에 포함되는 시설물들만 세기
#def calculate_safety_score_cell(cell_polygon)= 격자 cell하나의 안전점수 계산하기
#def define_grade(safety_score)= 안전점수 기반 grade지정



#facility_data= 광진구 시설물 데이터
#safety_weight_dict= 안점점수 가중치 딕셔너리
#max_count_dict= 시설별 만점기준 개수 딕셔너리
#grade_color_dict= 안전등급별 색깔



#지도 관련 함수
#def make_gwangjing_map()= 광진구 지도 생성해주는 함수
#def add_gwaingjin_whole_square(map)= 광진구 경계를 감싸는 큰 사각형 만드는 함수
#def add_grid_point_cross_markers(map)= 격자점을 지도 위에 십자(+) 모양으로 표시하는 함수
#def add_facility_circle_markers(map, facility_data)= 지도 위에 시설물 점 찍는 함수
#def add_grid_cells_with_safety_color(map, result_df, gwangjin_polygon_4326)= 격자 cell을 안전등급 색깔로 채워서 지도에 표시하는 함수



#결과물 
#reuslt_df= 격자마다의 정보 dataframe





################### 법정동 경계 파일 불러오기 ###################

# SHP 파일 경로
shp_file = (
    boundary_dir
    / 'admstr_zone_lgldong_bndry_24.shp'
)


# SHP 파일을 GeoDataFrame으로 불러오기
# 여기에는 광진구뿐 아니라 다른 지역의 경계도 들어 있음
all_boundary_gdf = gpd.read_file(
    shp_file,
    encoding='cp949'
)


print(
    '[전체 법정동 경계 GeoDataFrame]'
)

#자료 형태 확인
print(
    all_boundary_gdf.head()
)

#어떤 좌표계를 사용하는지 확인
print(
    '전체 경계 좌표계:',
    all_boundary_gdf.crs,
    '''

    '''
)




################### 광진구에 속한 동 경계만 선택 ###################

# COL_ADM_SE는 시군구 코드
# 광진구 시군구 코드는 11215
gwangjin_dong_boundary_gdf = all_boundary_gdf[
    all_boundary_gdf['COL_ADM_SE'] == '11215' #True/False
]


print(
    '\n[광진구 동 경계 GeoDataFrame]'
)

print(
    gwangjin_dong_boundary_gdf.head()
)

print(
    '광진구 동 개수:',
    len(gwangjin_dong_boundary_gdf)
)

print(
    '광진구 동 경계 좌표계:',
    gwangjin_dong_boundary_gdf.crs,
    '''

    '''
)




################### 광진구 동 경계를 하나로 합치기 ###################

# 여러 동의 경계선을 모두 합쳐서
# 내부의 동 경계선을 없애고 하나의 광진구 모양으로 만듦
gwangjin_polygon = gwangjin_dong_boundary_gdf.union_all() #이때, union_all함수 때문에 자료형이 polygon이 됨




################### 광진구 전체 경계 GeoDataFrame 만들기 ###################

# union_all()의 결과는 Polygon이므로
# plot, 좌표계 변환 등을 편하게 하기 위해
# 다시 GeoDataFrame으로 감싸줌
#
# 현재 좌표계는 EPSG:5186
# 좌표값과 거리, 면적의 단위는 m 기준
gwangjin_boundary_5186_gdf = gpd.GeoDataFrame(
    {
        "name": ["광진구"]
    },
    geometry=[
        gwangjin_polygon
    ],
    crs=gwangjin_dong_boundary_gdf.crs #다시 geoDataFrame으로 고침
)


print(
    '\n[광진구 전체 경계 EPSG:5186]'
)

print(
    gwangjin_boundary_5186_gdf.head()
)

print(
    '좌표계:',
    gwangjin_boundary_5186_gdf.crs,
    '''

    '''
)


# Folium 지도 표시용으로 위도·경도 좌표계 변환
gwangjin_boundary_4326_gdf = (
    gwangjin_boundary_5186_gdf
    .to_crs(epsg=4326)
)


print(
    '\n[광진구 전체 경계 EPSG:4326]'
)

print(
    gwangjin_boundary_4326_gdf.head()
)

print(
    '좌표계:',
    gwangjin_boundary_4326_gdf.crs
)




################### Folium 지도 생성 함수#################
def make_gwangjing_map():
    map = folium.Map(
    location = [37.5384, 127.0822], #광진구 중심 위도, 경도
    zoom_start= 13 #확대 정도
    )

    ################### Folium 지도 위에 광진구 경계 표시 ##################
    folium.GeoJson( #지도 위에 경계선이나 영역을 올리는 함수
        data = gwangjin_boundary_4326_gdf,
        name = '광진구_경계',
        style_function= lambda _: #lambda함수 반환값 = 딕셔너리
        {
            'color': 'black',
            'weight': 2, #경계선의 굵기
            'fillOpacity': 0 #경계 안쪽에 채워지는 색의 투명도

        }
    ).add_to(map)

    return map

#브라우저에서 열어 확인하기 
#preview_map = make_gwangjin_map() #확인용 임시 맵
#preview_map.show_in_browser()


    






################## m단위를 위도,경도 단위로 바꾸기 #####################
#격자 한 칸의 가로, 세로 길이(m)
cell_size_m = 500

#지구 타웜체 기준 거리 계산기
geod = Geod(ellps = 'WGS84')

#광진구 중심점
center_lat = 37.5384
center_lng = 127.0822

#중심점에서 북쪽으로 1m이동한 좌표
north_lng, north_lat, _ = geod.fwd(
    center_lng, center_lat,
    0, #이동방향: 북쪽
    1  #이동거리: 1m
)


#중심점에서 동쪽으로 1m 이동한 좌표
east_lng, east_lat,_ = geod.fwd(
    center_lng, center_lat,
    90, #이동방향: 동쪽
    1   #이돟거리: 1m
)

#1m당 위도 변화량
lat_per_1m = north_lat - center_lat
#1m당 경도 변화량
lng_per_1m = east_lng - center_lng

#500m당 위도,경도 변화량
cell_size_lat = cell_size_m * lat_per_1m
cell_size_lng = cell_size_m * lng_per_1m








################### 광진구 경계를 감싸는 큰 사각형 만드는 함수###################
#격자점을 어디서부터 어디까지 만들기 정하기
#모서리
min_lng, min_lat, max_lng, max_lat = gwangjin_boundary_4326_gdf.total_bounds
    
def add_gwaingjin_whole_square(map):
    
    #사각형 지도에 표시해서 확인 
    folium.Rectangle(
        bounds = [
            [min_lat, min_lng],
            [max_lat, max_lng]
        ],
        color = 'blue',
        weight = 2,
        fill = False,
        tooltip = '격자생성범위'
    ).add_to(map)
    
    return map


#preview_map= make_gwangjin_whole_square(preview_map)
#preview_map.show_in_browser()










############## 광진구 포괄 사각형 안에서 격자 만들기 + 리스트 생성 ###########
#격자 간의 간격(위도, 경도) = 500m기준
#cell_size_lat= 격자 길이당 위도 변화량(500m)
#cell_size_lng= 격자 길이당 경도 변화량(500m)


#위도 지점 리스트(세로)
lat_list = []
for lat in np.arange(min_lat,
                    max_lat + cell_size_lat, #np.arange가 끝값을 포함하지 않는걸 해결
                    cell_size_lat): #500m간격으로 리스트 만들기(위도단위)
    lat_list.append(lat)

print('[위도 지점 리스트]')
print(lat_list)
print('[위도 지점 개수]')
print(len(lat_list))
print()


#경도 지점 리스트(가로)
lng_list = []
for lng in np.arange(min_lng,
                     max_lng + cell_size_lng,
                     cell_size_lng):
    lng_list.append(lng)

print('[경도 지점 리스트]')
print(lng_list)
print('[경도 지점 개수]')
print(len(lng_list))
print()


#위도지점리스트(lat_list), 경도지점리스트(lng_list)를 이용하여 격자 지점 튜플 리스트 만들기
point_list = [] #격자 튜플을 저장할 리스트

for lat in lat_list:
    for lng in lng_list:
        point_list.append((lat, lng))

print('[격자점 (위도,경도)]')
print(point_list[:5])
print('[격자점 개수]')
print(len(point_list))
print()






######################## 격자점을 지도 위에 십자(+) 모양으로 표시하는 함수 ################
def add_grid_point_cross_markers(map):
    #(점이 여러개이므로 반복문으로 구현)
    for lat, lng in point_list:

        folium.Marker(
            location=[lat, lng],

            icon=folium.DivIcon(
                html='''
                    <div style="
                        font-size: 18px;
                        font-weight: bold;
                        color: black;
                        width: 20px;
                        height: 20px;
                        line-height: 20px;
                        text-align: center;
                    ">
                        +
                    </div>
                ''',

                # + 표시의 중심이 실제 위도·경도 위치에 오도록 조정
                icon_size=(20, 20),
                icon_anchor=(10, 10)
            )
        ).add_to(map)

    return map

#preview_map = add_grid_point_cross_markers(preview_map)
#preview_map.show_in_browser()













################## 격자점마다 검사 구역 지정하기 ##################
#격자점마다 네모 구간 만드는 함수(함수 이름 적절한 걸로 바꿔줘도 됨)
def make_cell_polygon(point_lat, point_lng):
    #구역 모서리 좌표 만들기
    # 위도 방향: 남쪽과 북쪽
    min_lat = point_lat - cell_size_lat / 2   # 남쪽
    max_lat = point_lat + cell_size_lat / 2   # 북쪽

    # 경도 방향: 서쪽과 동쪽
    min_lng = point_lng - cell_size_lng / 2   # 서쪽
    max_lng = point_lng + cell_size_lng / 2   # 동쪽
    
    #하나의 사각형 polygon 객체 하나를 반환
    #box 입력 순서: box(서쪽 경도, 남쪽 위도, 동쪽 경도, 북쪽 위도)
    cell_polygon = box(
        min_lng, min_lat, max_lng, max_lat
    )



    return cell_polygon #자료형 = polygon
    #ex)POLYGON ((
    #127.08 37.53,
    #127.08 37.54,      
    #127.07 37.54,
    #127.07 37.53,
    #127.08 37.53))







################## 지도 위에 시설물 점 찍는 함수 ################
#시설물 데이터 불러오기 
facility_data = pd.read_csv(facility_path, encoding= 'utf-8-sig')
#print(facility_data.head())
'''
  시설명  시설유형                          주소        위도         경도
0  CCTV  CCTV    서울특별시 광진구 광장로3길 22 (광장동)  37.54850  127.10300
1  CCTV  CCTV    서울특별시 광진구 아차산로 540 (광장동)  37.54244  127.10147
2  CCTV  CCTV  서울특별시 광진구 아차산로78길 53 (광장동)  37.55144  127.10983
3  CCTV  CCTV    서울특별시 광진구 아차산로 636 (광장동)  37.54891  127.10899
4  CCTV  CCTV    서울특별시 광진구 천호대로 809 (광장동)  37.54587  127.10359
'''



def add_facility_circle_markers(map, facility_data):
    
    #시설물 점 색깔 딕셔너리
    facility_color_dict = {
        'CCTV': 'green',
        '가로등': 'orange',
        '비상벨': 'red',
        '경찰서': 'navy',
        '파출소': 'blue',
        '지구대': 'deepskyblue'
    }

    
    #데이터프레임 한 행씩 돌면서.....
    #facility_data.iterrows()는 데이터프레임을 한 행씩 꺼내는 기능
    for _, facility in facility_data.iterrows(): #*행번호는 받아오지 않음
        #해당 시설의 위도,경도 정보 받아오기
        lat = facility['위도']
        lng = facility['경도']

        #시설물 종류 확인 
        facility_type = facility['시설유형']

        #시설물 표시색깔 가져오기(딕셔너리에 없는 시설유형이면 회색 사용)
        marker_color = facility_color_dict.get(
            facility_type,
            'gray'
        )

        #지도 위에 점 찍기
        folium.CircleMarker(
            location = [lat, lng],
            radius = 2, #점의 크기 
            color = marker_color, #점 테두리 색갈
            weight = 1, #점 테두리 두께
            fill = True, #점 내부 채우기
            fill_color = marker_color,
            fill_opacity = 0.8, #점 내부 투명도
            tooltip = facility_type #마우스를 올렸을때 시설유형 표시 
        ).add_to(map)

    return map


#preview_map = add_facility_circle_markers(preview_map, facility_data)
#preview_map.show_in_browser()





###
##
###
###
###
################## 격자 cell을 안전등급 색깔로 채워서 지도에 표시하는 함수 ##################
# + 
def add_grid_cells_with_safety_color(map, result_df, gwangjin_polygon_4326):

    for _, row in result_df.iterrows(): #결과물 dataframe한 행씩 순회하며........

        # 결과 dataframe에 저장된 중심 위경도로 cell_polygon 다시 생성
        cell_polygon = make_cell_polygon(
            row['중심위도'],
            row['중심경도']
        )

        # 광진구 경계 밖으로 나가는 부분은 잘라내기(intersection)
        #intersection() = 두 도형이 겹치는 부분만 잘라서 새로운 도형으로 반환하는 함수// 도형A.intersection(도형B) 
        clipped_polygon = cell_polygon.intersection(gwangjin_polygon_4326)

        # 겹치는 부분이 아예 없으면 (혹시 모를 예외) 건너뛰기
        if clipped_polygon.is_empty:
            continue

        # 마우스 올렸을 때 보여줄 텍스트
        tooltip_text = f"등급 {row['안전등급']} (점수: {row['안전점수']:.1f})"

        # 클릭했을 때 보여줄 상세 정보
        popup_text = (
            f"<b>격자 {row['격자번호']}번</b><br>"
            f"안전등급: {row['안전등급']}<br>"
            f"안전점수: {row['안전점수']:.1f}점<br>"
            f"CCTV: {row['CCTV개수']}개<br>"
            f"가로등: {row['가로등개수']}개<br>"
            f"비상벨: {row['비상벨개수']}개<br>"
            f"경찰서: {row['경찰서개수']}개<br>"
            f"파출소: {row['파출소개수']}개<br>"
            f"지구대: {row['지구대개수']}개"
        )

        # 클로저 문제 방지: 반복문 안에서 lambda를 쓸 때
        # 기본 인자(color=...)로 현재 row의 색을 고정시켜줘야
        # 모든 cell이 마지막 색으로 통일되는 버그를 막을 수 있음
        folium.GeoJson(
            data=mapping(clipped_polygon),
            style_function=lambda _, color=row['등급색상']: {
                'fillColor': color,
                'color': 'gray',      # cell 테두리 색
                'weight': 0.5,
                'fillOpacity': 0.5
            },
            tooltip=tooltip_text,
            popup=folium.Popup(popup_text, max_width=250)
        ).add_to(map)

    return map










##################### 하나의 cell_polygon의 시설 카운트 딕셔너리 함수 #####################

#해당 구역 안에 포함되는 시설물들만 세기
def counting_facility(cell_polygon, facility_data):
    #시설유형별 개수를 저장할 딕셔너리
    facility_count_dict={
        'CCTV': 0,
        '가로등':0, 
        '비상벨': 0,
        '경찰서': 0,
        '파출소': 0,
        '지구대': 0
    }

    #해당 구역 네 모서리
    min_lng, min_lat, max_lng, max_lat = cell_polygon.bounds

    #시설물 데이터를 한 행씩 확인
    for _, facility in facility_data.iterrows(): #type(facility) = 시리즈
        
        #해당 시설의 종류 확인 
        facility_type = facility['시설유형']

        #해당 시설의 위치 확인
        lat = facility['위도']
        lng = facility['경도']

        #해당 시설의 위도, 경도가 cell_polygon안에 포함되는지 확인
        is_inside_lat = min_lat <= lat <= max_lat
        is_inside_lng = min_lng <= lng <= max_lng

        if is_inside_lat and is_inside_lng:#만약 시설이 네 모서리 안에 존재한다면...
            #해당 시설 유형 딕셔너리 count value값 1증가
            if facility_type in facility_count_dict:
                facility_count_dict[facility_type] += 1
    
    #해당 격자 cell기준, 모든 시설에 대한 검사를 마친 후 
    return facility_count_dict #시설 카운트 딕셔너리 반환









##################### 하나의 cell_polygon의 안전점수 계산하기 #####################

#안전점수 가중치 딕셔너리(임시 가중치)
#시설별 가중치의 합은 100
safety_weight_dict = {
    "CCTV": 30,
    "가로등": 20,
    "비상벨": 5,
    "경찰서": 15,
    "파출소": 15, 
    "지구대": 15
}


# 시설별 만점 기준 개수
max_count_dict = {
    "CCTV": 20,
    "가로등":80,
    "비상벨": 10,
    "경찰서": 1,
    "파출소": 1,
    "지구대": 1
}

#cell_polygon(네모칸 하나)의 안전점수 계산하기
def calculate_safety_score_cell( facility_count_dict):

    #안전점수 가중치 딕셔너리를 이용하여 해당 cell의 안점점수 계산하기
    safety_score  = 0 #초기화

    
    #ratio구하기(만점이상일 경우 1로 계산)
    CCTV_ratio = min(facility_count_dict['CCTV']/max_count_dict['CCTV'], 1)
    bell_ratio = min(facility_count_dict['비상벨']/max_count_dict['비상벨'], 1)
    police_station_ratio = min(facility_count_dict['경찰서']/max_count_dict['경찰서'],1)
    police_box_ratio = min(facility_count_dict['파출소']/max_count_dict['파출소'], 1)
    police_substation_ratio= min(facility_count_dict['지구대']/max_count_dict['지구대'], 1)
    light_ratio = min(facility_count_dict['가로등']/max_count_dict['가로등'], 1)

   
   #안점점수구허가
    safety_score =( safety_weight_dict['CCTV']*CCTV_ratio + safety_weight_dict['비상벨']*bell_ratio +
                   safety_weight_dict['경찰서'] * police_station_ratio + safety_weight_dict['가로등']*light_ratio+
                   safety_weight_dict['파출소'] * police_box_ratio + safety_weight_dict['지구대'] * police_substation_ratio)
    

    #해당 격자 안전점수 반환
    return safety_score


 




################### 하나의 cell_polygon의 grade지정 함수 ########################

def define_grade(safety_score):
    if safety_score >= 80:
        return 'A' 
    elif safety_score >= 60:
        return 'B'  
    elif safety_score >=40:
        return 'C'  
    elif safety_score >= 20:
        return 'D'
    else:
        return 'E'






#################### 모든 격자점에 대해서 안점점수 계산하기+ grade지정 + 색깔 지정##################
# 안전등급별 색깔
grade_color_dict = {
    "A": "green",
    "B": "yellowgreen",
    "C": "yellow",
    "D": "orange",
    "E": "red"
}



# #################### 모든 격자점 안전점수 계산 ####################
# dataframe에 해당 격자점 정보 저장
result_columns = [
    '격자번호', '중심위도', '중심경도',
    '격자한변길이_m', '격자전체면적_m2',
    'CCTV개수','가로등개수', '비상벨개수','경찰서개수','지구대개수','파출소개수','전체시설개수',
    '안전점수', '안전등급', '등급색상'
]
result_df = pd.DataFrame(columns= result_columns)
# 각 격자의 결과를 저장할 리스트(격자마다의 결과 딕셔너리를 넣을거임)
result_rows = []




#필요한 변수 선언
gwangjin_polygon_4326 = gwangjin_boundary_4326_gdf.geometry.iloc[0]
total_point_count = len(point_list)


#격자점 리스트 순회
#enumerate(): 각 값앞에 번호를 붙여줌(ex: point_number)
for point_number, (point_lat, point_lng) in enumerate(
    point_list,
    start=1 #번호를 0번 부터가 아닌 1번부터 붙이기!
):
    # 현재 진행 상황 출력
    print(
        f'\r격자 계산 중: {point_number}/{total_point_count} '
        f'({point_number / total_point_count * 100:.1f}%)',
        end='',
        flush=True
    )

    # 해당 격자점을 기준으로 하는 cell_polygon 생성
    cell_polygon = make_cell_polygon(
        point_lat,
        point_lng
    )
    #만약 해당 cell이 광진구와 전혀 겹치지 않는다면 제외
    
    #intersects:
    if not cell_polygon.intersects(
        gwangjin_polygon_4326
    ):
        continue #다음 cell계산

    #시설물 개수 세기
    facility_count_dict = counting_facility(cell_polygon, facility_data)


    # cell_polygon의 안전점수 계산
    safety_score = calculate_safety_score_cell(
        facility_count_dict
    )

    # 안전등급
    safety_grade = define_grade(
        safety_score
    )

    # cell_polygon 색깔
    safety_grade_color = grade_color_dict[
        safety_grade
    ]

    #현재 격자의 결과를 딕셔너리 형태로 저장
    cell_result_dict = {
        '격자번호': point_number,
        '중심위도': point_lat,
        '중심경도': point_lng,
        '격자한변길이_m': cell_size_m,
        '격자전체면적_m2': cell_size_m ** 2,
        'CCTV개수': facility_count_dict['CCTV'],
        '가로등개수': facility_count_dict['가로등'],
        '비상벨개수': facility_count_dict['비상벨'],
        '경찰서개수': facility_count_dict['경찰서'],
        '지구대개수': facility_count_dict['지구대'],
        '파출소개수': facility_count_dict['파출소'],
        '전체시설개수': sum(facility_count_dict.values()), #values(): 딕셔너리에서 값만 꺼내는 기능
        '안전점수': safety_score,
        '안전등급': safety_grade,
        '등급색상': safety_grade_color
    }

    # 결과 리스트에 현재 격자 정보 추가
    result_rows.append(
        cell_result_dict
    )


# 모든 격자의 계산이 끝난 뒤 DataFrame 생성
result_df = pd.DataFrame(
    result_rows,
    columns=result_columns
)

print('\n모든 격자 계산 완료')






#################### 지도 구현 ####################
# 광진구 지도 만들기 (경계선 포함)
gwangjin_map = make_gwangjing_map()

# 광진구 전체 polygon (경계 자르기 + intersects 판정용, EPSG:4326)
gwangjin_polygon_4326 = gwangjin_boundary_4326_gdf.geometry.iloc[0]

# 격자 cell을 안전등급 색깔로 채우기 (맨 아래 레이어로 먼저 그리기)
add_grid_cells_with_safety_color(gwangjin_map, result_df, gwangjin_polygon_4326)

# 격자점 찍기
add_grid_point_cross_markers(gwangjin_map)

# 시설물 점 찍기
add_facility_circle_markers(gwangjin_map, facility_data)

gwangjin_map.show_in_browser()





############### 저장 ##########################
gwangjin_map.save(output_dir/ 'gwangjin_safety_map.html')
result_df.to_csv(processed_dir/ 'safety_score_result_csv.csv', index = False)

########### 면적보정 vs 실제 데이터 더 수집하기... ####################
##면적 보정 방법은 claude에 있음









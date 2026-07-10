'''
흐름

'''

import numpy as np 
import pandas as pd
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import folium


###################경로설정###################
#시설물 통합 csv 경로
facility_path  = Path('data/raw/광진구_안전시설_통합.csv')
#광진구 경계 폴더
boundary_dir = Path('data/raw/boundary/lgldong')
#가공데이터 저장 폴더 
processed_dir = Path('data/processed')
processed_dir.mkdir(parents= True,exist_ok=True)
#결과 히트맵 저장 폴더 
output_dir= Path('outputs')
output_dir.mkdir(parents= True, exist_ok = True)



###################
#일단 지금 음.... 광진구 경계 위에 격자를 500m 간격으로 찍어야함
#그리고 찍은 격자를 중심으로한 사각형 만들기(가로 500m, 세로 500m)
#그리고 격자에 시설들 체크하고 카운팅
#해당 사각형의 모서리 네개 중 하나라도 광진구 경계를 벗어나는지 확인
#만약 벗어난다면 경계를 넘어가는 영역 자르기!(이거 어케 구현하지;;)
#면적 보정(네모칸이 안 잘린 경우, 면적 보정을 해도 보정전과 같음)
#가중치 고려해서 해당 격자 위 점수 내기 + 등급 내기
#Q.지도를 어떻게 그리지?



###################설정값들#####################
#격자 한 칸 길이(m)
cell_size_m = 500

#격자 면적 
cell_size_m2 = cell_size_m * cell_size_m

#가중치 //합쳐서 100이 나오게 설정
safety_weight_dict = {
    "CCTV": 35,
    "가로등": 30,
    "비상벨": 20,
    "경찰서": 15
}

#만점 기준 
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


####################광진구 경계 geoDataFrame만들기######################
#경계파일 읽기
shp_file = Path(boundary_dir/'admstr_zone_lgldong_bndry_24.shp')
boundary_gdf = gpd.read_file(shp_file, encoding='cp949') #geoDataFrame으로 읽음

#광진구만 골라내기
# COL_ADM_SE는 시군구 코드이고, 광진구 코드는 11215
gwangjin_boundary_gdf =  boundary_gdf[boundary_gdf['COL_ADM_SE'] == '11215']
print('[광진구 경계 geoDataFrame출력]')
print(gwangjin_boundary_gdf.head())

#동끼리의 경계 지우고 실질적인 '광진구경계'만 남게 합치기
gwangjin_polygon = gwangjin_boundary_gdf.geometry.union_all()
print(type(gwangjin_polygon)) #<class 'shapely.geometry.polygon.Polygon'>

#간편하게 plot하기 위해 geoDataFrame으로 변환 
gwangjin_total_boundary_gdf = gpd.GeoDataFrame( 
    {
        "name": ["광진구"]
    },
    geometry=[gwangjin_polygon],
    crs = gwangjin_boundary_gdf.crs #좌표계 설정!!(위도 경도 아니고 m단위임)
)
print(gwangjin_total_boundary_gdf.head())
print(gwangjin_total_boundary_gdf.crs) #좌표계 = EPSG:5186(m)





####################광진구 경계 그리기######################
# 한글 깨짐 방지: Windows 기준
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

#만든 광진구경계 geoDataFrame을 지도모양으로 plot
ax = gwangjin_total_boundary_gdf.plot(
    figsize=(8,8),
    edgecolor = 'black',
    facecolor= 'lightgreen',
    linewidth = 1 
)

plt.title('광진구 법정동 경계')
plt.xlabel('X축(m단위)')
plt.ylabel('Y축(m단위)')
plt.axis('equal') #찌그러짐 방지(지도, 도형, 거리, 면적, 격자인 경우에 주로 사용)
#plt.show()

#저장(practoce_outputs에 저장)
# 저장 폴더 생성
practice_outputs_dir = Path("outputs/practice_outputs")
practice_outputs_dir.mkdir(parents=True, exist_ok=True)

# 저장할 파일 경로
save_path = practice_outputs_dir / "gwangjin_boundary.png"

# 저장
plt.savefig(save_path, dpi=300, bbox_inches="tight")





##################지도 생성(foluim) + 지도 위에 경계그리기##################
#지도 생성
gwangjin_map = folium.Map(location = [37.5384, 127.0822], #지도에서 처음 보여줄 중심 위치
                    zoom_start = 13) #얼마나 확대해서 보여줄지


# folium에 올리기 위해 좌표계를 위도/경도 좌표계로 변환
gwangjin_total_boundary_gdf = gwangjin_total_boundary_gdf.to_crs(epsg=4326)

# 지도 위에 광진구 경계선 덧대기
folium.GeoJson(
    data=gwangjin_total_boundary_gdf.to_json(),
    name="광진구 경계",
    style_function=lambda feature: {
        "color": "black",        # 경계선 색
        "weight": 3,            # 경계선 두께
        "fillColor": "blue",    # 내부 색
        "fillOpacity": 0.1      # 내부 투명도
    }
).add_to(gwangjin_map)

# 4. 브라우저로 열기
gwangjin_map.show_in_browser()




################격자 찍기(격자중심점 간의 사이 = 500m)###################3

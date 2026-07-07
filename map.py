"""
지도 시각화 및 UI 골격 코드
지도(folium) + UI(streamlit)

[3주차 업데이트]
데이터 담당이 넘겨준 통합 CSV(광진구_안전시설_통합.csv) 반영.
경찰서/지구대·파출소 포함 전체 시설이 위경도까지 포함된 상태로 들어옴.
-> 기존에 원본 파일 5개를 따로 매핑하던 RAW_COLUMN_MAP 제거하고 통합 CSV 하나만 읽어오는 구조로 변경함.
"""

import os
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import MarkerCluster
import pandas as pd


STANDARD_COLUMNS = {
    "lat": "위도",
    "lng": "경도",
    "type": "시설유형",   # "CCTV", "가로등", "비상벨", "파출소", "지구대", "경찰서"
    "address": "주소",
}

# 통합 CSV 파일명 
INTEGRATED_CSV_FILENAME = "광진구_안전시설_통합.csv"

# 인코딩 자동 감지용 후보 목록 
ENCODING_CANDIDATES = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]


def _read_csv_with_fallback_encoding(filepath: str) -> pd.DataFrame:
    last_error = None
    for enc in ENCODING_CANDIDATES:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            return df
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
    raise last_error


def load_all_facilities(file_dir: str) -> pd.DataFrame:
    """통합 CSV 읽어서 표준 컬럼 형태로 반환함.
    """
    filepath = os.path.join(file_dir, INTEGRATED_CSV_FILENAME)
    if not os.path.exists(filepath):
        print(f"[안내] {INTEGRATED_CSV_FILENAME} 없음 -> 더미 데이터로 대체 예정")
        return pd.DataFrame(columns=list(STANDARD_COLUMNS.values()))

    df = _read_csv_with_fallback_encoding(filepath)

    # BOM이 남아있는 경우에 컬럼명 정리
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]

    lat_col, lng_col, type_col = (
        STANDARD_COLUMNS["lat"],
        STANDARD_COLUMNS["lng"],
        STANDARD_COLUMNS["type"],
    )

    # 위경도 없는 행이 있을 경우를 대비
    df = df.dropna(subset=[lat_col, lng_col])

    keep_cols = [c for c in STANDARD_COLUMNS.values() if c in df.columns]
    df = df[keep_cols].copy()

    return df.reset_index(drop=True)


# 시설 유형별 마커 디자인 파트 
FACILITY_STYLE = {
    "CCTV": {"color": "blue", "icon": "video-camera", "prefix": "fa"},
    "가로등": {"color": "orange", "icon": "lightbulb-o", "prefix": "fa"},
    "비상벨": {"color": "red", "icon": "bell", "prefix": "fa"},
    "파출소": {"color": "darkblue", "icon": "shield", "prefix": "fa"},
    "지구대": {"color": "darkblue", "icon": "shield", "prefix": "fa"},
    "경찰서": {"color": "black", "icon": "building", "prefix": "fa"},
}

DEFAULT_STYLE = {"color": "gray", "icon": "info-sign", "prefix": "glyphicon"}


def get_marker_style(facility_type: str) -> dict:
    return FACILITY_STYLE.get(facility_type, DEFAULT_STYLE)


# Folium 기본 지도 객체 생성 
GWANGJIN_CENTER = [37.5384, 127.0822]  # 광진구 대략 중심 좌표


def create_base_map(center=GWANGJIN_CENTER, zoom_start=14) -> folium.Map:
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="CartoDB positron",
    )
    return m


# 마커가 많은 시설유형(가로등/CCTV/비상벨)은 MarkerCluster로 묶어서 렌더링
# 그냥 하나씩 Icon 마커로 그리면 5000개 넘는 DOM이 생겨서 브라우저가 멈추거나 무한 로딩하는 오류가 발생함. 경찰서/지구대/파출소 같은 소수 카테고리는 클러스터 없이 진행함.
CLUSTER_THRESHOLD = 50  #50개 이상이면 클러스터링 적용


def add_facility_layers(m: folium.Map, df: pd.DataFrame) -> folium.Map:
    """시설유형별 FeatureGroup을 만들고 지도에 마커를 추가한 뒤
    LayerControl로 ON/OFF 토글 기능을 붙임.

    df는 STANDARD_COLUMNS 기준 컬럼(위도, 경도, 시설유형, 주소)을
    가지고 있다고 가정함.
    """
    lat_col, lng_col, type_col, addr_col = (
        STANDARD_COLUMNS["lat"],
        STANDARD_COLUMNS["lng"],
        STANDARD_COLUMNS["type"],
        STANDARD_COLUMNS["address"],
    )

    facility_types = df[type_col].unique()
    layers = {}

    for f_type in facility_types:
        layers[f_type] = FeatureGroup(name=f_type, show=True)

    for f_type in facility_types:
        sub_df = df[df[type_col] == f_type]
        style = get_marker_style(f_type)

        # 마커 개수가 많은 유형은 클러스터 컨테이너에 담아서 성능 확보
        use_cluster = len(sub_df) >= CLUSTER_THRESHOLD
        target = MarkerCluster().add_to(layers[f_type]) if use_cluster else layers[f_type]

        for _, row in sub_df.iterrows():
            popup_text = f_type
            if addr_col in sub_df.columns and pd.notna(row.get(addr_col)):
                popup_text += f"<br>{row[addr_col]}"

            if use_cluster:
                # 클러스터 내부는 가벼운 CircleMarker로 표시 
                marker = folium.CircleMarker(
                    location=[row[lat_col], row[lng_col]],
                    radius=5,
                    color=style["color"],
                    fill=True,
                    fill_color=style["color"],
                    fill_opacity=0.8,
                    popup=popup_text,
                )
            else:
                marker = folium.Marker(
                    location=[row[lat_col], row[lng_col]],
                    popup=popup_text,
                    icon=folium.Icon(
                        color=style["color"],
                        icon=style["icon"],
                        prefix=style["prefix"],
                    ),
                )
            marker.add_to(target)

    for layer in layers.values():
        layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    return m


def build_dummy_data() -> pd.DataFrame:
    """통합 CSV가 없을 때 대비용 더미 데이터 """ 
    data = [
        {"위도": 37.5400, "경도": 127.0830, "시설유형": "CCTV", "주소": "테스트 주소1"},
        {"위도": 37.5420, "경도": 127.0810, "시설유형": "가로등", "주소": "테스트 주소2"},
        {"위도": 37.5370, "경도": 127.0850, "시설유형": "비상벨", "주소": "테스트 주소3"},
        {"위도": 37.5390, "경도": 127.0795, "시설유형": "파출소", "주소": "테스트 주소4"},
    ]
    return pd.DataFrame(data)


# Streamlit 앱
def run_streamlit_app():
    import streamlit as st
    from streamlit_folium import st_folium

    st.set_page_config(page_title="광진구 안전지도", layout="wide")
    st.title("광진구 안전지수 지도")

    tab1, tab2, tab3 = st.tabs(["지도", "안전지수", "경로 추천"])

    with tab1:
        st.subheader("시설 위치 지도")

        DATA_DIR = "./data"
        df = load_all_facilities(DATA_DIR)

        # 시설유형별 필터 (사이드바)
        all_types = sorted(df[STANDARD_COLUMNS["type"]].unique().tolist())
        selected_types = st.sidebar.multiselect(
            "표시할 시설유형 선택", options=all_types, default=all_types
        )
        filtered_df = df[df[STANDARD_COLUMNS["type"]].isin(selected_types)]

        m = create_base_map()
        m = add_facility_layers(m, filtered_df)
        st_folium(m, width=1000, height=600)

    with tab2:
        st.subheader("안전지수 히트맵 (안전지수 파트 연동 예정)")
        st.info("안전지수 파트 결과물 연동 대기 중")

    with tab3:
        st.subheader("안전 우선 경로 추천 (경로 파트 연동 예정)")
        st.info("경로 추천 파트 결과물 연동 대기 중")


if __name__ == "__main__":
    run_streamlit_app()
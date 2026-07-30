"""
지도 시각화 및 UI 골격 코드
지도(folium) + UI(streamlit)

"""

import os
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import FastMarkerCluster
import pandas as pd
import streamlit as st

from route_mock import recommend_safe_route  # 4주차: 경로 추천 목업 함수 


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


@st.cache_data(show_spinner="시설 데이터 불러오는 중...")
def load_all_facilities(file_dir: str) -> pd.DataFrame:
    """통합 CSV 읽어서 표준 컬럼 형태로 반환함."""
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


@st.cache_data(show_spinner="지도 렌더링 중...")
def build_facility_map(_df_placeholder_unused, selected_types: tuple, data_dir: str, center: tuple, zoom_start: int):
    """선택된 시설유형 조합이 동일하면 캐시된 지도를 재사용함.
    (df 자체는 캐시 키로 쓰기엔 무거워서, load_all_facilities가 이미 캐시돼있다는
    전제로 여기선 selected_types만 키로 사용함)
    """
    df = load_all_facilities(data_dir)
    type_col = STANDARD_COLUMNS["type"]
    filtered_df = df[df[type_col].isin(selected_types)]

    m = create_base_map(center=list(center), zoom_start=zoom_start)
    m = add_facility_layers(m, filtered_df)
    return m, len(filtered_df), len(df)


# 마커가 많은 시설유형(가로등/CCTV/비상벨)은 MarkerCluster로 묶어서 렌더링
# 그냥 하나씩 Icon 마커로 그리면 5000개 넘는 DOM이 생겨서 브라우저가 멈추거나 무한 로딩하는 오류가 발생함.
# 경찰서/지구대/파출소 같은 소수 카테고리는 클러스터 없이 진행함.
CLUSTER_THRESHOLD = 50  # 50개 이상이면 클러스터링 적용


# [4주차 성능 개선] 다량 마커용 JS 콜백
# 기존에는 파이썬 for문으로 CircleMarker를 하나씩 만들어서 MarkerCluster에 add했는데,
# CCTV/가로등처럼 수천 개인 유형에서는 이게 페이지 로딩을 심하게 느리게 만들고
# 브라우저가 회색 화면으로 멈추는 원인이 됨.
# FastMarkerCluster는 좌표 데이터를 JS 쪽으로 통째로 넘기고 클러스터링 자체를
# 브라우저(JS)에서 처리해서 훨씬 빠름.
_FAST_CLUSTER_CALLBACK = """
function (row) {
    var marker = L.circleMarker(new L.LatLng(row[0], row[1]), {
        radius: 5,
        color: row[2],
        fill: true,
        fillColor: row[2],
        fillOpacity: 0.8
    });
    marker.bindPopup(row[3]);
    return marker;
}
"""


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

        use_cluster = len(sub_df) >= CLUSTER_THRESHOLD

        if use_cluster:
            # 좌표+색상+팝업 텍스트를 리스트로 한 번에 넘겨서 JS에서 클러스터링/렌더링 처리
            popups = f_type
            if addr_col in sub_df.columns:
                popups = sub_df[addr_col].fillna(f_type).apply(lambda a: f"{f_type}<br>{a}")
            else:
                popups = [f_type] * len(sub_df)

            data = [
                [lat, lng, style["color"], popup]
                for lat, lng, popup in zip(sub_df[lat_col], sub_df[lng_col], popups)
            ]
            FastMarkerCluster(data=data, callback=_FAST_CLUSTER_CALLBACK).add_to(layers[f_type])
        else:
            for _, row in sub_df.iterrows():
                popup_text = f_type
                if addr_col in sub_df.columns and pd.notna(row.get(addr_col)):
                    popup_text += f"<br>{row[addr_col]}"

                folium.Marker(
                    location=[row[lat_col], row[lng_col]],
                    popup=popup_text,
                    icon=folium.Icon(
                        color=style["color"],
                        icon=style["icon"],
                        prefix=style["prefix"],
                    ),
                ).add_to(layers[f_type])

    for layer in layers.values():
        layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    return m


def build_dummy_data() -> pd.DataFrame:
    """통합 CSV가 없을 때 대비용 더미 데이터"""
    data = [
        {"위도": 37.5400, "경도": 127.0830, "시설유형": "CCTV", "주소": "테스트 주소1"},
        {"위도": 37.5420, "경도": 127.0810, "시설유형": "가로등", "주소": "테스트 주소2"},
        {"위도": 37.5370, "경도": 127.0850, "시설유형": "비상벨", "주소": "테스트 주소3"},
        {"위도": 37.5390, "경도": 127.0795, "시설유형": "파출소", "주소": "테스트 주소4"},
    ]
    return pd.DataFrame(data)



# [4주차 신규] 주소 -> 좌표 변환 (geopy)

def geocode_address(address: str):
    """주소 문자열을 (위도, 경도) 튜플로 변환함.
    Nominatim은 무료 API라 요청 제한이 있어서, 실패 시 None을 반환하고
    화면에서 에러 메시지로 안내함.
    """
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError

    geolocator = Nominatim(user_agent="gwangjin_safety_map")
    try:
        location = geolocator.geocode(address, timeout=5)
    except (GeocoderTimedOut, GeocoderServiceError):
        return None

    if location is None:
        return None
    return (location.latitude, location.longitude)


def add_user_location_marker(m: folium.Map, lat: float, lng: float, label: str = "내 위치") -> folium.Map:
    """사용자가 입력한 위치를 지도 위에 강조 마커(별 아이콘)로 표시함."""
    folium.Marker(
        location=[lat, lng],
        popup=label,
        tooltip=label,
        icon=folium.Icon(color="green", icon="star", prefix="fa"),
    ).add_to(m)
    # 위치를 눈에 잘 띄게 하기 위한 반경 원 표시
    folium.Circle(
        location=[lat, lng],
        radius=50,
        color="green",
        fill=True,
        fill_opacity=0.15,
    ).add_to(m)
    return m


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
        df = load_all_facilities(DATA_DIR)  # @st.cache_data 적용됨 - 매 rerun마다 재로딩 안 함

        # 시설유형별 필터 (사이드바)
        all_types = sorted(df[STANDARD_COLUMNS["type"]].unique().tolist())
        selected_types = st.sidebar.multiselect(
            "표시할 시설유형 선택", options=all_types, default=all_types
        )

        # [4주차 신규] 주소 입력 -> geopy 좌표 변환 -> 사용자 위치 마커 표시
        st.markdown("##### 내 위치 찾기")
        addr_col, btn_col = st.columns([4, 1])
        address_input = addr_col.text_input(
            "주소를 입력하세요", placeholder="예: 서울특별시 광진구 능동로 120", label_visibility="collapsed"
        )
        find_clicked = btn_col.button("위치 찾기", use_container_width=True)

        user_location = None
        if find_clicked:
            if not address_input.strip():
                st.warning("주소를 입력해주세요.")
            else:
                result = geocode_address(address_input)
                if result is None:
                    st.error("주소를 찾을 수 없음. 주소를 더 구체적으로 입력해주세요.")
                else:
                    user_location = result
                    st.session_state["user_location"] = result
                    st.success(f"위치 확인됨: 위도 {result[0]:.5f}, 경도 {result[1]:.5f}")

        # 이전에 찾은 위치가 있으면 유지 (재검색 전까지 지도에 계속 표시)
        if user_location is None and "user_location" in st.session_state:
            user_location = st.session_state["user_location"]

        map_center = user_location if user_location else GWANGJIN_CENTER
        zoom = 16 if user_location else 14

        m, shown_count, total_count = build_facility_map(
            None, tuple(sorted(selected_types)), DATA_DIR, tuple(map_center), zoom
        )
        st.sidebar.caption(f"표시 중인 데이터: {shown_count}건 / 전체 {total_count}건")

        if user_location:
            m = add_user_location_marker(m, user_location[0], user_location[1])

        # returned_objects=[] : 클릭/줌 등 상호작용 데이터를 파이썬으로 안 돌려받게 해서
        # 매 상호작용마다 전체 스크립트가 무겁게 rerun되는 걸 줄임 (회색 화면/렉의 주요 원인 중 하나)
        st_folium(m, use_container_width=True, height=600, returned_objects=[])

    with tab2:
        st.subheader("안전지수 히트맵 (안전지수 파트 연동 예정)")
        st.info("안전지수 파트 결과물 연동 대기 중")

    with tab3:
        st.subheader("안전 우선 경로 추천")
        st.caption("경로 추천 알고리즘 연동 전까지는 목업 함수로 화면만 구성함")

        c1, c2 = st.columns(2)
        start_addr = c1.text_input("출발지 주소", key="route_start")
        end_addr = c2.text_input("도착지 주소", key="route_end")

        if st.button("경로 찾기"):
            if not start_addr.strip() or not end_addr.strip():
                st.warning("출발지와 도착지를 모두 입력해주세요.")
            else:
                start_loc = geocode_address(start_addr)
                end_loc = geocode_address(end_addr)

                if start_loc is None or end_loc is None:
                    st.error("출발지 또는 도착지 주소를 찾을 수 없음.")
                else:
                    result = recommend_safe_route(
                        start_loc[0], start_loc[1], end_loc[0], end_loc[1]
                    )

                    route_map = create_base_map(center=start_loc, zoom_start=15)
                    folSTium.PolyLine(
                        result["path"], color="blue", weight=5, opacity=0.8
                    ).add_to(route_map)
                    route_map = add_user_location_marker(
                        route_map, start_loc[0], start_loc[1], label="출발지"
                    )
                    folium.Marker(
                        location=end_loc,
                        popup="도착지",
                        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
                    ).add_to(route_map)

                    st_folium(route_map, use_container_width=True, height=500, returned_objects=[])

                    m1, m2 = st.columns(2)
                    m1.metric("거리", f"{result['distance_m']:.0f} m")
                    m2.metric("안전지수", f"{result['safety_score']:.1f}")


if __name__ == "__main__":
    run_streamlit_app()
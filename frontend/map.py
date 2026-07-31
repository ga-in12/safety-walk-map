"""
지도 시각화 및 UI 골격 코드
지도(folium) + UI(streamlit)

폴더 구조 (safety-walk-map 기준)
├─ data/processed/   광진구_안전시설_통합.csv, safety_score_result.csv, gwangjin.graphml
├─ route/             shortest_safety_route.py   (가인)
└─ frontend/map.py    이 파일                     (지아)
"""

import os
import sys
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import FastMarkerCluster
import pandas as pd
import streamlit as st

# ===== 경로 설정 =====
# 이 파일(frontend/map.py) 위치를 기준으로 절대경로를 잡아서
# streamlit을 어느 위치에서 실행하든(cwd와 무관하게) 항상 같은 파일을 찾도록 함
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(REPO_ROOT, "data", "processed")
ROUTE_DIR = os.path.join(REPO_ROOT, "route")

if ROUTE_DIR not in sys.path:
    sys.path.append(ROUTE_DIR)

# [백엔드 모듈 임포트] 가인이 구현한 실제 경로 알고리즘 모듈
try:
    from shortest_safety_route import (
        load_graph,
        load_safety_grid,
        attach_safety_scores,
        find_route,
        visualize as route_visualize,
    )
    ROUTE_MODULE_LOADED = True
    ROUTE_LOAD_ERROR = None
except ImportError as e:
    ROUTE_MODULE_LOADED = False
    ROUTE_LOAD_ERROR = str(e)

    def load_graph():
        raise NotImplementedError("route/shortest_safety_route.py 파일을 찾을 수 없음.")

    def load_safety_grid():
        raise NotImplementedError("route/shortest_safety_route.py 파일을 찾을 수 없음.")

    def attach_safety_scores(G, grid):
        return G

    def find_route(*args, **kwargs):
        return {}

    def route_visualize(*args, **kwargs):
        return create_base_map()


STANDARD_COLUMNS = {
    "lat": "위도",
    "lng": "경도",
    "type": "시설유형",   # "CCTV", "가로등", "비상벨", "파출소", "지구대", "경찰서"
    "address": "주소",
}

INTEGRATED_CSV_FILENAME = "광진구_안전시설_통합.csv"
SAFETY_SCORE_CSV_FILENAME = "safety_score_result.csv"
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
    filepath = os.path.join(file_dir, INTEGRATED_CSV_FILENAME)
    if not os.path.exists(filepath):
        return pd.DataFrame(columns=list(STANDARD_COLUMNS.values()))

    df = _read_csv_with_fallback_encoding(filepath)
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]

    lat_col, lng_col, type_col = (
        STANDARD_COLUMNS["lat"],
        STANDARD_COLUMNS["lng"],
        STANDARD_COLUMNS["type"],
    )

    df = df.dropna(subset=[lat_col, lng_col])
    keep_cols = [c for c in STANDARD_COLUMNS.values() if c in df.columns]
    df = df[keep_cols].copy()

    return df.reset_index(drop=True)


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


GWANGJIN_CENTER = [37.5384, 127.0822]


def create_base_map(center=GWANGJIN_CENTER, zoom_start=14) -> folium.Map:
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="CartoDB positron",
    )
    return m


@st.cache_data(show_spinner="지도 렌더링 중...")
def build_facility_map(_df_placeholder_unused, selected_types: tuple, data_dir: str, center: tuple, zoom_start: int):
    df = load_all_facilities(data_dir)
    type_col = STANDARD_COLUMNS["type"]
    filtered_df = df[df[type_col].isin(selected_types)]

    m = create_base_map(center=list(center), zoom_start=zoom_start)
    m = add_facility_layers(m, filtered_df)
    return m, len(filtered_df), len(df)


CLUSTER_THRESHOLD = 50

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


def geocode_address(address: str):
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
    folium.Marker(
        location=[lat, lng],
        popup=label,
        tooltip=label,
        icon=folium.Icon(color="green", icon="star", prefix="fa"),
    ).add_to(m)
    folium.Circle(
        location=[lat, lng],
        radius=50,
        color="green",
        fill=True,
        fill_opacity=0.15,
    ).add_to(m)
    return m


# ===== 경로 추천용 백엔드 리소스 로딩 (그래프 + 안전지수 그리드) =====
# route.py의 load_graph()/load_safety_grid()는 파일명을 상대경로("gwangjin.graphml",
# "safety_score_result.csv")로만 참조하므로, 호출 직전에 cwd를 data/processed로
# 잠깐 옮겼다가 원래 위치로 복귀시킴. 무거운 작업이라 cache_resource로 앱 실행 중 1회만 로드함.
@st.cache_resource(show_spinner="보행 네트워크 그래프 및 안전지수 불러오는 중... (최초 1회, 다소 시간 걸릴 수 있음)")
def load_route_resources():
    prev_cwd = os.getcwd()
    try:
        os.chdir(DATA_DIR)
        G = load_graph()
        grid = load_safety_grid()
        G = attach_safety_scores(G, grid)
    finally:
        os.chdir(prev_cwd)
    return G, grid


def run_streamlit_app():
    import streamlit as st
    from streamlit_folium import st_folium

    st.set_page_config(page_title="광진구 안전지도", layout="wide")
    st.title("광진구 안전지수 지도 및 경로 추천 서비스")

    tab1, tab2, tab3 = st.tabs(["지도", "안전지수", "경로 추천"])

    with tab1:
        st.subheader("시설 위치 지도")

        df = load_all_facilities(DATA_DIR)

        all_types = sorted(df[STANDARD_COLUMNS["type"]].unique().tolist())
        selected_types = st.sidebar.multiselect(
            "표시할 시설유형 선택", options=all_types, default=all_types
        )

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

        st_folium(m, use_container_width=True, height=600, returned_objects=[])

    with tab2:
        st.subheader("광진구 500m 격자별 안전지수 히트맵")
        st.info("안전지수 산출 결과 데이터 연동 완료함.")

        grid_csv_path = os.path.join(DATA_DIR, SAFETY_SCORE_CSV_FILENAME)

        if os.path.exists(grid_csv_path):
            grid_df = pd.read_csv(grid_csv_path)
            st.dataframe(grid_df.head(10), use_container_width=True)
            st.success(f"안전지수 데이터 로드 성공 ({grid_csv_path})")
        else:
            st.warning(f"지정된 경로에 파일이 없음: {grid_csv_path}")
            st.caption("data/processed 폴더 안에 safety_score_result.csv 파일이 있는지 확인 바람.")

    with tab3:
        st.subheader("안전 우선 경로 추천")
        st.caption("최단 거리 경로와 안전 가중치가 반영된 안전 경로를 비교하여 안내함.")

        if not ROUTE_MODULE_LOADED:
            st.error(
                "경로 알고리즘 모듈(route/shortest_safety_route.py)을 불러오지 못함. "
                f"에러 내용: {ROUTE_LOAD_ERROR}"
            )
            st.stop()

        alpha_val = st.slider(
            "안전 가중치 튜닝 (α)",
            min_value=0,
            max_value=30,
            value=12,
            step=1,
            help="0 = 시간/거리만 최적화, 값이 클수록 안전시설 밀도가 낮은 구간에 더 큰 페널티를 부여함 (기본값 12)",
        )

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
                    with st.spinner("경로 탐색 알고리즘 실행 중임..."):
                        try:
                            G, grid = load_route_resources()

                            result = find_route(
                                G,
                                orig_lat=start_loc[0],
                                orig_lon=start_loc[1],
                                dest_lat=end_loc[0],
                                dest_lon=end_loc[1],
                                alpha=alpha_val,
                            )

                            fast_route = result["fast"]
                            safe_route = result["safe"]

                            # route.py가 제공하는 시각화 함수를 그대로 사용
                            # (최단=파랑 실선 / 안전=초록 대시선 + 출발/도착 마커 + 범례 포함)
                            route_map = route_visualize(fast_route, safe_route, safety_grid=grid)

                            st_folium(route_map, use_container_width=True, height=500, returned_objects=[])

                            m1, m2 = st.columns(2)
                            with m1:
                                st.markdown("**최단 경로**")
                                st.metric("거리", f"{fast_route['distance_m']:.0f} m")
                                st.metric("예상 시간", f"{fast_route['time_min']:.1f} 분")
                            with m2:
                                st.markdown("**안전 경로**")
                                st.metric("거리", f"{safe_route['distance_m']:.0f} m")
                                st.metric("예상 시간", f"{safe_route['time_min']:.1f} 분")

                            increase_pct = result["time_increase_ratio"] * 100
                            recommended_label = "안전 경로" if result["recommended"] == "safe" else "최단 경로"

                            st.info(
                                f"안전 경로는 최단 경로 대비 시간이 약 {increase_pct:.1f}% 증가함. "
                                f"추천 경로: **{recommended_label}**"
                            )
                            st.success("경로 탐색이 완료됨.")

                        except Exception as e:
                            st.error(f"경로 탐색 중 오류가 발생함: {e}")


if __name__ == "__main__":
    run_streamlit_app()
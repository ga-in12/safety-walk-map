"""
지도 시각화 및 UI 골격 코드
지도(folium) + UI(streamlit)
"""

import os
import sys
import math
import folium
from folium import FeatureGroup, LayerControl
from folium.plugins import FastMarkerCluster
import pandas as pd
import streamlit as st

# ===== 경로 설정 =====

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(REPO_ROOT, "data", "processed")
RAW_DATA_DIR = os.path.join(REPO_ROOT, "data", "raw")  # 광진구_안전시설_통합.csv 위치
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
SAFETY_GRID_GEOJSON_FILENAME = "gwangjin_safety_grid.geojson"
ENCODING_CANDIDATES = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]

# final_safety_score.py(신영)가 저장하는 결과물 위치
# - data/processed/safety_score_result.csv : 격자별 안전점수 표
# - outputs/gwangjin_safety_grid.geojson   : 격자 폴리곤 도형(등급 포함)
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs")

# final_safety_score.py의 grade_color_dict와 동일하게 맞춤
GRADE_COLOR_MAP = {
    "A": "green",
    "B": "yellowgreen",
    "C": "yellow",
    "D": "orange",
    "E": "red",
}


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


# ===== tab2: 안전지수 격자 지도 =====
# safety_score/final_safety_score.py가 미리 계산해서 저장해 둔 geojson을 그대로 읽어서
# 그린다. 이 안에서 격자 폴리곤을 다시 계산하지 않음(그 스크립트를 다시 돌리면 매우 무거움).
@st.cache_data(show_spinner="안전지수 격자 데이터 불러오는 중...")
def load_safety_grid_geojson(path: str):
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# final_safety_score.py의 make_grid_information_html과 동일한 항목 순서로 맞춤
GRID_TOOLTIP_FIELDS = [
    "score_grade",
    "safety_score",
    "cctv_count",
    "streetlight_count",
    "emergency_bell_count",
    "police_station_count",
    "police_box_count",
    "police_substation_count",
    "total_facility_count",
]
GRID_TOOLTIP_ALIASES = [
    "안전등급:",
    "안전점수:",
    "CCTV:",
    "가로등:",
    "비상벨:",
    "경찰서:",
    "파출소:",
    "지구대:",
    "전체 시설:",
]


def build_safety_grid_map(geojson_path: str, center=GWANGJIN_CENTER, zoom_start: int = 13) -> folium.Map:
    m = create_base_map(center=center, zoom_start=zoom_start)
    geojson_data = load_safety_grid_geojson(geojson_path)

    folium.GeoJson(
        data=geojson_data,
        name="안전등급 격자",
        style_function=lambda feature: {
            "fillColor": feature["properties"].get("grade_color", "gray"),
            "color": "gray",
            "weight": 0.6,
            "fillOpacity": 0.5,
        },
        highlight_function=lambda feature: {
            "color": "black",
            "weight": 2,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=GRID_TOOLTIP_FIELDS,
            aliases=GRID_TOOLTIP_ALIASES,
            sticky=True,
            labels=True,
            style=(
                "background-color: white; color: #222222; "
                "border: 1px solid #777777; border-radius: 5px; "
                "box-shadow: 0 1px 4px rgba(0,0,0,0.25); padding: 7px; font-size: 13px;"
            ),
        ),
        popup=folium.GeoJsonPopup(
            fields=GRID_TOOLTIP_FIELDS,
            aliases=GRID_TOOLTIP_ALIASES,
            max_width=260,
        ),
        smooth_factor=0,
    ).add_to(m)

    m = add_grade_legend(m)
    LayerControl(collapsed=False).add_to(m)
    return m


def add_grade_legend(m: folium.Map) -> folium.Map:
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background-color: white; border: 1px solid #777777; border-radius: 5px;
                padding: 10px 12px; font-size: 13px; line-height: 1.6;
                box-shadow: 0 1px 4px rgba(0,0,0,0.25);">
        <b>안전등급</b><br>
        <span style="color: green;">■</span> A<br>
        <span style="color: yellowgreen;">■</span> B<br>
        <span style="color: #d4c500;">■</span> C<br>
        <span style="color: orange;">■</span> D<br>
        <span style="color: red;">■</span> E
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


# ===== tab2 폴백: geojson 없이 CSV만으로 격자 지도 그리기 =====
# safety_score_result.csv에는 center_lat/center_lng/grid_size_m이 이미 들어있으므로
# geopandas/shapely 없이도 위경도 근사 변환만으로 정사각형을 그릴 수 있음.
# 다만 광진구 경계선에 맞춘 정밀한 clipping은 하지 않고 정사각형 그대로 그림
# (geojson이 생기면 build_safety_grid_map()이 더 정확한 버전이니 그쪽이 우선됨).
_METERS_PER_LAT_DEGREE = 111_320.0


def _half_cell_lat_lng_delta(half_size_m: float, lat_deg: float) -> tuple:
    lat_delta = half_size_m / _METERS_PER_LAT_DEGREE
    lng_delta = half_size_m / (_METERS_PER_LAT_DEGREE * math.cos(math.radians(lat_deg)))
    return lat_delta, lng_delta


def _grid_row_tooltip_html(row: pd.Series) -> str:
    def _get(col, default=0):
        return row[col] if col in row and pd.notna(row[col]) else default

    return f"""
    <div style="min-width: 190px; font-size: 13px; line-height: 1.55;">
        <div style="font-size: 14px; margin-bottom: 4px;"><b>격자 {int(_get('grid_id', 0))}번</b></div>
        안전등급: <b>{_get('score_grade', '-')}</b><br>
        안전점수: <b>{float(_get('safety_score', 0)):.1f}점</b><br>
        <hr style="margin: 5px 0; border: 0; border-top: 1px solid #bbbbbb;">
        CCTV: {int(_get('cctv_count'))}개<br>
        가로등: {int(_get('streetlight_count'))}개<br>
        비상벨: {int(_get('emergency_bell_count'))}개<br>
        경찰서: {int(_get('police_station_count'))}개<br>
        파출소: {int(_get('police_box_count'))}개<br>
        지구대: {int(_get('police_substation_count'))}개<br>
        <b>전체 시설: {int(_get('total_facility_count'))}개</b>
    </div>
    """


@st.cache_data(show_spinner="안전지수 격자 지도 그리는 중... (CSV 기반)")
def build_safety_grid_map_from_csv(csv_path: str, center=GWANGJIN_CENTER, zoom_start: int = 13):
    df = pd.read_csv(csv_path)
    m = create_base_map(center=center, zoom_start=zoom_start)
    layer = FeatureGroup(name="안전등급 격자", show=True)

    for _, row in df.iterrows():
        lat, lng = row["center_lat"], row["center_lng"]
        size_m = row["grid_size_m"] if "grid_size_m" in row and pd.notna(row["grid_size_m"]) else 500
        lat_delta, lng_delta = _half_cell_lat_lng_delta(size_m / 2, lat)
        bounds = [[lat - lat_delta, lng - lng_delta], [lat + lat_delta, lng + lng_delta]]

        html = _grid_row_tooltip_html(row)
        grade_color = row["grade_color"] if "grade_color" in row and pd.notna(row["grade_color"]) else "gray"

        folium.Rectangle(
            bounds=bounds,
            color="gray",
            weight=0.6,
            fill=True,
            fill_color=grade_color,
            fill_opacity=0.5,
            tooltip=folium.Tooltip(html, sticky=True),
            popup=folium.Popup(html, max_width=260),
        ).add_to(layer)

    layer.add_to(m)
    m = add_grade_legend(m)
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
        # route.py(shortest_safety_route.py)가 "data/processed/..." 형태로
        # 저장소 루트 기준 상대경로를 쓰고 있어서, cwd를 REPO_ROOT로 맞춰줘야 함
        os.chdir(REPO_ROOT)
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

        df = load_all_facilities(RAW_DATA_DIR)

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
            None, tuple(sorted(selected_types)), RAW_DATA_DIR, tuple(map_center), zoom
        )
        st.sidebar.caption(f"표시 중인 데이터: {shown_count}건 / 전체 {total_count}건")

        if user_location:
            m = add_user_location_marker(m, user_location[0], user_location[1])

        st_folium(m, use_container_width=True, height=600, returned_objects=[])

    with tab2:
        st.subheader("광진구 500m 격자별 안전지수 지도")
        st.caption("격자에 마우스를 올리면 안전등급·안전점수·시설유형별 개수를 확인할 수 있음.")

        grid_geojson_path = os.path.join(OUTPUTS_DIR, SAFETY_GRID_GEOJSON_FILENAME)
        grid_csv_path = os.path.join(DATA_DIR, SAFETY_SCORE_CSV_FILENAME)

        if os.path.exists(grid_geojson_path):
            safety_map = build_safety_grid_map(grid_geojson_path)
            st_folium(safety_map, use_container_width=True, height=600, returned_objects=[])
            st.success(f"안전지수 격자 지도 로드 성공 ({grid_geojson_path})")

            if os.path.exists(grid_csv_path):
                with st.expander("격자별 원본 데이터 표로 보기"):
                    grid_df = pd.read_csv(grid_csv_path)
                    st.dataframe(grid_df, use_container_width=True)
        elif os.path.exists(grid_csv_path):
            # geojson이 아직 없으면 CSV의 center_lat/center_lng/grid_size_m으로
            # 정사각형 격자를 직접 그림 (경계선 clipping은 안 됨)
            st.caption(
                "격자 도형 파일(outputs/gwangjin_safety_grid.geojson)이 아직 없어서 "
                "CSV 좌표로 정사각형 격자를 그림. 경계선에 딱 맞게 잘린 형태는 아님."
            )
            safety_map = build_safety_grid_map_from_csv(grid_csv_path)
            st_folium(safety_map, use_container_width=True, height=600, returned_objects=[])
            st.success(f"안전지수 격자 지도 로드 성공 (CSV 기반, {grid_csv_path})")

            with st.expander("격자별 원본 데이터 표로 보기"):
                grid_df = pd.read_csv(grid_csv_path)
                st.dataframe(grid_df, use_container_width=True)
        else:
            st.warning(f"안전지수 결과 파일이 없음: {grid_csv_path}")
            st.caption(
                "data/processed 폴더 안에 safety_score_result.csv, "
                "outputs 폴더 안에 gwangjin_safety_grid.geojson 파일이 있는지 확인 바람."
            )

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
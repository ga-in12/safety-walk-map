"""
지도 시각화 및 UI 골격 코드
지도(folium) + UI(streamlit)
실데이터가 들어오기 전 단계의 골격 코드입니다!
더미 좌표로 동작 테스트가 가능하며, 실제 통합 CSV가 오면 맞출 예정
"""

import folium
from folium import FeatureGroup, LayerControl
import pandas as pd


# 컬럼명 표준화 (데이터 파트의 전처리 끝나면 수정할 예정)

STANDARD_COLUMNS = {
    "lat": "위도",
    "lng": "경도",
    "type": "시설유형",   # 예: "CCTV", "가로등", "비상벨", "파출소"
    "address": "주소",
}

# 원본 CSV별 실제 컬럼명 -> 표준 컬럼명 매핑
# 경찰서/지구대·파출소 2개는 현재 위경도가 없는 버전이며, 데이터 담당이 위경도 포함 버전으로 다시 줄 예정 -> 그때 위도/경도 키만 추가하면 됨
RAW_COLUMN_MAP = {
    "CCTV정보_서울광진구.csv": {
        "WGS84위도": "위도",
        "WGS84경도": "경도",
        "소재지도로명주소": "주소",
    },
    "안전비상벨위치정보_서울광진구.csv": {
        "WGS84위도": "위도",
        "WGS84경도": "경도",
        "소재지도로명주소": "주소",
    },
    "서울특별시_광진구_가로등_위치정보_20220214.csv": {
        "위도": "위도",
        "경도": "경도",
        # 주소 컬럼 없음 (필요시 역지오코딩)
    },
    "경찰청_전국_지구대_파출소_주소_현황_20251231.csv": {
        "주소": "주소",
        # TODO: 데이터 담당이 위경도 포함 버전 전달 시 아래 주석 해제하고
        # 실제 컬럼명에 맞게 수정
        # "위도": "위도",
        # "경도": "경도",
    },
    "경찰청_전국_경찰서_명칭_및_주소_20230627.csv": {
        "경찰서주소": "주소",
        # TODO: 데이터 담당이 위경도 포함 버전 전달 시 아래 주석 해제하고
        # 실제 컬럼명에 맞게 수정
        # "위도": "위도",
        # "경도": "경도",
    },
}

# 원본 CSV에 시설유형 컬럼이 없는 경우 고정으로 부여할 값
FIXED_FACILITY_TYPE = {
    "CCTV정보_서울광진구.csv": "CCTV",
    "안전비상벨위치정보_서울광진구.csv": "비상벨",
    "서울특별시_광진구_가로등_위치정보_20220214.csv": "가로등",
    # 지구대/파출소는 원본에 "구분" 컬럼이 있어 그대로 사용 (지구대/파출소)
    # 경찰서는 시설유형 컬럼이 없어 고정값 사용
    "경찰청_전국_경찰서_명칭_및_주소_20230627.csv": "경찰서",
}


def standardize_columns(df: pd.DataFrame, source_filename: str) -> pd.DataFrame:
    col_map = RAW_COLUMN_MAP.get(source_filename, {})
    df = df.rename(columns=col_map)

    if STANDARD_COLUMNS["type"] not in df.columns:
        fixed_type = FIXED_FACILITY_TYPE.get(source_filename)
        if fixed_type:
            df[STANDARD_COLUMNS["type"]] = fixed_type
        elif "구분" in df.columns:
            df[STANDARD_COLUMNS["type"]] = df["구분"]  # 지구대/파출소 케이스

    return df


def load_all_facilities(file_dir: str) -> pd.DataFrame:
    import os

    all_dfs = []
    for filename, col_map in RAW_COLUMN_MAP.items():
        filepath = os.path.join(file_dir, filename)
        if not os.path.exists(filepath):
            continue

        df = pd.read_csv(filepath, encoding="cp949")
        df = standardize_columns(df, filename)

        lat_col, lng_col = STANDARD_COLUMNS["lat"], STANDARD_COLUMNS["lng"]
        if lat_col in df.columns and lng_col in df.columns:
            df = df.dropna(subset=[lat_col, lng_col])
            keep_cols = [c for c in STANDARD_COLUMNS.values() if c in df.columns]
            all_dfs.append(df[keep_cols])
        else:
            print(f"[안내] {filename}: 위경도 없음 -> 일단 제외 (데이터 담당 업데이트 대기)")

    if not all_dfs:
        return pd.DataFrame(columns=list(STANDARD_COLUMNS.values()))

    return pd.concat(all_dfs, ignore_index=True)


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


# FeatureGroup + LayerControl 골격
def add_facility_layers(m: folium.Map, df: pd.DataFrame) -> folium.Map:
    """시설유형별 FeatureGroup을 만들고 지도에 마커를 추가한 뒤
    LayerControl로 ON/OFF 토글 기능을 붙입니다.

    df는 STANDARD_COLUMNS 기준 컬럼(위도, 경도, 시설유형, 주소)을
    가지고 있다고 가정합니다.
    """
    facility_types = df[STANDARD_COLUMNS["type"]].unique()
    layers = {}

    for f_type in facility_types:
        layers[f_type] = FeatureGroup(name=f_type, show=True)

    for _, row in df.iterrows():
        f_type = row[STANDARD_COLUMNS["type"]]
        style = get_marker_style(f_type)

        popup_text = f"{f_type}"
        if STANDARD_COLUMNS["address"] in df.columns:
            popup_text += f"<br>{row[STANDARD_COLUMNS['address']]}"

        marker = folium.Marker(
            location=[row[STANDARD_COLUMNS["lat"]], row[STANDARD_COLUMNS["lng"]]],
            popup=popup_text,
            icon=folium.Icon(
                color=style["color"],
                icon=style["icon"],
                prefix=style["prefix"],
            ),
        )
        marker.add_to(layers[f_type])

    for layer in layers.values():
        layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)
    return m


def build_dummy_data() -> pd.DataFrame:
    """실데이터 도착 전 테스트용 더미 데이터"""
    data = [
        {"위도": 37.5400, "경도": 127.0830, "시설유형": "CCTV", "주소": "테스트 주소1"},
        {"위도": 37.5420, "경도": 127.0810, "시설유형": "가로등", "주소": "테스트 주소2"},
        {"위도": 37.5370, "경도": 127.0850, "시설유형": "비상벨", "주소": "테스트 주소3"},
        {"위도": 37.5390, "경도": 127.0795, "시설유형": "파출소", "주소": "테스트 주소4"},
    ]
    return pd.DataFrame(data)


# Streamlit 앱 골격 (3주차에 본격 작업, 틀만 미리 준비)
def run_streamlit_app():
    """streamlit run map_ui_skeleton.py 로 실행해서 확인 가능"""
    import streamlit as st
    from streamlit_folium import st_folium

    st.set_page_config(page_title="광진구 안전지도", layout="wide")
    st.title("광진구 안전지수 지도")

    tab1, tab2, tab3 = st.tabs(["지도", "안전지수", "경로 추천"])

    with tab1:
        st.subheader("시설 위치 지도")

        # 위경도가 있는 CSV들만 자동으로 합쳐서 로드.
        # 데이터 담당이 경찰서/지구대·파출소 위경도 버전을 주면
        # 같은 파일명으로 DATA_DIR에 넣기만 하면 자동 포함될 예정임
        DATA_DIR = "."  # CSV들이 위치한 폴더로 수정
        df = load_all_facilities(DATA_DIR)

        if df.empty:
            st.warning("위경도가 있는 데이터가 아직 없어 더미 데이터로 표시합니다.")
            df = build_dummy_data()

        m = create_base_map()
        m = add_facility_layers(m, df)
        st_folium(m, width=1000, height=600)

    with tab2:
        st.subheader("안전지수 히트맵 (안전지수 파트 연동 예정)")
        st.info("안전지수 파트 결과물 연동 대기 중")

    with tab3:
        st.subheader("안전 우선 경로 추천 (경로 파트 연동 예정)")
        st.info("경로 추천 파트 결과물 연동 대기 중")


if __name__ == "__main__":
    run_streamlit_app()
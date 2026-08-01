# safety-walk-map

# 공공데이터 기반 보행 안전시설 시각화 및 안전경로 추천 웹서비스

> 세종대학교 2026-하계 창의학기제 | AI로봇학과 · 자기주도창의전공Ⅰ

귀갓길·야간 보행 시 골목길 안전 불안감을 공공데이터로 해결하는 웹서비스 
가로등·CCTV·비상벨·파출소 위치를 반영한 **안전지수 계산**과 **안전 우선 경로 추천** 기능을 제공

---

## 기술 스택

| | 기술 |
|--|------|
| UI / 서버 | `Streamlit` |
| 지도 | `Folium` · `streamlit-folium` |
| 데이터 처리 | `pandas` |
| 경로 탐색 | `OSMnx` · `NetworkX` |

---

## 파트 구성

| 파트 | 담당 기능 |
|------|-----------|
| 데이터 | 공공데이터 수집 · pandas 전처리 · 통합 CSV 생성 |
| 지도 | Folium 마커 · 레이어 · Streamlit UI |
| 안전지수 | 반경 1km 가중합산 · 히트맵 · A~E 등급 |
| 경로 | OSMnx 도로 그래프 · Dijkstra 안전경로 추천 |

## 데이터 출처

| 데이터 | 출처 | 담당 기관 | URL | 데이터 기준일 | 다운로드 날짜 |
|---|---|---|---|---|---|
| CCTV | 행정안전부 LocalData | 개인정보보호위원회 신기술개인정보과 | https://file.localdata.go.kr/file/emergency_call_box_info/info | 2025.11.27 | 2026.06.29 |
| 비상벨 | 행정안전부 LocalData | 국토교통부 주택정비과 | https://file.localdata.go.kr/file/cctv_info/info | 2025.11.27 | 2026.06.29 |
| 경찰서 | 공공데이터포털 | 경찰청 기획조정관실 혁신기획조정관 | https://www.data.go.kr/data/15124966/fileData.do | 2025.05.02 | 2026.06.29 |
| 파출소 | 공공데이터포털 | 경찰청 범죄예방대응국 지역경찰운영과 | https://www.data.go.kr/data/15077036/fileData.do | 2026.02.19 | 2026.06.29 |
| 가로등(광진구) | 공공데이터포털 | 서울특별시 광진구 스마트정보과 | https://www.data.go.kr/data/15070592/fileData.do | 2025.07.29 | 2026.06.29 |
| 가로등(서울시) | 공공데이터포털 | 서울특별시 데이터전략과 | https://www.data.go.kr/data/15107934/fileData.do | 2025.11.20 | 2026.07.13 |

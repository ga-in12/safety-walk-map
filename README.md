# 광진구 안전보행 경로 추천 서비스

> 공공 안전시설 데이터를 기반으로 광진구의 지역별 안전지수를 계산하고,  
> 일반 최단경로와 안전성을 고려한 보행 경로를 함께 제공하는 웹서비스

## 프로젝트 소개

본 프로젝트는 귀갓길과 야간 보행 시 느끼는 불안감을 줄이기 위해 제작한 공공데이터 기반 보행 안전 서비스입니다.

광진구 내 CCTV, 가로등, 비상벨, 경찰서, 지구대, 파출소 데이터를 통합하고, 광진구를 500m 격자로 나누어 각 지역의 상대적인 안전지수를 계산합니다.

계산된 안전지수는 OpenStreetMap 보행 도로망에 반영되며, 사용자는 출발지와 도착지를 입력해 다음 두 경로를 비교할 수 있습니다.

- 이동시간을 우선한 일반 최단경로
- 안전점수가 낮은 구간에 페널티를 적용한 안전경로

  
## safety-walk-map — 광진구 보행자 안전 지도

**배포 링크**: https://gwangjin-safety-map.streamlit.app/

---

## 주요 기능

### 안전시설 시각화

- 광진구 내 CCTV, 가로등, 안전비상벨, 지구대(경찰시설) 등 공공데이터 기반 안전시설 위치를 지도에 시각화
- 격자(grid) 단위로 안전 점수를 산출하여 등급(A~E)별로 색상 구분 표시
- Folium 기반 인터랙티브 지도로 확대/축소, 클릭을 통한 상세 정보 확인 가능

### 안전 경로 추천

- OSMnx 기반 보행자 도로 네트워크를 활용한 경로 탐색
- **최단 경로**와 **안전 최적 경로**(안전 점수를 가중치로 반영) 두 가지를 비교 제공
- 안전 경로가 최단 경로보다 소요 시간이 일정 수준(15%) 이상 늘어나지 않는 선에서 추천 여부 결정
- BallTree(최근접 이웃 탐색) 알고리즘으로 도로 네트워크 노드에 안전 점수를 빠르게 매핑

### 위치 입력 방식

- 주소 검색을 통한 좌표 변환 (Geopy/Nominatim geocoding)
- 지도 클릭을 통한 출발지/도착지 직접 선택

### 안전 점수 산정

- 공공데이터 기반 격자별 안전 점수 계산 및 등급화 (A~E 등급)
- CCTV, 가로등, 비상벨, 지구대 개수 등을 종합한 안전 스코어링 모델
---

## 실행 화면

### 안전시설 지도
<img width="1895" height="811" alt="image" src="https://github.com/user-attachments/assets/37b97e6d-ac71-48e6-9958-66e62bf0740f" />


### 안전지수 지도
<img width="1876" height="777" alt="image" src="https://github.com/user-attachments/assets/a0cee1e9-20de-460a-a947-abc694184b9b" />


### 안전경로 추천
<img width="969" height="494" alt="image" src="https://github.com/user-attachments/assets/a675917f-3180-4f33-9d08-b774eca3c335" />


---

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| 언어 | Python 3.13 |
| 개발 환경 | Visual Studio Code |
| 웹 UI | Streamlit |
| 지도 연동 | streamlit-folium |
| 지도 시각화 | Folium |
| 데이터 처리 | pandas, NumPy |
| 공간 데이터 처리 | GeoPandas, Shapely, PyProj |
| 보행 도로망 | OSMnx |
| 그래프 탐색 | NetworkX |
| 최근접 격자 탐색 | scikit-learn BallTree |
| 주소 좌표 변환 | GeoPy Nominatim |
| 지도 데이터 | OpenStreetMap |

정확한 라이브러리 버전은 저장소의 `requirements.txt`에서 확인할 수 있습니다.

---

## 프로젝트 구조

```text
safety-walk-map/
│
├── data/
│   ├── raw/
│   │   ├── 광진구_주변지역_안전시설_통합.csv
│   │   └── boundary/
│   │       └── lgldong/
│   │           ├── admstr_zone_lgldong_bndry_24.shp
│   │           ├── admstr_zone_lgldong_bndry_24.dbf
│   │           ├── admstr_zone_lgldong_bndry_24.shx
│   │           └── admstr_zone_lgldong_bndry_24.prj
│   │
│   └── processed/
│       ├── 광진구_안전시설_통합.csv
│       ├── safety_score_result.csv
│       └── gwangjin.graphml
│
├── frontend/
│   └── map.py
│
├── safety_score/
│   └── grid_safety_score.py
│
├── route/
│   └── shortest_safety_route.py
│
├── outputs/
│   ├── gwangjin_safety_map.html
│   ├── route_map.html
│   ├── gwangjin_safety_grid.geojson
│   └── gwangjin_facilities.geojson
│
├── requirements.txt
├── README.md
└── .gitignore
```

### 폴더 설명

| 폴더 | 설명 |
| --- | --- |
| `data/raw` | 공공데이터와 행정구역 경계 등 원본 데이터 |
| `data/processed` | 전처리된 시설 데이터, 안전지수 결과, 보행 그래프 |
| `frontend` | Streamlit 기반 사용자 인터페이스 |
| `safety_score` | 격자 생성, 시설 영향값 및 안전점수 계산 |
| `route` | 최단경로와 안전경로 탐색 |
| `outputs` | 실행 후 생성된 HTML 및 GeoJSON 결과물 |

---

## 안전지수 산정 방식

### 1. 격자 생성

광진구 전체 영역에 500m × 500m 크기의 격자를 생성합니다.

광진구 행정구역 경계와 겹치는 격자만 안전지수 계산 대상으로 사용하며, 지도에 표시할 때는 광진구 경계에 맞게 격자를 잘라서 표현합니다.

### 2. 활용 시설

안전지수 계산에는 다음 시설을 사용합니다.

- CCTV
- 가로등
- 비상벨
- 경찰서
- 파출소
- 지구대

### 3. 시설별 가중치

| 시설 | 가중치 |
| --- | ---: |
| 가로등 | 40 |
| CCTV | 30 |
| 파출소 | 12 |
| 지구대 | 10 |
| 비상벨 | 5 |
| 경찰서 | 3 |
| 합계 | 100 |

가로등과 CCTV는 범죄예방 효과 관련 선행자료를 참고하여 상대적으로 높은 가중치를 부여하였으며, 비상벨은 직접적인 범죄 감소 효과가 제한적이라는 점을 고려해 낮은 가중치를 적용하였습니다.

### 4. 거리감쇠

격자 안에 존재하는 시설은 영향값 `1.0`으로 반영합니다.

격자 바깥에 있더라도 격자 경계에서 50m 이내에 위치한 시설은 거리가 가까울수록 높은 영향값을 부여합니다.

현재 코드에서는 다음 선형 거리감쇠식을 사용합니다.

```text
시설 영향값 = max(0, 1 - 격자 경계와의 거리 / 50)
```

예시는 다음과 같습니다.

| 격자 경계와의 거리 | 시설 영향값 |
| ---: | ---: |
| 격자 내부 | 1.0 |
| 격자 외부 10m | 0.8 |
| 격자 외부 20m | 0.6 |
| 격자 외부 30m | 0.4 |
| 격자 외부 40m | 0.2 |
| 격자 외부 50m 이상 | 0.0 |

이를 통해 격자 경계 바로 밖에 있는 시설의 영향이 완전히 제외되는 경계효과를 줄였습니다.

### 5. 시설별 만점 기준

CCTV, 가로등, 비상벨처럼 여러 개가 밀집해 설치되는 시설은 전체 격자 영향값 분포의 90백분위수를 만점 기준으로 사용합니다.

```text
시설 점수 비율 = min(시설 영향값 / 시설별 만점 기준, 1)
```

경찰서, 파출소, 지구대처럼 개수가 적은 희소시설은 시설 1개의 완전한 영향값인 `1.0`을 만점 기준으로 사용합니다.

### 6. 최종 안전점수

각 시설의 점수 비율에 가중치를 곱한 뒤 모두 합산합니다.

```text
안전점수
= Σ(시설별 가중치 × 시설별 점수 비율)
```

최종 안전점수는 0점에서 100점 사이로 계산됩니다.

### 7. A~E 안전등급

전체 격자의 안전점수 분포를 기준으로 20%씩 나누어 상대등급을 부여합니다.

| 등급 | 기준 |
| --- | --- |
| A | 상위 20% |
| B | 상위 20~40% |
| C | 상위 40~60% |
| D | 상위 60~80% |
| E | 하위 20% |

따라서 이 등급은 절대적인 범죄 위험도를 의미하는 것이 아니라, 광진구 내 격자 간 상대적인 안전시설 분포를 나타냅니다.

---

## 안전경로 산정 방식

### 1. 보행 도로망 생성

OSMnx를 이용하여 광진구의 OpenStreetMap 보행 도로망을 불러옵니다.

저장된 `gwangjin.graphml` 파일이 있으면 이를 재사용하고, 파일이 없으면 OpenStreetMap에서 새로운 보행 그래프를 내려받아 저장합니다.

### 2. 도로 노드와 안전점수 연결

각 보행 도로 노드에 가장 가까운 안전지수 격자를 BallTree로 탐색하고, 해당 격자의 안전점수를 도로 노드에 연결합니다.

### 3. 안전 가중치 계산

도로 구간 양 끝 노드의 평균 안전점수를 계산하고, 안전점수가 낮을수록 이동비용이 증가하도록 페널티를 적용합니다.

```text
안전 페널티 = (100 - 평균 안전점수) / 100

안전 경로 비용
= 이동시간 × (1 + α × 안전 페널티)
```

`α` 값이 커질수록 안전점수가 낮은 도로를 피하는 정도가 커집니다.

기본값은 다음과 같습니다.

```text
α = 12
```

### 4. 경로 추천

다음 두 경로를 각각 계산합니다.

- 최단경로: 이동시간 최소화
- 안전경로: 안전 페널티가 적용된 이동비용 최소화

안전경로의 이동시간이 최단경로보다 15% 이내로 증가하면 안전경로를 추천하고, 15%를 초과하면 최단경로를 추천합니다.

```text
추천 기준 = 최단경로 대비 시간 증가율 15%
```

---

## 설치 및 실행 방법

### 1. 저장소 복제

```bash
git clone https://github.com/likelion-project-README/README.git
cd safety-walk-map
```

저장소 주소가 변경된 경우 실제 GitHub 저장소 주소로 수정해야 합니다.

### 2. Python 버전 확인

```bash
python --version
```

본 프로젝트의 개발 및 실행 환경은 Python 3.13입니다.

### 3. 가상환경 생성

```bash
python -m venv venv
```

### 4. 가상환경 실행

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

실행 정책 오류가 발생하는 경우 현재 PowerShell 세션에서 다음 명령을 먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

그다음 다시 가상환경을 실행합니다.

```powershell
.\venv\Scripts\Activate.ps1
```

Windows 명령 프롬프트:

```cmd
venv\Scripts\activate
```

macOS 또는 Linux:

```bash
source venv/bin/activate
```

가상환경이 정상적으로 실행되면 터미널 앞에 `(venv)`가 표시됩니다.

### 5. 라이브러리 설치

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 6. 웹서비스 실행

저장소 최상위 폴더에서 다음 명령을 실행합니다.

```bash
streamlit run frontend/map.py
```

실행 후 브라우저가 자동으로 열리지 않으면 터미널에 표시된 주소로 접속합니다.

```text
http://localhost:8501
```

---


## 주요 결과물

| 파일 | 설명 |
| --- | --- |
| `data/processed/safety_score_result.csv` | 격자별 시설 개수, 안전점수, 안전등급 |
| `data/processed/gwangjin.graphml` | 광진구 OpenStreetMap 보행 그래프 |
| `outputs/gwangjin_safety_map.html` | 광진구 안전지수 및 안전시설 지도 |
| `outputs/route_map.html` | 최단경로와 안전경로 비교 지도 |
| `outputs/gwangjin_safety_grid.geojson` | 격자 안전지수 공간 데이터 |
| `outputs/gwangjin_facilities.geojson` | 안전시설 위치 공간 데이터 |

---

## 활용 데이터
| 데이터 | 출처 | 담당 기관 | URL | 데이터 기준일 | 다운로드 날짜 |
| --- | --- | --- | --- | --- | --- |
| CCTV | 행정안전부 LocalData | 개인정보보호위원회 신기술개인정보과 | https://file.localdata.go.kr/file/emergency_call_box_info/info | 2025.11.27 | 2026.06.29 |
| 비상벨 | 행정안전부 LocalData | 국토교통부 주택정비과 | https://file.localdata.go.kr/file/cctv_info/info | 2025.11.27 | 2026.06.29 |
| 경찰서 | 공공데이터포털 | 경찰청 기획조정관실 혁신기획조정관 | https://www.data.go.kr/data/15124966/fileData.do | 2025.05.02 | 2026.06.29 |
| 파출소 | 공공데이터포털 | 경찰청 범죄예방대응국 지역경찰운영과 | https://www.data.go.kr/data/15077036/fileData.do | 2026.02.19 | 2026.06.29 |
| 가로등(광진구) | 공공데이터포털 | 서울특별시 광진구 스마트정보과 | https://www.data.go.kr/data/15070592/fileData.do | 2025.07.29 | 2026.06.29 |
| 가로등(서울시) | 공공데이터포털 | 서울특별시 데이터전략과 | https://www.data.go.kr/data/15107934/fileData.do | 2025.11.20 | 2026.07.13 |

---

## 참고 자료

### 안전시설 효과

- 경찰청·건축도시공간연구소, 범죄예방 환경설계 및 안전시설 효과 관련 연구, 2019.
- 관련 보도자료: https://www.yna.co.kr/view/AKR20200108078300004
- 활용 내용: 가로등, CCTV, 비상벨의 범죄예방 효과를 검토하고 시설 가중치 설정에 참고
- 최종 확인일: 2026-08-01

### 지도 및 공간 데이터

- OpenStreetMap Contributors
- OSMnx Documentation
- GeoPandas Documentation
- Folium Documentation

---

## 프로젝트 한계

- 공공데이터의 수집 시점과 갱신 주기가 서로 다를 수 있습니다.
- 실제 시설이 존재하더라도 공공데이터에서 누락될 수 있습니다.
- 공원, 사유지, 단지 내부 시설은 데이터에 충분히 반영되지 않을 수 있습니다.
- 안전지수는 공개된 안전시설의 위치와 분포를 바탕으로 계산한 상대적 지표입니다.
- 안전점수와 안전등급은 실제 범죄 발생 가능성이나 절대적인 보행 안전을 보장하지 않습니다.
- 현재 경로 추천은 시간대별 조도, 보행량, 유동인구, 도로 폭, 경사도 등을 반영하지 않습니다.
- 주소 검색은 외부 지오코딩 서비스 상태와 주소 표기 방식에 따라 실패할 수 있습니다.
- 실제 서비스 적용을 위해서는 범죄 발생 데이터와의 상관분석 및 사용자 평가가 추가로 필요합니다.

---

## 팀 정보

- 프로젝트명: 광진구 안전보행 경로 추천 서비스
- 수행 과정: 2026년 하계 세종창의학기제
- 수행 기간: 2026년 하계
- 참여 인원: 4명

## 역할 분담

| 역할 | 담당 업무 |
| --- | --- |
| 데이터 | 공공데이터 수집, 정제, 중복 확인 및 통합 |
| 안전지수 | 격자 생성, 거리감쇠 적용, 안전점수·등급 계산 |
| 경로 추천 | 보행 그래프 생성, 안전 가중치 적용, 최단·안전경로 탐색 |
| 지도 및 UI | 시설 지도 시각화, Streamlit 화면 및 기능 통합 |

---

## 실행 요약

```bash
git clone 저장소_URL
cd safety-walk-map

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
streamlit run frontend/map.py
```

`main` 브랜치를 복제한 뒤 위 명령을 순서대로 실행하면 프로젝트의 통합 웹서비스를 실행할 수 있습니다.

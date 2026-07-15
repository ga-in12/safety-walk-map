"""
경로 추천 목업(mock) 모듈 (route_mock.py)

OSMnx + Dijkstra 변형 알고리즘으로 만들 실제
recommend_safe_route 함수가 완성되기 전까지 화면 개발을 진행하기 위한 임시 구현임.

[합의된 인터페이스]
입력: 출발지/도착지 위도경도 (start_lat, start_lon, end_lat, end_lon)
출력: dict {
    "path": [(lat1, lon1), (lat2, lon2), ...],  # 경로 좌표 리스트
    "distance_m": float,                         # 총 거리(m)
    "safety_score": float,                       # 평균 안전지수(0~100)
}

팀원 완성본을 받으면 이 파일의 recommend_safe_route 함수만
그대로 교체할 예정. map.py 쪽 호출부는 수정할 필요 없음.
"""


def recommend_safe_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
    """[목업] 출발지-도착지를 직선으로 잇고, 임의의 거리/안전지수를 반환함."""
    # 실제 구현에서는 OSMnx로 도로 그래프를 불러오고
    # Dijkstra(비용 = 거리 / (안전지수+1))로 경로를 계산할 예정임.
    path = [(start_lat, start_lon), (end_lat, end_lon)]

    # 하버사인 거리로 대략적인 직선 거리 계산 (실제 도로 거리 아님, 목업용)
    from math import radians, sin, cos, sqrt, atan2

    R = 6371000  # 지구 반지름(m)
    dlat = radians(end_lat - start_lat)
    dlon = radians(end_lon - start_lon)
    a = sin(dlat / 2) ** 2 + cos(radians(start_lat)) * cos(radians(end_lat)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance_m = R * c

    return {
        "path": path,
        "distance_m": distance_m,
        "safety_score": 75.0,  # 목업 고정값
    }
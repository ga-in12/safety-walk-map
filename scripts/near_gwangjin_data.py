"광진구 주변 지역 시설물 전처리"


import pandas as pd


#################### 데이터 불러오기 ####################

gwangjin_facility = pd.read_csv(
    'data/raw/광진구_안전시설_통합.csv',
    encoding='utf-8-sig'
)

add_facility = pd.read_csv(
    'data/raw/추가본_v2_광진구필터.csv',
    encoding='utf-8-sig'
)


print('[기존 광진구 데이터 칼럼]')
print(gwangjin_facility.columns)

print('\n[추가 데이터 칼럼]')
print(add_facility.columns)

print('\n[기존 광진구 시설유형]')
print(gwangjin_facility['시설유형'].unique())

print('\n[추가 데이터 시설유형]')
print(add_facility['시설유형'].unique())


#################### 필요한 칼럼 확인 ####################

required_columns = [
    '시설명',
    '시설유형',
    '주소',
    '위도',
    '경도'
]


for data_name, data in [
    ('기존 광진구 데이터', gwangjin_facility),
    ('추가 데이터', add_facility)
]:

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:

        raise ValueError(
            f'{data_name}에 필요한 칼럼이 없습니다: '
            f'{missing_columns}'
        )


#################### 필요한 칼럼만 선택 ####################

gwangjin_facility = gwangjin_facility[
    required_columns
].copy()

add_facility = add_facility[
    required_columns
].copy()


#################### 문자열 칼럼 정리 ####################

text_columns = [
    '시설명',
    '시설유형',
    '주소'
]


for data in [
    gwangjin_facility,
    add_facility
]:

    for column in text_columns:

        data[column] = (
            data[column]
            .astype('string')
            .str.strip()
        )


#################### 위도·경도를 숫자로 변환 ####################

coordinate_columns = [
    '위도',
    '경도'
]


for data in [
    gwangjin_facility,
    add_facility
]:

    for column in coordinate_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors='coerce'
        )


#################### 좌표가 없는 행 제거 ####################

gwangjin_facility = gwangjin_facility.dropna(
    subset=[
        '위도',
        '경도'
    ]
).copy()

add_facility = add_facility.dropna(
    subset=[
        '위도',
        '경도'
    ]
).copy()


#################### 추가 데이터 시설유형 통일 ####################

add_facility['시설유형'] = (
    add_facility['시설유형']
    .replace({
        '안전비상벨': '비상벨',
        '경찰서/파출소': '파출소'
    })
)


print('\n[정리한 기존 광진구 시설유형별 개수]')
print(
    gwangjin_facility[
        '시설유형'
    ].value_counts(
        dropna=False
    )
)

print('\n[정리한 추가 데이터 시설유형별 개수]')
print(
    add_facility[
        '시설유형'
    ].value_counts(
        dropna=False
    )
)


#################### 중복 비교용 칼럼 생성 함수 ####################

def make_duplicate_key(data):

    data = data.copy()

    # 좌표를 소수점 네 자리까지 맞춰 비교
    data['_lat_key'] = (
        data['위도']
        .round(4)
    )

    data['_lng_key'] = (
        data['경도']
        .round(4)
    )

    # 시설명 비교용 문자열 생성
    data['_name_key'] = (
        data['시설명']
        .fillna('')
        .astype(str)

        # 괄호와 괄호 안의 내용 제거
        .str.replace(
            r'\([^)]*\)',
            '',
            regex=True
        )

        # 모든 공백 제거
        .str.replace(
            r'\s+',
            '',
            regex=True
        )

        .str.strip()
    )

    return data


#################### 비교용 칼럼 추가 ####################

gwangjin_facility = make_duplicate_key(
    gwangjin_facility
)

add_facility = make_duplicate_key(
    add_facility
)


# 시설명이 같고,
# 위도와 경도가 소수점 네 자리까지 같으면
# 같은 시설로 판단
duplicate_key_columns = [
    '_name_key',
    '_lat_key',
    '_lng_key'
]


#################### 각 데이터 내부 중복 제거 ####################

gwangjin_before_count = len(
    gwangjin_facility
)

gwangjin_facility = (
    gwangjin_facility
    .drop_duplicates(
        subset=duplicate_key_columns,
        keep='first'
    )
    .copy()
)

gwangjin_removed_count = (
    gwangjin_before_count
    - len(gwangjin_facility)
)


add_before_count = len(
    add_facility
)

add_facility = (
    add_facility
    .drop_duplicates(
        subset=duplicate_key_columns,
        keep='first'
    )
    .copy()
)

add_removed_count = (
    add_before_count
    - len(add_facility)
)


print('\n[기존 광진구 데이터 내부 중복 제거 개수]')
print(gwangjin_removed_count)

print('\n[추가 데이터 내부 중복 제거 개수]')
print(add_removed_count)


#################### 기존 데이터에 없는 시설만 선택 ####################

# 기존 광진구 시설의 비교 기준 생성
gwangjin_keys = (
    gwangjin_facility[
        duplicate_key_columns
    ]
    .drop_duplicates()
    .assign(
        existing_facility=True
    )
)


# 추가 데이터와 기존 광진구 데이터 비교
add_facility_checked = add_facility.merge(
    gwangjin_keys,
    on=duplicate_key_columns,
    how='left'
)


# existing_facility 값이 없으면
# 기존 광진구 데이터에 없는 새로운 시설
new_facility = add_facility_checked[
    add_facility_checked[
        'existing_facility'
    ].isna()
].copy()


new_facility = new_facility.drop(
    columns=[
        'existing_facility'
    ]
)


#################### 데이터 출처 표시 ####################

gwangjin_facility['데이터출처'] = (
    '기존_광진구통합본'
)

new_facility['데이터출처'] = (
    '주변지역_추가본'
)


#################### 최종 데이터 합치기 ####################

final_facility = pd.concat(
    [
        gwangjin_facility,
        new_facility
    ],
    ignore_index=True
)


#################### 최종 중복 한 번 더 제거 ####################

final_facility = (
    final_facility
    .drop_duplicates(
        subset=duplicate_key_columns,
        keep='first'
    )
    .copy()
)


#################### 임시 비교용 칼럼 제거 ####################

temporary_columns = [
    '_name_key',
    '_lat_key',
    '_lng_key'
]


final_facility = final_facility.drop(
    columns=temporary_columns
)

new_facility = new_facility.drop(
    columns=temporary_columns
)

gwangjin_facility = gwangjin_facility.drop(
    columns=temporary_columns
)


#################### 칼럼 순서 정리 ####################

final_columns = [
    '시설명',
    '시설유형',
    '주소',
    '위도',
    '경도',
    '데이터출처'
]


final_facility = final_facility[
    final_columns
]

new_facility = new_facility[
    final_columns
]

gwangjin_facility = gwangjin_facility[
    final_columns
]


#################### 결과 확인 ####################

print('\n[기존 광진구 시설 개수]')
print(len(gwangjin_facility))

print('\n[추가본에서 실제로 새로 추가된 시설 개수]')
print(len(new_facility))

print('\n[새로 추가된 시설 유형별 개수]')
print(
    new_facility[
        '시설유형'
    ].value_counts(
        dropna=False
    )
)

print('\n[최종 통합 시설 개수]')
print(len(final_facility))

print('\n[최종 통합 시설 유형별 개수]')
print(
    final_facility[
        '시설유형'
    ].value_counts(
        dropna=False
    )
)


#################### 최종 경찰시설 확인 ####################

police_facility_types = [
    '경찰서',
    '지구대',
    '파출소'
]


final_police_facility = final_facility[
    final_facility[
        '시설유형'
    ].isin(
        police_facility_types
    )
].copy()


print('\n[최종 경찰시설 확인]')

if final_police_facility.empty:

    print('경찰시설 데이터가 없습니다.')

else:

    print(
        final_police_facility[
            [
                '시설명',
                '시설유형',
                '주소',
                '위도',
                '경도',
                '데이터출처'
            ]
        ].to_string(
            index=False
        )
    )


#################### 동일한 좌표의 시설 확인 ####################

same_coordinate_facility = final_facility[
    final_facility.duplicated(
        subset=[
            '위도',
            '경도'
        ],
        keep=False
    )
].copy()


duplicate_count = final_facility.duplicated(
    subset=[
        '위도',
        '경도'
    ]
).sum()


print('\n[위도·경도가 중복되는 시설 개수]')
print(f'{duplicate_count}개')


if not same_coordinate_facility.empty:

    print('\n[동일한 좌표를 사용하는 시설 목록]')

    print(
        same_coordinate_facility[
            [
                '시설명',
                '시설유형',
                '주소',
                '위도',
                '경도',
                '데이터출처'
            ]
        ]
        .sort_values(
            by=[
                '위도',
                '경도'
            ]
        )
        .to_string(
            index=False
        )
    )


#################### 결과 저장 ####################

output_path = (
    'data/raw/광진구_주변지역_안전시설_통합.csv'
)


final_facility.to_csv(
    output_path,
    index=False,
    encoding='utf-8-sig'
)


print('\n최종 통합 데이터 저장 완료')
print('저장 경로:', output_path)



############ 확인용 ###########

# 위도·경도별로 시설 개수와 시설유형 목록 정리
duplicate_location_info = (
    final_facility
    .groupby(['위도', '경도'])
    .agg(
        중복개수=('시설유형', 'size'),
        중복시설유형=(
            '시설유형',
            lambda x: ', '.join(
                sorted(
                    x.dropna().astype(str).unique()
                )
            )
        )
    )
    .reset_index()
)


# 5개 초과인 좌표만 선택하고, 중복개수가 많은 순으로 정렬
duplicate_location_info = (
    duplicate_location_info[
        duplicate_location_info['중복개수'] > 5
    ]
    .sort_values(
        by='중복개수',
        ascending=False
    )
)


# 출력
for _, row in duplicate_location_info.iterrows():

    print(
        f"({row['위도']}, {row['경도']})"
        f" -> {row['중복개수']}개의 중복 시설물 발견"
        f" (중복시설유형: {row['중복시설유형']})"
    )
import numpy as np

print('확인')

print(
    gwangjin_facility[
        np.isclose(
            gwangjin_facility['위도'],
            37.55552
        )
        &
        np.isclose(
            gwangjin_facility['경도'],
            127.08984
        )
    ]
)
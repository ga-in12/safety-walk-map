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

for data in [
    gwangjin_facility,
    add_facility
]:

    for column in [
        '위도',
        '경도'
    ]:

        data[column] = pd.to_numeric(
            data[column],
            errors='coerce'
        )


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
    gwangjin_facility['시설유형'].value_counts(
        dropna=False
    )
)

print('\n[정리한 추가 데이터 시설유형별 개수]')
print(
    add_facility['시설유형'].value_counts(
        dropna=False
    )
)


#################### 구리시 경찰시설 수동 데이터 ####################

manual_police_facility = pd.DataFrame({
    '시설명': [
        '구리경찰서 (본서)',
        '교문지구대',
        '토평지구대 (아천동 관할)'
    ],

    '시설유형': [
        '경찰서',
        '지구대',
        '지구대'
    ],

    '주소': [
        '경기도 구리시 아차산로 359',
        '경기도 구리시 안골로 40',
        '경기도 구리시 체육관로74번길 55'
    ],

    '위도': [
        37.5876,
        37.5971,
        37.5913
    ],

    '경도': [
        127.1284,
        127.1354,
        127.1412
    ]
})


# 수동 데이터 문자열 정리
for column in text_columns:

    manual_police_facility[column] = (
        manual_police_facility[column]
        .astype('string')
        .str.strip()
    )


# 수동 데이터 위도·경도를 숫자형으로 변환
for column in [
    '위도',
    '경도'
]:

    manual_police_facility[column] = pd.to_numeric(
        manual_police_facility[column],
        errors='coerce'
    )


print('\n[추가하려는 구리시 경찰시설]')
print(manual_police_facility)


#################### 중복 비교용 칼럼 생성 함수 ####################

def make_duplicate_key(data):

    data = data.copy()

    # 수동으로 가져온 좌표가 소수점 네 자리이므로
    # 좌표를 소수점 네 자리로 맞춰 비교
    data['_lat_key'] = (
        data['위도']
        .round(4)
    )

    data['_lng_key'] = (
        data['경도']
        .round(4)
    )

    # 시설명 비교용 문자열 생성
    #
    # 예:
    # 구리경찰서 (본서) → 구리경찰서
    # 토평지구대 (아천동 관할) → 토평지구대
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

        # 문자열의 모든 공백 제거
        .str.replace(
            r'\s+',
            '',
            regex=True
        )

        .str.strip()
    )

    return data


#################### 모든 데이터에 비교용 칼럼 추가 ####################

gwangjin_facility = make_duplicate_key(
    gwangjin_facility
)

add_facility = make_duplicate_key(
    add_facility
)

manual_police_facility = make_duplicate_key(
    manual_police_facility
)


# 같은 시설이라고 판단할 기준
#
# 시설명이 같고,
# 위도와 경도가 소수점 네 자리까지 같으면
# 동일한 시설로 판단
duplicate_key_columns = [
    '_name_key',
    '_lat_key',
    '_lng_key'
]


#################### 추가 데이터 내부 중복 제거 ####################

add_facility = add_facility.drop_duplicates(
    subset=duplicate_key_columns,
    keep='first'
).copy()


#################### 수동 경찰시설 중 이미 존재하는 시설 확인 ####################

# 기존 광진구 데이터와 추가 데이터를 합쳐서
# 현재 존재하는 모든 시설의 비교 기준을 만듦
current_facility_keys = pd.concat(
    [
        gwangjin_facility[
            duplicate_key_columns
        ],

        add_facility[
            duplicate_key_columns
        ]
    ],
    ignore_index=True
)


current_facility_keys = (
    current_facility_keys
    .drop_duplicates()
    .assign(
        facility_already_exists=True
    )
)


# 수동으로 만든 경찰시설이
# 현재 데이터에 이미 존재하는지 확인
manual_police_checked = manual_police_facility.merge(
    current_facility_keys,
    on=duplicate_key_columns,
    how='left'
)


# 기존 데이터에 없는 경찰시설만 선택
new_manual_police = manual_police_checked[
    manual_police_checked[
        'facility_already_exists'
    ].isna()
].copy()


new_manual_police = new_manual_police.drop(
    columns='facility_already_exists'
)


print('\n[수동 데이터 중 실제 추가될 경찰시설]')
print(
    new_manual_police[
        [
            '시설명',
            '시설유형',
            '주소',
            '위도',
            '경도'
        ]
    ]
)

print('\n[수동 데이터 중 실제 추가될 시설 개수]')
print(len(new_manual_police))


#################### 없는 경찰시설만 추가 데이터에 합치기 ####################

add_facility = pd.concat(
    [
        add_facility,
        new_manual_police
    ],
    ignore_index=True
)


# 혹시 모를 추가 데이터 내부 중복을 다시 제거
add_facility = add_facility.drop_duplicates(
    subset=duplicate_key_columns,
    keep='first'
).copy()


#################### 기존 광진구 데이터에 없는 시설만 선택 ####################

# 기존 광진구 시설의 비교 기준만 추출
gwangjin_keys = (
    gwangjin_facility[
        duplicate_key_columns
    ]
    .drop_duplicates()
    .assign(
        existing_facility=True
    )
)


# 추가 데이터의 각 시설이
# 기존 광진구 데이터에 존재하는지 확인
add_facility_checked = add_facility.merge(
    gwangjin_keys,
    on=duplicate_key_columns,
    how='left'
)


# existing_facility가 비어 있으면
# 기존 광진구 데이터에 없는 새로운 시설
new_facility = add_facility_checked[
    add_facility_checked[
        'existing_facility'
    ].isna()
].copy()


new_facility = new_facility.drop(
    columns='existing_facility'
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

final_facility = final_facility.drop_duplicates(
    subset=duplicate_key_columns,
    keep='first'
).copy()


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


#################### 구리시 수동 경찰시설 포함 여부 확인 ####################

guri_police_names = [
    '구리경찰서',
    '교문지구대',
    '토평지구대'
]


guri_police_check = final_facility[
    final_facility[
        '시설명'
    ].fillna('').str.contains(
        '|'.join(guri_police_names),
        regex=True
    )
]


print('\n[구리시 경찰시설 최종 포함 여부]')
print(
    guri_police_check[
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
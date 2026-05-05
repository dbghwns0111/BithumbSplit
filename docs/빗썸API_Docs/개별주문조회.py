# Python 3
# pip install pyjwt python-dotenv requests

import os
import uuid
import hashlib
import time
from urllib.parse import urlencode
import requests
import jwt
from dotenv import load_dotenv

# ① .env 파일 로드
load_dotenv()
accessKey = os.getenv("BITHUMB_API_KEY")
secretKey = os.getenv("BITHUMB_API_SECRET")
apiUrl    = 'https://api.bithumb.com'

# ② 사용자 입력: 조회할 주문 UUID
order_uuid = input("조회할 주문의 UUID를 입력하세요: ").strip()

# ③ API 파라미터 준비
param = { 'uuid': order_uuid }

# ④ query_hash 생성 (SHA512)
q = urlencode(param).encode()
h = hashlib.sha512()
h.update(q)
query_hash = h.hexdigest()

# ⑤ JWT 페이로드 생성
payload = {
    'access_key':     accessKey,
    'nonce':          str(uuid.uuid4()),
    'timestamp':      round(time.time() * 1000),
    'query_hash':     query_hash,
    'query_hash_alg': 'SHA512',
}

# ⑥ JWT 토큰 인코딩
jwt_token = jwt.encode(payload, secretKey, algorithm="HS256")
auth_token = f"Bearer {jwt_token}"

# ⑦ 헤더 구성
headers = {
    'Authorization': auth_token
}

# ⑧ API 호출 및 pretty-print 함수
def pretty_print_order(data: dict):
    """
    빗썸 개별주문조회 결과 data(dict)를 보기 좋게 출력
    """
    # 필드명, data 키 쌍 정의
    fields = [
        ("주문 UUID",         data.get('uuid')),
        ("주문 타입",         data.get('side')),            # bid 또는 ask
        ("통화",              f"{data.get('order_currency')}/{data.get('payment_currency')}"),
        ("주문 수량",         data.get('units')),
        ("체결 수량",         data.get('executed_units')),
        ("미체결 수량",       data.get('remaining_units')),
        ("주문 가격",         data.get('price')),
        ("평균 체결가",       data.get('average_price')),
        ("수수료",            data.get('paid_fee')),
        ("주문 상태",         data.get('status')),          # e.g. "filled", "cancelled"
        ("주문 생성 시각",    data.get('order_date')),     # "2025-05-07 17:00:00"
    ]

    # 레이블 폭 계산
    label_width = max(len(label) for label, _ in fields)

    print("\n=== 주문 상세 조회 결과 ===")
    for label, val in fields:
        print(f"{label.ljust(label_width)} : {val}")

# ⑨ 호출 및 결과 처리
try:
    resp = requests.get(f"{apiUrl}/v1/order", params=param, headers=headers)
    data = resp.json()

    if data.get('status') != '0000':
        print(f"❌ 조회 실패 (status {data.get('status')}): {data.get('message')}")
    else:
        pretty_print_order(data.get('data', {}))

except Exception as e:
    print("예외 발생:", e)

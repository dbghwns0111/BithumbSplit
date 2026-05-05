# Python 3
# pip3 install pyjwt python-dotenv requests

import os
import uuid
import hashlib
import time
from urllib.parse import urlencode
import requests
import json
import jwt
from dotenv import load_dotenv

# ① .env 파일 로드
load_dotenv()
accessKey = os.getenv("BITHUMB_API_KEY")
secretKey = os.getenv("BITHUMB_API_SECRET")

apiUrl = 'https://api.bithumb.com'

# ② 사용자 입력 받기
market   = input("거래 종목을 입력하세요 (예: KRW-BTC): ").strip()
side     = input("주문 종류를 입력하세요 (bid 또는 ask): ").strip().lower()
volume   = input("주문 수량을 입력하세요 (예: 0.001): ").strip()
price    = input("주문 가격을 입력하세요 (예: 84000000): ").strip()
ord_type = input("주문 타입을 입력하세요 (limit 또는 market): ").strip().lower()

# ③ 요청 바디 구성
requestBody = {
    "market":   market,
    "side":     side,
    "volume":   volume,
    "price":    price,
    "ord_type": ord_type
}

# ④ JWT payload 생성을 위한 query_hash
query_string = urlencode(requestBody).encode()
h = hashlib.sha512()
h.update(query_string)
query_hash = h.hexdigest()

payload = {
    'access_key':     accessKey,
    'nonce':          str(uuid.uuid4()),
    'timestamp':      round(time.time() * 1000),
    'query_hash':     query_hash,
    'query_hash_alg': 'SHA512',
}

# ⑤ JWT 토큰 인코딩 & 헤더 구성
jwt_token = jwt.encode(payload, secretKey, algorithm="HS256")
authorization_token = f"Bearer {jwt_token}"

headers = {
    'Authorization':    authorization_token,
    'Content-Type':     'application/json'
}

# ⑥ API 호출
try:
    response = requests.post(
        f"{apiUrl}/v1/orders",
        data=json.dumps(requestBody),
        headers=headers
    )
    print("HTTP 상태코드:", response.status_code)
    print("응답 JSON:")
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
except Exception as err:
    print("예외 발생:", err)

# Python 3
# pip3 installl pyJwt
import jwt 
import uuid
import hashlib
import time
from urllib.parse import urlencode
import requests
import os
import json
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수에서 키 읽기
accessKey = os.getenv("BITHUMB_API_KEY")
secretKey = os.getenv("BITHUMB_API_SECRET")

apiUrl = 'https://api.bithumb.com'

# Set API parameters
param = dict( market='KRW-BTC' )

# Generate access token
query = urlencode(param).encode()
hash = hashlib.sha512()
hash.update(query)
query_hash = hash.hexdigest()
payload = {
    'access_key': accessKey,
    'nonce': str(uuid.uuid4()),
    'timestamp': round(time.time() * 1000), 
    'query_hash': query_hash,
    'query_hash_alg': 'SHA512',
}   
jwt_token = jwt.encode(payload, secretKey)
authorization_token = 'Bearer {}'.format(jwt_token)
headers = {
  'Authorization': authorization_token
}

def pretty_print_order_chance(res_json):
    # status 분기 생략… info 추출까지 마친 상태라 가정
    if 'status' in res_json and res_json.get('status') == '0000':
        info = res_json['data']
    else:
        info = res_json

    # 출력할 항목과 가져올 경로(딕셔너리) 정의
    fields = [
        ("매수 수수료 (%)",    info.get('bid_fee')),
        ("매도 수수료 (%)",    info.get('ask_fee')),
        ("메이커 매수 수수료",  info.get('maker_bid_fee')),
        ("메이커 매도 수수료",  info.get('maker_ask_fee')),
        ("최소 매수 총액",     info.get('market', {}).get('bid', {}).get('min_total')),
        ("최소 매도 총액",     info.get('market', {}).get('ask', {}).get('min_total')),
        ("최대 거래 총액",     info.get('market', {}).get('max_total')),
        ("보유 KRW 잔고",      info.get('bid_account', {}).get('balance')),
        ("보유 BTC 잔고",      info.get('ask_account', {}).get('balance')),
    ]
    label_width = max(len(label) for label, _ in fields)
    print("=== 주문 가능 정보 ===")
    for label, value in fields:
        print(f"{label:<{label_width}} : {value}")


try:
    # Call API
    response = requests.get(apiUrl + '/v1/orders/chance', params=param, headers=headers)
    # handle to success or fail
    print("HTTP 상태코드:", response.status_code)
    res_json = response.json()
    # 보기 좋게 출력
    pretty_print_order_chance(res_json)
except Exception as err:
    # handle exception
    print(err)

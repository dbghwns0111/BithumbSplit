# Python 3
# -*- coding: utf-8 -*-

import uuid
import time
import requests
import jwt
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# 환경변수에서 키 읽기
accessKey = os.getenv("BITHUMB_API_KEY")
secretKey = os.getenv("BITHUMB_API_SECRET")

apiUrl = 'https://api.bithumb.com'

# JWT 페이로드 생성
payload = {
    'access_key': accessKey,
    'nonce': str(uuid.uuid4()),
    'timestamp': round(time.time() * 1000)
}

# JWT 토큰 인코딩 (HS256)
jwt_token = jwt.encode(payload, secretKey, algorithm="HS256")
authorization_token = f'Bearer {jwt_token}'

# 헤더 구성
headers = {
    'Authorization': authorization_token
}

def pretty_print_assets(result_json):
    """
    빗썸 자산조회 결과를 보기 좋게 출력합니다.
    - /v1/accounts 는 리스트를 반환하므로, 리스트일 때 별도 처리
    - /info/balance 는 딕셔너리 형태(status/data)로 반환
    """
    # 1) 리스트 형태 (/v1/accounts)
    if isinstance(result_json, list):
        print("=== 개별 통화 잔고 (/v1/accounts) ===")
        # === 개별 통화 잔고 (/v1/accounts) ===
        for acct in result_json:
            cur    = acct.get('currency', '').upper()
            bal    = acct.get('balance', '0')
            locked = acct.get('locked', '0')
            avg    = acct.get('avg_buy_price') or acct.get('avg_buy_price_krw') or ''

            if cur == 'KRW':
                # KRW는 정수형처럼 포맷
                bal_val    = float(bal)
                locked_val = float(locked)
                print(f"{cur:>5} | 잔고: {bal_val:>10,.0f}원 | 락: {locked_val:>10,.0f}원")
            else:
                # 기존 포맷 유지 (BTC 등 소수 포함)
                print(f"{cur:>5} | 잔고: {bal:>12} | 락: {locked:>15} | 평균매수가: {avg}")
        return

    # 2) 딕셔너리 형태 (/info/balance)
    if isinstance(result_json, dict):
        status = result_json.get('status')
        if status != '0000':
            print(f"❌ 조회 실패: {result_json.get('message')!r}")
            return
        data = result_json.get('data', {})
        if 'total_krw' in data:
            print("=== KRW/BTC 잔고 (/info/balance) ===")
            total_krw = float(data.get('total_krw', 0))
            print(f"총 KRW:       {total_krw:,.0f}원")
            available_krw = float(data.get('available_krw', 0))
            print(f"사용 가능 KRW: {available_krw:,.0f}원")
            print(f"총 BTC:       {data.get('total_btc'):>12} BTC")
            print(f"사용 가능 BTC: {data.get('available_btc'):>12} BTC")
            return

    # 3) 위 두 경우 모두 아니면 원시 데이터 출력
    print("=== 원시 데이터 ===")
    print(result_json)


try:
    # API 호출: 자산 조회
    response = requests.get(f"{apiUrl}/v1/accounts", headers=headers)
    print("HTTP 상태코드:", response.status_code)
    res_json = response.json()
    # 보기 좋게 출력
    pretty_print_assets(res_json)

except Exception as err:
    print("예외 발생:", err)

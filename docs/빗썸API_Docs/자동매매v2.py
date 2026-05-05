import hashlib
import hmac
import time
import json
import requests
import os
from dotenv import load_dotenv

# .env 파일에서 API 키, Secret 불러오기
load_dotenv()
API_KEY = os.getenv("BITHUMB_API_KEY")
API_SECRET = os.getenv("BITHUMB_API_SECRET")

# 🔐 빗썸 API 2.0 서명 생성 함수
def get_headers(api_key, api_secret, method, url_path, body_dict):
    nonce = str(int(time.time() * 1000))  # timestamp (ms)
    str_body = json.dumps(body_dict, separators=(',', ':'), ensure_ascii=False)

    sign_target = method + url_path + nonce + str_body
    signature = hmac.new(
        api_secret.encode("utf-8"),
        sign_target.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        'Api-Key': api_key,
        'Api-Sign': signature,
        'Api-Timestamp': nonce,
        'Api-Content-Type': 'application/json'
    }, str_body

# 💰 빗썸 API 2.0 잔고조회 함수
def get_balance_v2():
    method = "POST"
    url_path = "/trade/balance"
    url = "https://api.bithumb.com" + url_path

    body = {
        "currency": "BTC"
    }

    # header + body 생성
    headers, str_body = get_headers(API_KEY, API_SECRET, method, url_path, body)

    # 반드시 application/json으로 명시, body는 json 문자열로 보냄
    response = requests.post(url, headers=headers, data=str_body.encode("utf-8"))

    print("📡 응답 상태코드:", response.status_code)
    print("📄 응답 본문:")
    print(response.text)

    try:
        return response.json()
    except Exception as e:
        print("❌ JSON 파싱 실패:", e)
        return None

# ✅ 테스트 실행
if __name__ == "__main__":
    result = get_balance_v2()
    print("📦 빗썸 API 2.0 잔고조회 결과:")
    print(result)

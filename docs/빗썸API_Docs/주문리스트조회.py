import os
import uuid as uuid_lib
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
apiUrl    = "https://api.bithumb.com"

# ② 사용자 입력
market   = input("조회할 마켓 (예: KRW-XRP): ").strip()
limit    = input("페이지당 주문 개수 limit (기본 100): ").strip() or "100"
page     = input("조회할 페이지 번호 page (기본 1): ").strip() or "1"
order_by = input("정렬순서 order_by (asc 또는 desc, 기본 desc): ").strip().lower() or "desc"
uuids_in = input("조회할 주문 UUID들 (쉼표로 구분): ").strip()
uuids    = [u.strip() for u in uuids_in.split(",") if u.strip()]

# ③ 쿼리 문자열 생성
base_params = {"market": market, "limit": limit, "page": page, "order_by": order_by}
query = urlencode(base_params)

if uuids:
    uuid_q = "&".join(f"uuids[]={u}" for u in uuids)
    query += f"&{uuid_q}"

# ④ query_hash 생성
h = hashlib.sha512()
h.update(query.encode("utf-8"))
query_hash = h.hexdigest()

# ⑤ JWT 페이로드 및 토큰 생성
payload = {
    "access_key":     accessKey,
    "nonce":          str(uuid_lib.uuid4()),
    "timestamp":      round(time.time() * 1000),
    "query_hash":     query_hash,
    "query_hash_alg": "SHA512",
}
jwt_token = jwt.encode(payload, secretKey, algorithm="HS256")
headers = {"Authorization": f"Bearer {jwt_token}"}

# ⑥ API 호출 및 결과 처리
try:
    url = f"{apiUrl}/v1/orders?{query}"
    resp = requests.get(url, headers=headers)
    orders = resp.json() # 빗썸 v1은 여기서 바로 리스트를 반환함
    
    print("HTTP 상태코드:", resp.status_code)

    # 에러 발생 시 (딕셔너리로 오고 'error' 키가 있을 경우)
    if isinstance(orders, dict) and "error" in orders:
        print(f"❌ 조회 실패: {orders.get('error').get('message')}")
        exit(1)

    # ⑦ 리스트 조회 결과 예쁘게 출력
    print("\n=== 주문 리스트 조회 결과 ===")
    if not orders:
        print("조회된 주문 내역이 없습니다.")
    else:
        for idx, order in enumerate(orders, start=1):
            print(f"\n▶ 주문 #{idx} (UUID: {order.get('uuid')})")
            # 빗썸 응답 필드명에 맞춰 수정 (v1 기준)
            fields = [
                ("주문 종류",     order.get("side")),            
                ("마켓",          order.get("market")),
                ("주문 수량",     order.get("volume")),
                ("체결 수량",     order.get("executed_volume")),
                ("미체결 수량",   order.get("remaining_volume")),
                ("주문가",        order.get("price")),
                ("평균 체결가",   order.get("avg_price")),
                ("주문 상태",     order.get("state")),
                ("주문 생성 시각", order.get("created_at")),
            ]
            
            for label, val in fields:
                print(f"{label.ljust(10)} : {val}")

except Exception as err:
    print("예외 발생:", err)
# bitsplit/api/api.py
# 빗썸 API와 연동하는 함수 모음

import os
import uuid
import hashlib
import time
import json
from urllib.parse import urlencode
import requests
from requests.exceptions import RequestException
import jwt
from dotenv import load_dotenv
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
if getattr(sys, 'frozen', False):
    # PyInstaller로 패키징된 경우
    base_path = Path(sys.executable).parent
else:
    # 개발 환경
    base_path = Path(__file__).parent.parent

if str(base_path) not in sys.path:
    sys.path.insert(0, str(base_path))

from utils.telegram import send_telegram_message
from config.settings import (
    API_TIMEOUT, PUBLIC_API_TIMEOUT, MAX_RETRY, RETRY_DELAY, RETRY_BACKOFF,
    TIME_SYNC_INTERVAL
)

# .env 파일 로드
load_dotenv()
accessKey = os.getenv("BITHUMB_API_KEY")
secretKey = os.getenv("BITHUMB_API_SECRET")

# 환경 변수 검증
def validate_api_credentials():
    """API 인증 정보 검증"""
    if not accessKey or not secretKey:
        error_msg = (
            "❌ API 인증 정보가 설정되지 않았습니다.\n"
            "BITHUMB_API_KEY와 BITHUMB_API_SECRET을 .env 파일에 설정해주세요."
        )
        print(error_msg)
        raise ValueError(error_msg)
    print("✅ API 인증 정보 확인 완료")

# 프로그램 시작 시 검증 (import 시점에 자동 실행)
try:
    validate_api_credentials()
except ValueError as e:
    print(f"⚠️ 경고: {e}")
    # API 키 없이도 일부 기능은 사용 가능하도록 허용

# 서버 시간 보정값 (ms)
_server_time_offset_ms = 0
_last_time_sync = 0.0

class RateLimiter:
    """빗썸 API 호출 제한 관리자"""
    def __init__(self, calls_per_sec=10):
        self.interval = 1.0 / calls_per_sec
        self.last_call = 0.0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()

# 전역 레이트 리미터 인스턴스 (초당 10회 제한)
rate_limiter = RateLimiter(calls_per_sec=8)  # 여유 있게 8회로 설정

def _alert(msg: str):
    """텔레그램 알림 전송 (실패 시 로그 출력)"""
    try:
        send_telegram_message(msg)
    except Exception as e:
        # 텔레그램 전송 실패를 로그로 남김
        print(f"⚠️ 텔레그램 알림 전송 실패: {e}")
apiUrl = 'https://api.bithumb.com'


def _sync_server_time(force: bool = False):
    """공개 시세 API를 이용해 서버 시간과의 차이를 보정한다."""
    global _server_time_offset_ms, _last_time_sync

    if not force and (time.time() - _last_time_sync) < TIME_SYNC_INTERVAL:
        return

    try:
        # 빗썸 공식 API 사용
        url = f"{apiUrl}/v1/ticker?markets=KRW-BTC"
        headers = {"accept": "application/json"}
        resp = requests.get(url, headers=headers, timeout=PUBLIC_API_TIMEOUT)
        data = resp.json()
        
        # 빗썸 API는 timestamp를 밀리초로 반환
        if isinstance(data, list) and len(data) > 0:
            server_ts = int(data[0].get('timestamp', 0))
            if server_ts:
                local_ts = int(time.time() * 1000)
                _server_time_offset_ms = server_ts - local_ts
                _last_time_sync = time.time()
    except Exception:
        # 서버 시간 확인 실패 시 보정 없이 진행
        pass


def _now_ms():
    _sync_server_time()
    return round(time.time() * 1000 + _server_time_offset_ms)


def _is_expired_jwt(resp_json):
    if isinstance(resp_json, dict):
        err = resp_json.get('error')
        if isinstance(err, dict) and err.get('name') == 'expired_jwt':
            return True
    return False


def _signed_request(method, path, query=None, body=None, retries=MAX_RETRY, delay=RETRY_DELAY, backoff=RETRY_BACKOFF, timeout=API_TIMEOUT, alert_label=None):
    """JWT 서명 요청 + 만료 시 재시도 공통 헬퍼"""
    cur_delay = delay
    url = f"{apiUrl}{path}"

    for attempt in range(1, retries + 1):
        rate_limiter.wait()  # API 호출 전 대기
        headers = _make_token(body if body else query)
        if body is not None:
            headers['Content-Type'] = 'application/json'

        try:
            resp = requests.request(
                method,
                url,
                params=query,
                data=json.dumps(body) if body is not None else None,
                headers=headers,
                timeout=timeout,
            )
            data = resp.json()

            if _is_expired_jwt(data) and attempt < retries:
                # 서버 시간 보정 후 재시도
                _sync_server_time(force=True)
                time.sleep(cur_delay)
                cur_delay *= backoff
                continue

            return data
        except RequestException as e:
            if attempt == retries:
                if alert_label:
                    _alert(f"🚨 {alert_label} 실패({attempt}/{retries}): {e}")
                return {"status": "9999", "message": str(e)}
            time.sleep(cur_delay)
            cur_delay *= backoff

# 공통: JWT 토큰 생성 함수
def _make_token(query: dict = None):
    payload = {
        'access_key': accessKey,
        'nonce': str(uuid.uuid4()),
        'timestamp': _now_ms(),
    }

    if query:
        query_string = urlencode(query).encode()
        m = hashlib.sha512()
        m.update(query_string)
        query_hash = m.hexdigest()
        payload['query_hash'] = query_hash
        payload['query_hash_alg'] = 'SHA512'

    jwt_token = jwt.encode(payload, secretKey, algorithm='HS256')
    return {
        'Authorization': f'Bearer {jwt_token}'
    }

# 자산 조회
def get_balance():
    return _signed_request("GET", "/v1/accounts", alert_label="잔고 조회")

# 주문 가능 정보 조회
def get_order_chance(market='KRW-BTC'):
    query = {"market": market}
    return _signed_request("GET", "/v1/orders/chance", query=query, alert_label="주문 가능 조회")

# 주문 실행 함수 (지정가 또는 시장가)
def place_order(market, side, volume, price, ord_type='limit', retries=MAX_RETRY, delay=RETRY_DELAY, backoff=RETRY_BACKOFF):
    body = {
        "market": market,
        "side": side,
        "volume": str(volume),
        "price": str(price),
        "ord_type": ord_type
    }
    return _signed_request(
        "POST",
        "/v1/orders",
        body=body,
        retries=retries,
        delay=delay,
        backoff=backoff,
        alert_label=f"주문 요청 {market} {side} {price}"
    )

# 주문 취소 함수 (UUID 기반)
def cancel_order(order_uuid, retries=MAX_RETRY, delay=RETRY_DELAY, backoff=RETRY_BACKOFF):
    param = {'uuid': order_uuid}
    return _signed_request(
        "DELETE",
        "/v1/order",
        query=param,
        retries=retries,
        delay=delay,
        backoff=backoff,
        alert_label=f"주문 취소 {order_uuid}"
    )

# 개별 주문 조회
def get_order_detail(order_uuid, retries=MAX_RETRY, delay=RETRY_DELAY, backoff=RETRY_BACKOFF):
    query = {"uuid": order_uuid}
    result = _signed_request(
        "GET",
        "/v1/order",
        query=query,
        retries=retries,
        delay=delay,
        backoff=backoff,
        alert_label=f"주문 조회 {order_uuid}"
    )
    return result

# 주문 리스트 조회

def get_order_list(market='KRW-BTC', limit=100, page=1, order_by='desc', uuids=None, state='wait'):
    """주문 목록 조회
    
    Args:
        state: 'wait'(미체결), 'done'(체결), 'cancel'(취소), None(전체)
    """
    query = {
        "market": market,
        "limit": str(limit),
        "page": str(page),
        "order_by": order_by
    }
    # None일 때만 state 파라미터 생략 (전체 조회)
    if state is not None:
        query["state"] = state
    if uuids:
        for i, u in enumerate(uuids):
            query[f"uuids[{i}]"] = u

    return _signed_request("GET", "/v1/orders", query=query, alert_label="주문 리스트 조회")

# 전체 주문 취소
def cancel_all_orders(market):
    print(f"📋 {market} 미체결 주문 조회 중...")
    orders = get_order_list(market)

    # 응답이 dict가 아니거나 에러인 경우 처리
    if not isinstance(orders, list):
        if isinstance(orders, dict):
            error_msg = orders.get('message', 'Unknown error')
            print(f"⚠️ 주문 조회 실패: {error_msg}")
        else:
            print(f"⚠️ 주문 조회 실패: 예상치 못한 응답 형식")
        return

    if not orders:
        print("✅ 취소할 주문 없음")
        return

    for order in orders:
        if isinstance(order, dict):
            uuid = order.get("order_id") or order.get("uuid")
            if uuid:
                res = cancel_order(uuid)
                print(f"🗑️ 주문 취소 요청: {uuid} → {res}")
                time.sleep(0.2)

# 현재가 조회
def get_current_price(market='KRW-BTC', retries=MAX_RETRY, delay=RETRY_DELAY, backoff=RETRY_BACKOFF):
    """빗썸 공식 API를 사용하여 현재가 조회"""
    # 유효성 검사: market이 올바른 형식인지 확인
    if not market or not isinstance(market, str) or '-' not in market:
        print(f"⚠️ 잘못된 market 형식: '{market}' - 조회 건너뜀")
        return None
    
    parts = market.split('-')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        print(f"⚠️ 잘못된 market 형식: '{market}' - 조회 건너뜀")
        return None
    
    cur_delay = delay

    for attempt in range(1, retries + 1):
        try:
            rate_limiter.wait()  # API 호출 전 대기
            # 빗썸 공식 API 형식: /v1/ticker?markets=KRW-BTC
            url = f"{apiUrl}/v1/ticker?markets={market}"
            headers = {"accept": "application/json"}
            resp = requests.get(url, headers=headers, timeout=PUBLIC_API_TIMEOUT)
            data = resp.json()
            
            # 빗썸 API 응답 형식: [{"market": "KRW-BTC", "trade_price": 123456.0, ...}]
            if isinstance(data, list) and len(data) > 0:
                trade_price = data[0].get('trade_price')
                if trade_price:
                    return float(trade_price)
            
            # 오류 응답 처리 (마지막 시도에서만 알림)
            error_msg = data.get('error', {}).get('message', 'unknown error') if isinstance(data, dict) else 'unknown error'
            if attempt == retries:
                print(f"❌ 현재가 조회 최종 실패: {market} - {error_msg}")
                # 알림은 중요한 경우에만 (자동매매 전략 실행 중)
                # _alert(f"🚨 현재가 조회 실패 {market}: {error_msg}")
                return None
            else:
                time.sleep(cur_delay)
                cur_delay *= backoff
                
        except RequestException as e:
            print(f"⚠️ 현재가 조회 네트워크 오류 ({attempt}/{retries}): {e}")
            if attempt == retries:
                _alert(f"🚨 현재가 조회 실패({attempt}/{retries}) {market}: {e}")
                return None
            time.sleep(cur_delay)
            cur_delay *= backoff
        except Exception as e:
            print(f"⚠️ 현재가 조회 예외 ({attempt}/{retries}): {e}")
            if attempt == retries:
                return None
            time.sleep(cur_delay)
            cur_delay *= backoff
    
    # 모든 재시도 실패 시 명시적으로 None 반환
    return None
    
# 주문 취소 함수 (재시도 로직 포함)
# - 매수 체결 시: (n-1)차 매도 주문 취소 추가
# - 매도 체결 시: (n+1)차 매수 주문 취소 + (n-1)차 매도 주문 재등록
def cancel_order_by_uuid(uuid, retries=MAX_RETRY, delay=RETRY_DELAY):
    """주문 취소 (재시도 로직 포함)"""
    if not uuid:
        return False
    
    for attempt in range(1, retries + 1):
        try:
            res = cancel_order(uuid)
            
            # 성공 케이스
            if res.get('uuid') or res.get('data', {}).get('uuid'):
                print(f"🚫 주문 취소 성공: {uuid}")
                return True
            
            # 이미 취소/체결된 주문인 경우 (에러지만 문제 없음)
            error_msg = res.get('error', {}).get('message', '') if isinstance(res.get('error'), dict) else str(res)
            if 'already' in error_msg.lower() or 'not found' in error_msg.lower() or '찾지 못했습니다' in error_msg:
                print(f"ℹ️ 주문이 이미 취소/체결됨: {uuid[:8]}...")
                return None  # 이미 체결/취소된 경우는 None 반환 (에러 아님)
            
            # 실제 오류 케이스
            if attempt < retries:
                print(f"⚠️ 주문 취소 실패 ({attempt}/{retries}): {uuid[:8]}... / {error_msg} - 재시도 중...")
                time.sleep(delay)
            else:
                print(f"❌ 주문 취소 최종 실패: {uuid[:8]}... / {error_msg}")
                # 텔레그램 알림은 실제 치명적인 에러일 때만 전송
                # _alert(f"🚨 주문 취소 실패: {uuid[:8]}... / {error_msg}")
                return False
                
        except Exception as e:
            if attempt < retries:
                print(f"⚠️ 주문 취소 예외 ({attempt}/{retries}): {uuid[:8]}... / {e} - 재시도 중...")
                time.sleep(delay)
            else:
                print(f"❌ 주문 취소 중 예외 발생: {uuid[:8]}... / {e}")
                # 텔레그램 알림은 실제 치명적인 에러일 때만 전송
                # _alert(f"🚨 주문 취소 예외: {uuid[:8]}... / {str(e)[:50]}")
                return False
    
    return False
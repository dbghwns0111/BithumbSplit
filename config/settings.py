# config/settings.py
# BithumbSplit 전역 설정

# API 설정
API_TIMEOUT = 5  # API 호출 타임아웃 (초)
PUBLIC_API_TIMEOUT = 3  # 공개 API 타임아웃 (초)
MAX_RETRY = 3  # 최대 재시도 횟수
RETRY_DELAY = 0.3  # 재시도 간격 (초)
RETRY_BACKOFF = 2  # 재시도 시 대기 시간 배수

# 서버 시간 동기화
TIME_SYNC_INTERVAL = 300  # 서버 시간 동기화 간격 (초)

# 거래 설정
FEE_RATE = 0.0004  # 빗썸 거래 수수료율 (0.04%)

# 헬스체크 설정
HEALTH_CHECK_INTERVAL = 30  # 헬스체크 루프 간격 (30 * sleep_sec = 약 1분)
SLEEP_SEC = 2  # 메인 루프 대기 시간 (초) - 급변동 대응 강화

# 다중 주문 설정 (급변동 대응)
MULTI_ORDER_COUNT = 2  # 동시에 걸어둘 매수/매도 차수 개수 (2 = 2개씩, 3 = 3개씩)

# GUI 설정
PRICE_UPDATE_INTERVAL = 3  # 실시간 가격 업데이트 간격 (초)
STATUS_UPDATE_INTERVAL = 100  # 상태 업데이트 간격 (ms)

# 입력 검증
MIN_AMOUNT = 5000  # 최소 매수 금액 (원)
MAX_AMOUNT = 50000000  # 최대 매수 금액 (원)
MIN_LEVELS = 1  # 최소 차수
MAX_LEVELS = 999  # 최대 차수 (사실상 제한 없음)
MIN_GAP = 0.01  # 최소 간격 (%)
MAX_GAP = 50  # 최대 간격 (%)

# 지원 코인 목록
SUPPORTED_COINS = [
    'BTC', 'ETH', 'XRP', 'USDT', 'USDC', 
    'SOL', 'ADA', 'DOGE', 'LTC', 'ETC', 
    'BCH', 'AVAX', 'LINK', 'DOT', 'MATIC',
    'UNI', 'ATOM', 'XLM', 'TRX', 'SHIB',
    'APT', 'ARB', 'OP', 'SUI', 'SEI',
]

# 필수 디렉토리
REQUIRED_DIRS = ['logs', 'backups', 'config']

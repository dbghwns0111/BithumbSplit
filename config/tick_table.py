# bitsplit/config/tick_table.py
# 코인별 호가 단위 정의 (확장판)

TICK_SIZE = {
    # 메이저 코인
    'KRW-BTC': 1000,
    'KRW-ETH': 1000,
    'KRW-BCH': 1000,
    
    # 중형 코인 (10원 단위)
    'KRW-SOL': 10,
    'KRW-LTC': 10,
    'KRW-ETC': 10,
    'KRW-AVAX': 10,
    'KRW-LINK': 10,
    'KRW-DOT': 10,
    'KRW-MATIC': 10,
    'KRW-ATOM': 10,
    
    # 소형 코인 (1원 단위)
    'KRW-XRP': 1,
    'KRW-USDT': 1,
    'KRW-USDC': 1,
    'KRW-ADA': 1,
    'KRW-DOGE': 1,
    'KRW-TRX': 1,
    'KRW-XLM': 1,
    'KRW-UNI': 1,
    'KRW-SHIB': 1,
    'KRW-APT': 1,
    'KRW-ARB': 1,
    'KRW-OP': 1,
    'KRW-SUI': 1,
    'KRW-SEI': 1,
}

def get_tick_size(market):
    """호가 단위 조회 (기본값: 1원)"""
    return TICK_SIZE.get(market, 1)

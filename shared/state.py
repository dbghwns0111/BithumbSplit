import threading

# 전역 전략 상태
strategy_info = {
    "market": "-",
    "start_price": 0.0,
    "current_price": 0.0,
    "realized_profit": 0.0,
    "today_profit": 0.0,
    "monthly_profit": 0.0
}

# 스레드 안전성을 위한 락
state_lock = threading.Lock()

def update_strategy_info(key, value):
    """전략 상태를 안전하게 업데이트"""
    with state_lock:
        strategy_info[key] = value

def get_strategy_info(key=None):
    """전략 상태를 안전하게 조회"""
    with state_lock:
        if key:
            return strategy_info.get(key)
        return strategy_info.copy()

def update_strategy_info_batch(data):
    """여러 필드를 한 번에 안전하게 업데이트"""
    with state_lock:
        strategy_info.update(data)
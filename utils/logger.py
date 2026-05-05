import os
import csv
from datetime import datetime
from .file_io import get_base_dir, ensure_directory

def get_trade_log_path(market='KRW-BTC'):
    """거래 로그 파일 경로 생성"""
    filename = f'trade_log_{market.replace("-", "_")}.csv'
    return os.path.join(get_base_dir(), 'logs', filename)

def append_trade_log(market, level, buy_price, sell_price, volume, profit, filled_time):
    """거래 내역을 CSV 파일에 추가"""
    try:
        path = get_trade_log_path(market)
        ensure_directory(path)
        
        file_exists = os.path.exists(path)
        
        with open(path, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'market', 'level', 'buy_price', 'sell_price', 'volume', 'profit', 'filled_time'])
            
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                market,
                level,
                buy_price,
                sell_price,
                volume,
                profit,
                filled_time
            ])
        return True
    except Exception as e:
        print(f"⚠️ 거래 로그 기록 실패: {e}")
        return False

def load_trade_history(market):
    """로그 파일에서 거래 이력(누적 수익, 거래 횟수) 로드"""
    try:
        path = get_trade_log_path(market)
        if not os.path.exists(path):
            return 0.0, 0
        
        total_profit = 0.0
        trade_count = 0
        
        with open(path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    total_profit += float(row['profit'])
                    trade_count += 1
                except (ValueError, KeyError):
                    continue
        
        return total_profit, trade_count
    except Exception as e:
        print(f"⚠️ 거래 로그 복원 실패: {e}")
        return 0.0, 0

def get_profit_stats(market):
    """오늘 및 이번 달 수익 통계 계산"""
    try:
        path = get_trade_log_path(market)
        if not os.path.exists(path):
            return 0.0, 0.0
        
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        month_str = now.strftime('%Y-%m')
        
        today_profit = 0.0
        monthly_profit = 0.0
        
        with open(path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = row['timestamp'] # 형식: 2026-05-02 02:00:00
                    profit = float(row['profit'])
                    
                    if ts.startswith(today_str):
                        today_profit += profit
                    if ts.startswith(month_str):
                        monthly_profit += profit
                except (ValueError, KeyError):
                    continue
                    
        return today_profit, monthly_profit
    except Exception as e:
        print(f"⚠️ 수익 통계 계산 실패: {e}")
        return 0.0, 0.0

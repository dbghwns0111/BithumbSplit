import os
import json
import sys
from pathlib import Path
from datetime import datetime

def get_base_dir():
    """프로젝트 루트 또는 실행 파일 위치 반환"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_state_path(market='KRW-BTC'):
    """상태 파일 경로 생성"""
    filename = f'autotrade_state_{market.replace("-", "_")}.json'
    return os.path.join(get_base_dir(), 'logs', filename)

def ensure_directory(path):
    """디렉토리가 없으면 생성"""
    os.makedirs(os.path.dirname(path), exist_ok=True)

def save_state(state, market='KRW-BTC'):
    """상태를 JSON 파일로 저장"""
    try:
        path = get_state_path(market)
        ensure_directory(path)
        state['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ 상태 파일 저장 실패: {e}")
        return False

def load_state(market='KRW-BTC'):
    """상태를 JSON 파일에서 로드"""
    try:
        path = get_state_path(market)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 상태 파일 로드 실패: {e}")
        return None

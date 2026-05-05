# utils/log_config.py
# 로깅 설정 모듈

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_logger(name='bithumbSplit', log_level=logging.INFO):
    """애플리케이션 로거 설정 (콘솔 + 파일 로테이션)"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(log_level)
    
    # 로그 디렉토리 생성
    log_dir = os.path.join(get_base_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 포매터
    fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)-7s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(fmt)
    logger.addHandler(console)
    
    # 파일 핸들러 (일별 로테이션, 30일 보관)
    log_path = os.path.join(log_dir, 'app.log')
    file_handler = TimedRotatingFileHandler(
        log_path, when='midnight', interval=1,
        backupCount=30, encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(fmt)
    file_handler.suffix = '%Y-%m-%d'
    logger.addHandler(file_handler)
    
    return logger

# 전역 로거 인스턴스
logger = setup_logger()

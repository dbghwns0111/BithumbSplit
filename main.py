# bithumbSplit/main.py
# 메인 통합 실행 엔트리 포인트

import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
base_path = Path(__file__).parent
if str(base_path) not in sys.path:
    sys.path.insert(0, str(base_path))

from config.settings import REQUIRED_DIRS

def ensure_directories():
    """프로그램 실행에 필요한 디렉토리 생성"""
    for dir_name in REQUIRED_DIRS:
        dir_path = os.path.join(base_path, dir_name)
        os.makedirs(dir_path, exist_ok=True)
    print("✅ 필수 디렉토리 확인 완료")

if __name__ == '__main__':
    ensure_directories()
    
    # 인자값이 있으면 CLI 모드(구버전 호환용), 없으면 GUI 실행
    if len(sys.argv) > 1:
        from strategy.auto_trade import run_auto_trade
        from config.settings import SUPPORTED_COINS
        
        print("📈 CLI 모드로 전략 실행을 시작합니다.")
        # CLI 로직 (기존 main.py 내용)
        # ... (생략 또는 기존 코드 유지) ...
        # 현재는 GUI가 주력이므로 GUI 실행을 권장하는 메시지 출력
        print("💡 GUI 모드를 실행하려면 인자 없이 실행하세요: python main.py")
    else:
        print("🖥️ GUI 모드를 실행합니다...")
        from gui.gui_app import app
        app.mainloop()
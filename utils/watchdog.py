# utils/watchdog.py
# 자동 재시작 워치독 - main.py 대신 이 파일을 실행
# 사용법: python utils/watchdog.py (프로젝트 루트에서) 또는 python -m utils.watchdog

import subprocess
import sys
import time
import os
from datetime import datetime

MAX_RESTARTS = 10       # 최대 연속 재시작 횟수
COOLDOWN_SEC = 30       # 재시작 대기 시간 (초)
RESET_AFTER_SEC = 300   # 이 시간 이상 정상 실행되면 카운터 리셋

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(project_root, 'main.py')
    restart_count = 0
    
    while restart_count < MAX_RESTARTS:
        start_time = time.time()
        print(f"\n{'='*50}")
        print(f"[WATCHDOG] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[WATCHDOG] main.py 시작 (재시작 {restart_count}/{MAX_RESTARTS})")
        print(f"{'='*50}\n")
        
        try:
            process = subprocess.Popen(
                [sys.executable, script],
                cwd=os.path.dirname(script)
            )
            process.wait()
            exit_code = process.returncode
        except KeyboardInterrupt:
            print("\n[WATCHDOG] 사용자 중단 (Ctrl+C)")
            try:
                process.terminate()
            except:
                pass
            break
        except Exception as e:
            print(f"[WATCHDOG] 프로세스 실행 오류: {e}")
            exit_code = -1
        
        elapsed = time.time() - start_time
        
        # 정상 종료(0) 시 워치독도 종료
        if exit_code == 0:
            print("[WATCHDOG] 정상 종료. 워치독 종료합니다.")
            break
        
        # 충분히 오래 실행된 경우 카운터 리셋
        if elapsed > RESET_AFTER_SEC:
            restart_count = 0
        
        restart_count += 1
        print(f"[WATCHDOG] 비정상 종료 (코드: {exit_code}, 실행시간: {elapsed:.0f}초)")
        print(f"[WATCHDOG] {COOLDOWN_SEC}초 후 재시작...")
        time.sleep(COOLDOWN_SEC)
    
    if restart_count >= MAX_RESTARTS:
        print(f"[WATCHDOG] 최대 재시작 횟수({MAX_RESTARTS}) 초과. 종료합니다.")

if __name__ == '__main__':
    main()

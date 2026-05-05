# utils/telegram_bot.py
# 텔레그램 원격 제어 봇 (경량 폴링 방식, 외부 라이브러리 없음)

import os
import time
import threading
import requests
from dotenv import load_dotenv
from utils.log_config import logger

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TelegramCommandBot:
    """텔레그램 명령어를 수신하여 전략을 원격 제어하는 봇"""
    
    def __init__(self, manager=None):
        self.manager = manager
        self.running = False
        self.last_update_id = 0
        self._thread = None
    
    def start(self):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("텔레그램 봇 토큰/채팅ID 미설정 - 원격 제어 비활성화")
            return
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("📡 텔레그램 원격 제어 봇 시작")
    
    def stop(self):
        self.running = False
    
    def _poll_loop(self):
        """Telegram getUpdates API를 주기적으로 폴링"""
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 10}
                resp = requests.get(url, params=params, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        msg = update.get("message", {})
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        text = msg.get("text", "").strip()
                        
                        # 보안: 등록된 채팅 ID만 허용
                        if chat_id != TELEGRAM_CHAT_ID:
                            continue
                        
                        self._handle_command(text)
            except Exception as e:
                logger.debug(f"텔레그램 폴링 오류: {e}")
            
            time.sleep(3)
    
    def _handle_command(self, text):
        """명령어 처리"""
        if not text.startswith("/"):
            return
        
        cmd = text.lower().split()[0]
        
        if cmd == "/status":
            self._cmd_status()
        elif cmd == "/profit":
            self._cmd_profit()
        elif cmd == "/stop":
            self._cmd_stop()
        elif cmd == "/help":
            self._cmd_help()
        else:
            self._send(f"❓ 알 수 없는 명령어: {cmd}\n/help 로 도움말을 확인하세요.")
    
    def _cmd_status(self):
        if not self.manager:
            self._send("⚠️ 전략이 연결되지 않았습니다.")
            return
        
        from shared.state import get_strategy_info
        info = get_strategy_info()
        last_filled = max([lv.level for lv in self.manager.levels if lv.buy_filled], default=0)
        active_buys = sum(1 for lv in self.manager.levels if lv.buy_uuid and not lv.buy_filled)
        active_sells = sum(1 for lv in self.manager.levels if lv.sell_uuid and not lv.sell_filled)
        
        msg = (
            f"📊 <b>[현황 조회]</b>\n"
            f"📍 코인: {info.get('market', '-')}\n"
            f"💰 현재가: {info.get('current_price', 0):,.0f}원\n"
            f"🔢 마지막 체결: {last_filled}차\n"
            f"📋 미체결: 매수 {active_buys}건 / 매도 {active_sells}건\n"
            f"💵 누적 수익: {info.get('realized_profit', 0):,.0f}원"
        )
        self._send(msg)
    
    def _cmd_profit(self):
        from utils.logger import get_profit_stats, load_trade_history
        if not self.manager:
            self._send("⚠️ 전략이 연결되지 않았습니다.")
            return
        
        today_p, monthly_p = get_profit_stats(self.manager.market)
        total_p, count = load_trade_history(self.manager.market)
        
        msg = (
            f"💰 <b>[수익 조회]</b>\n"
            f"📅 오늘: <b>{today_p:,.0f}원</b>\n"
            f"🗓️ 이번 달: <b>{monthly_p:,.0f}원</b>\n"
            f"🏆 총 누적: <b>{total_p:,.0f}원</b>\n"
            f"📊 총 체결: {count}건"
        )
        self._send(msg)
    
    def _cmd_stop(self):
        self._send("🛑 전략 중단 명령 수신... 처리 중...")
        if self.manager and hasattr(self.manager, 'stop_condition'):
            # GUI의 stop_flag를 설정
            import shared.state as state_mod
            if hasattr(state_mod, '_remote_stop'):
                state_mod._remote_stop = True
            self._send("🛑 전략 중단 요청 완료. 다음 루프에서 중단됩니다.")
        else:
            self._send("⚠️ 전략 매니저가 연결되지 않았습니다.")
    
    def _cmd_help(self):
        msg = (
            "📋 <b>[명령어 목록]</b>\n"
            "/status - 현재 전략 상태 조회\n"
            "/profit - 수익 현황 조회\n"
            "/stop - 전략 중단\n"
            "/help - 도움말"
        )
        self._send(msg)
    
    def _send(self, message):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=5)
        except Exception as e:
            logger.error(f"텔레그램 응답 전송 실패: {e}")

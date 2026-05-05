# bithumbSplit/strategy/auto_trade.py
# 리팩토링된 자동매매 매니저 클래스

import time
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
if getattr(sys, 'frozen', False):
    base_path = Path(sys.executable).parent
else:
    base_path = Path(__file__).parent.parent

if str(base_path) not in sys.path:
    sys.path.insert(0, str(base_path))

from api.api import place_order, get_order_detail, cancel_order_by_uuid, get_current_price, get_order_list
from config.tick_table import get_tick_size
from config.settings import FEE_RATE, HEALTH_CHECK_INTERVAL, SLEEP_SEC, MULTI_ORDER_COUNT
from utils.telegram import (
    send_telegram_message, MSG_AUTO_TRADE_START, MSG_BUY_ORDER, 
    MSG_SELL_ORDER, MSG_BUY_FILLED, MSG_SELL_FILLED, MSG_STATUS_REPORT
)
from utils.file_io import save_state, load_state
from utils.logger import append_trade_log, load_trade_history, get_profit_stats
from utils.log_config import logger
from shared.state import update_strategy_info, update_strategy_info_batch, get_strategy_info

def calculate_price(base_price, gap_value, mode, direction):
    """가격을 퍼센트 또는 고정 금액으로 계산 (헬퍼 함수)"""
    if mode == 'percent':
        rate = (1 + gap_value / 100) if direction == 'up' else (1 - gap_value / 100)
        return round(base_price * rate, 2)
    elif mode == 'price':
        return round(base_price + gap_value, 2) if direction == 'up' else round(base_price - gap_value, 2)
    else:
        raise ValueError("mode는 'percent' 또는 'price' 여야 합니다.")

class GridLevel:
    """각 차수의 매수/매도 가격과 상태를 관리하는 클래스"""
    def __init__(self, level, buy_price, sell_price, volume):
        self.level = level
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.volume = volume
        self.buy_uuid = None
        self.sell_uuid = None
        self.buy_filled = False
        self.sell_filled = False

    def to_dict(self):
        return {
            "level": self.level,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "volume": self.volume,
            "buy_uuid": self.buy_uuid,
            "sell_uuid": self.sell_uuid,
            "buy_filled": self.buy_filled,
            "sell_filled": self.sell_filled,
        }

    @classmethod
    def from_dict(cls, data):
        level = cls(data["level"], data["buy_price"], data["sell_price"], data["volume"])
        level.buy_uuid = data.get("buy_uuid")
        level.sell_uuid = data.get("sell_uuid")
        level.buy_filled = data.get("buy_filled", False)
        level.sell_filled = data.get("sell_filled", False)
        return level

class AutoTradeManager:
    """자동매매 전략 실행 및 관리 클래스"""
    def __init__(self, start_price, krw_amount, max_levels, buy_gap, buy_mode, 
                 sell_gap, sell_mode, market_code='USDT', sleep_sec=SLEEP_SEC,
                 stop_condition=None, status_callback=None, summary_callback=None):
        
        self.market_code = market_code.upper()
        self.market = f"KRW-{self.market_code}"
        self.start_price = start_price
        self.krw_amount = krw_amount
        self.max_levels = max_levels
        self.buy_gap = buy_gap
        self.buy_mode = buy_mode
        self.sell_gap = sell_gap
        self.sell_mode = sell_mode
        self.sleep_sec = sleep_sec
        
        self.stop_condition = stop_condition
        self.status_callback = status_callback
        self.summary_callback = summary_callback
        
        self.tick = get_tick_size(self.market)
        self.levels = []
        self.realized_profit = 0.0
        self.trade_count = 0
        self.trade_history = []
        
        self.is_placing_orders = False
        self.reorder_lock = {'buy': set(), 'sell': set()}
        self.health_check_counter = 0
        self.last_report_hour = datetime.now().hour
        self.fast_mode_ticks = 0
        self.telegram_bot = None

    def initialize_levels(self):
        """차수별 그리드 레벨 생성"""
        self.levels = []
        for i in range(self.max_levels):
            raw_buy_price = calculate_price(self.start_price, self.buy_gap * i, self.buy_mode, 'down')
            raw_sell_price = calculate_price(raw_buy_price, self.sell_gap, self.sell_mode, 'up')
            
            buy_price = math.floor(raw_buy_price / self.tick) * self.tick
            sell_price = math.floor(raw_sell_price / self.tick) * self.tick
            volume = round(self.krw_amount / buy_price, 8)
            
            self.levels.append(GridLevel(i + 1, buy_price, sell_price, volume))

    def persist_state(self):
        """현재 상태를 JSON 파일로 저장"""
        snapshot = {
            "market": self.market,
            "start_price": self.start_price,
            "krw_amount": self.krw_amount,
            "max_levels": self.max_levels,
            "buy_gap": self.buy_gap,
            "buy_mode": self.buy_mode,
            "sell_gap": self.sell_gap,
            "sell_mode": self.sell_mode,
            "realized_profit": self.realized_profit,
            "levels": [lv.to_dict() for lv in self.levels],
            "trade_history": self.trade_history[-100:],  # 최근 100건만 저장
        }
        save_state(snapshot, self.market)

    def _params_match(self, state):
        """저장된 상태의 파라미터가 현재와 일치하는지 확인"""
        return (
            state.get("market") == self.market and
            state.get("start_price") == self.start_price and
            state.get("krw_amount") == self.krw_amount and
            state.get("max_levels") == self.max_levels and
            state.get("buy_gap") == self.buy_gap and
            state.get("buy_mode") == self.buy_mode and
            state.get("sell_gap") == self.sell_gap and
            state.get("sell_mode") == self.sell_mode
        )

    def resume_or_init(self, resume_level=0):
        """상태 복원 또는 초기화"""
        # 영구 로그에서 누적 수익 복원
        self.realized_profit, self.trade_count = load_trade_history(self.market)
        
        # 수동 재시작 처리
        if resume_level > 0:
            print(f"🔄 수동 재시작: {resume_level}차부터 시작합니다.")
            self.initialize_levels()
            # 모든 기존 주문 취소
            cancel_all_orders(self.market)
            time.sleep(2.0)
            
            # resume_level-1 차수까지는 매수 체결 상태로 설정
            for i in range(resume_level - 1):
                self.levels[i].buy_filled = True
            
            self.place_multi_orders(resume_level - 1, MULTI_ORDER_COUNT)
            self.persist_state()
            
            msg = f"🔄 [수동 재시작]\n📍코인: {self.market}\n🔢 재시작 차수: {resume_level}차\n💰 누적 수익: {self.realized_profit:,.0f}원"
            send_telegram_message(msg)
            return

        # 자동 복원 시도
        loaded_state = load_state(self.market)
        if loaded_state and self._params_match(loaded_state):
            logger.info(f"⏯️ 기존 상태 발견. {self.market} 재개 / 누적 수익: {self.realized_profit:,.0f}원")
            self.levels = [GridLevel.from_dict(lv) for lv in loaded_state.get("levels", [])]
            self.trade_history = loaded_state.get("trade_history", [])
            
            # 잔고 기반 복구 및 누락 주문 재연결
            self.recover_from_balance()
            self.reattach_missing_orders()
            self.cleanup_orphan_orders()
            
            # 필요한 주문 재등록
            self.ensure_active_orders()
            self.persist_state()
        else:
            # 신규 시작
            logger.info(f"📊 자동 매매 신규 시작: {self.market}")
            self.initialize_levels()
            self.place_multi_orders(0, MULTI_ORDER_COUNT)
            self.persist_state()
            send_telegram_message(MSG_AUTO_TRADE_START.format(
                market=self.market, max_levels=self.max_levels, 
                start_price=self.start_price, krw_amount=self.krw_amount
            ))

        # 일별/월별 수익 복원
        today_p, monthly_p = get_profit_stats(self.market)
        update_strategy_info_batch({
            "market": self.market,
            "start_price": self.start_price,
            "current_price": self.start_price,
            "realized_profit": self.realized_profit,
            "today_profit": today_p,
            "monthly_profit": monthly_p
        })

        # 텔레그램 원격 제어 봇 시작
        try:
            from utils.telegram_bot import TelegramCommandBot
            self.telegram_bot = TelegramCommandBot(manager=self)
            self.telegram_bot.start()
        except Exception as e:
            logger.warning(f"텔레그램 봇 시작 실패: {e}")

    def recover_from_balance(self):
        """잔고를 확인하여 체결 상태를 보정 (UUID가 없을 때 대비)"""
        try:
            from api.api import get_balance
            balance_data = get_balance()
            coin_balance = 0.0
            
            if isinstance(balance_data, list):
                for item in balance_data:
                    if item.get('currency') == self.market_code:
                        coin_balance = float(item.get('balance', 0)) + float(item.get('locked', 0))
                        break
            
            if coin_balance > 0.000001:
                total_expected = sum(lv.volume for lv in self.levels if lv.buy_filled and not lv.sell_filled)
                diff_ratio = abs(coin_balance - total_expected) / max(total_expected, 0.00000001)
                
                if diff_ratio > 0.1:
                    print(f"⚠️ 잔고 불일치 감지: 예상 {total_expected:.8f} vs 실제 {coin_balance:.8f} → 재구성 시도")
                    remaining = coin_balance
                    reconstructed = []
                    for lvl in reversed(self.levels):
                        if remaining >= lvl.volume * 0.99:
                            lvl.buy_filled = True
                            lvl.sell_filled = False
                            lvl.buy_uuid = lvl.sell_uuid = None
                            remaining -= lvl.volume
                            reconstructed.append(lvl.level)
                    
                    if reconstructed:
                        send_telegram_message(f"🔄 [잔고 기반 복구]\n📍코인: {self.market}\n📊 복구된 차수: {', '.join(map(str, sorted(reconstructed)))}차")
        except Exception as e:
            print(f"⚠️ 잔고 기반 복구 오류: {e}")

    def reattach_missing_orders(self):
        """실제 주문이 있지만 UUID가 없는 경우 다시 연결"""
        active_orders, _ = self.build_active_orders()
        if not active_orders: return

        reattached = []
        for lv in self.levels:
            if not lv.buy_filled and not lv.buy_uuid:
                uuid = self.find_matching_order(active_orders, 'bid', lv.buy_price, lv.volume)
                if uuid:
                    lv.buy_uuid = uuid
                    reattached.append(f"{lv.level}차 매수")
            if lv.buy_filled and not lv.sell_filled and not lv.sell_uuid:
                uuid = self.find_matching_order(active_orders, 'ask', lv.sell_price, lv.volume)
                if uuid:
                    lv.sell_uuid = uuid
                    reattached.append(f"{lv.level}차 매도")
        
        if reattached:
            print(f"🔗 누락 UUID 복구: {', '.join(reattached)}")

    def cleanup_orphan_orders(self):
        """전략에 포함되지 않은 고아 주문 제거"""
        try:
            active_orders, _ = self.build_active_orders()
            tracked_uuids = set()
            for lv in self.levels:
                if lv.buy_uuid: tracked_uuids.add(lv.buy_uuid)
                if lv.sell_uuid: tracked_uuids.add(lv.sell_uuid)
            
            orphans = [uuid for uuid in active_orders if uuid not in tracked_uuids]
            for uuid in orphans:
                print(f"🗑️ 고아 주문 제거: {uuid[:8]}...")
                cancel_order_by_uuid(uuid)
            if orphans:
                send_telegram_message(f"🗑️ [고아 주문 정리]\n📍코인: {self.market}\n🔢 취소된 주문: {len(orphans)}개")
        except Exception as e:
            print(f"⚠️ 고아 주문 정리 오류: {e}")

    def ensure_active_orders(self):
        """재시작 시 필요한 최소한의 주문이 있는지 확인하고 보충"""
        last_filled = max([lv.level for lv in self.levels if lv.buy_filled], default=0)
        has_pending = any(lv.buy_uuid or lv.sell_uuid for lv in self.levels)
        if not has_pending:
            print(f"🔄 주문 없음 감지 → {last_filled}차 기준 다중 주문 재등록")
            self.place_multi_orders(last_filled, MULTI_ORDER_COUNT)

    def build_active_orders(self):
        """현재 미체결 주문 목록 조회 및 매핑"""
        try:
            order_list = get_order_list(market=self.market, state='wait')
            if not isinstance(order_list, list): return {}, None
            
            active = {}
            for o in order_list:
                uuid = o.get('uuid') or o.get('order_id')
                if uuid:
                    active[uuid] = {
                        'side': o.get('side'),
                        'price': float(o.get('price', 0)),
                        'volume': float(o.get('volume', 0))
                    }
            return active, order_list
        except Exception as e:
            print(f"⚠️ 주문 조회 실패: {e}")
            return {}, None

    def find_matching_order(self, active_orders, side, target_price, target_volume):
        """가격/수량이 유사한 주문 검색"""
        price_tol = max(self.tick, target_price * 0.001)
        volume_tol = max(target_volume * 0.02, 1e-10)
        for uuid, info in active_orders.items():
            if info['side'] == side and \
               abs(info['price'] - target_price) <= price_tol and \
               abs(info['volume'] - target_volume) <= volume_tol:
                return uuid
        return None

    def place_buy(self, level, auto_recovery=False):
        if level.buy_uuid and not level.buy_filled: return True
        
        res = place_order(self.market, 'bid', level.volume, level.buy_price, 'limit')
        uuid = res.get('uuid') or res.get('data', {}).get('uuid')
        if uuid:
            level.buy_uuid = uuid
            print(f"{'🔄' if auto_recovery else '🛒'} [{level.level}차] 매수 주문 등록: {level.buy_price}원")
            msg = MSG_BUY_ORDER.format(market=self.market, level=level.level, buy_price=level.buy_price, volume=level.volume, order_time=datetime.now().strftime('%H:%M:%S'))
            if auto_recovery: msg = msg.replace("🛒 [매수", "🔄 [자동복구 - 매수")
            send_telegram_message(msg)
            # 즉시 체결 확인
            time.sleep(0.5)
            self._check_instant_fill(level, 'buy')
            return True
        return False

    def place_sell(self, level, auto_recovery=False):
        if level.sell_uuid and not level.sell_filled: return True
        
        res = place_order(self.market, 'ask', level.volume, level.sell_price, 'limit')
        uuid = res.get('uuid') or res.get('data', {}).get('uuid')
        if uuid:
            level.sell_uuid = uuid
            print(f"{'🔄' if auto_recovery else '📤'} [{level.level}차] 매도 주문 등록: {level.sell_price}원")
            msg = MSG_SELL_ORDER.format(market=self.market, level=level.level, sell_price=level.sell_price, volume=level.volume, order_time=datetime.now().strftime('%H:%M:%S'))
            if auto_recovery: msg = msg.replace("📤 [매도", "🔄 [자동복구 - 매도")
            send_telegram_message(msg)
            # 즉시 체결 확인
            time.sleep(0.5)
            self._check_instant_fill(level, 'sell')
            return True
        return False

    def _check_instant_fill(self, level, side):
        uuid = level.buy_uuid if side == 'buy' else level.sell_uuid
        detail = get_order_detail(uuid)
        data = detail.get('data') or detail
        filled, _, _ = self._is_order_filled(data)
        if filled:
            if side == 'buy': level.buy_filled = True
            else: level.sell_filled = True
            print(f"⚡ [{level.level}차] {side} 즉시 체결 감지!")

    def _is_order_filled(self, data):
        state = str(data.get('state') or data.get('ord_state') or '').lower()
        executed = float(data.get('executed_volume', 0) or 0)
        remaining = float(data.get('remaining_volume', 0) or 0)
        
        if state in ('done', 'filled', 'completed') or (executed > 0 and remaining <= 1e-12):
            return True, executed, remaining
        return False, executed, remaining

    def place_multi_orders(self, last_filled_buy, count=MULTI_ORDER_COUNT, sell_filled_mode=False):
        self.is_placing_orders = True
        sell_added = []
        buy_added = []
        
        if last_filled_buy == 0:
            for i in range(count):
                if i < len(self.levels):
                    if self.place_buy(self.levels[i]): buy_added.append(i+1)
                    time.sleep(0.2)
        elif sell_filled_mode:
            for i in range(count):
                idx = last_filled_buy - 1 - i
                if 0 <= idx < len(self.levels) and not self.levels[idx].buy_filled:
                    if self.place_buy(self.levels[idx]): buy_added.append(idx+1)
                    time.sleep(0.2)
            for i in range(count):
                idx = last_filled_buy - 2 - i
                if 0 <= idx < len(self.levels) and self.levels[idx].buy_filled and not self.levels[idx].sell_filled:
                    if self.place_sell(self.levels[idx]): sell_added.append(idx+1)
                    time.sleep(0.2)
        else:
            for i in range(count):
                idx = last_filled_buy - 1 - i
                if 0 <= idx < len(self.levels) and self.levels[idx].buy_filled and not self.levels[idx].sell_filled:
                    if self.place_sell(self.levels[idx]): sell_added.append(idx+1)
                    time.sleep(0.2)
            for i in range(count):
                idx = last_filled_buy + i
                if 0 <= idx < len(self.levels) and not self.levels[idx].buy_filled:
                    if self.place_buy(self.levels[idx]): buy_added.append(idx+1)
                    time.sleep(0.2)

        self.is_placing_orders = False
        print(f"🎯 [다중 주문 완료] 매수: {buy_added}, 매도: {sell_added}")
        return sell_added, buy_added

    def perform_health_check(self):
        """전체 주문 상태 검증 및 자동 복구 (상태 기반)"""
        try:
            print(f"🏥 [헬스체크] {self.market} 상태 검증 중...")
            
            # 1단계: 모든 UUID의 실제 체결 상태를 거래소에서 확인
            for lv in self.levels:
                if lv.buy_uuid and not lv.buy_filled:
                    try:
                        detail = get_order_detail(lv.buy_uuid)
                        data = detail.get('data') or detail
                        filled, _, _ = self._is_order_filled(data)
                        if filled:
                            lv.buy_filled = True
                            print(f"  🔍 {lv.level}차 매수 체결 확인 (헬스체크)")
                    except Exception:
                        pass
                    time.sleep(0.1)

                if lv.sell_uuid and not lv.sell_filled:
                    try:
                        detail = get_order_detail(lv.sell_uuid)
                        data = detail.get('data') or detail
                        filled, _, _ = self._is_order_filled(data)
                        if filled:
                            lv.sell_filled = True
                            # 매도 체결 시 수익 처리
                            buy_cost = lv.buy_price * (1 + FEE_RATE)
                            sell_income = lv.sell_price * (1 - FEE_RATE)
                            profit = (sell_income - buy_cost) * lv.volume
                            self.realized_profit += profit
                            append_trade_log(self.market, lv.level, lv.buy_price, lv.sell_price, lv.volume, profit, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            lv.buy_uuid = lv.sell_uuid = None
                            lv.buy_filled = lv.sell_filled = False
                            print(f"  🔍 {lv.level}차 매도 체결 확인 (수익 {profit:.0f}원)")
                    except Exception:
                        pass
                    time.sleep(0.1)

            self.persist_state()

            # 2단계: 실제 거래소 미체결 주문 조회
            active_orders, order_list = self.build_active_orders()
            if order_list is None:
                print("  ⚠️ 주문 목록 조회 실패 - 헬스체크 스킵")
                return

            # 3단계: UUID 재연결 (내부 상태에 UUID가 없지만 거래소에 주문이 있는 경우)
            self.reattach_missing_orders()

            # 4단계: 상태 기반으로 필요한 주문 계산 (핵심 수정)
            # 매도가 필요한 차수: buy_filled=True, sell_filled=False, sell_uuid=None
            needs_sell = [lv for lv in self.levels if lv.buy_filled and not lv.sell_filled and not lv.sell_uuid]
            # 매수가 필요한 차수: buy_filled=False, buy_uuid=None (단, 연속된 다음 차수만)
            last_filled = max([lv.level for lv in self.levels if lv.buy_filled], default=0)
            needs_buy = []
            for i in range(MULTI_ORDER_COUNT):
                idx = last_filled + i  # last_filled=0이면 0,1 / last_filled=20이면 20,21
                if idx < len(self.levels) and not self.levels[idx].buy_filled and not self.levels[idx].buy_uuid:
                    needs_buy.append(self.levels[idx])

            if not needs_sell and not needs_buy:
                print("✅ 상태 정상")
                self._health_fail_count = 0
                return

            # 5단계: 연속 실패 방지 (서킷 브레이커)
            if not hasattr(self, '_health_fail_count'):
                self._health_fail_count = 0
            self._health_fail_count += 1

            if self._health_fail_count > 5:
                print(f"🚫 헬스체크 연속 {self._health_fail_count}회 불일치 - 전체 재구성")
                send_telegram_message(
                    f"🚫 [서킷 브레이커 발동]\n📍코인: {self.market}\n"
                    f"⚠️ 연속 {self._health_fail_count}회 복구 실패\n"
                    f"🔄 전체 주문 취소 후 재구성 시도"
                )
                # 전체 취소 후 재구성
                try:
                    from api.api import cancel_all_orders
                    cancel_all_orders(self.market)
                    time.sleep(1.0)
                except Exception as e:
                    print(f"  ⚠️ 전체 취소 실패: {e}")
                
                for lv in self.levels:
                    lv.buy_uuid = lv.sell_uuid = None
                
                self.place_multi_orders(last_filled, MULTI_ORDER_COUNT)
                self.persist_state()
                self._health_fail_count = 0
                return

            # 6단계: 부족한 주문 등록
            recovery_actions = []
            for lv in needs_sell:
                print(f"  📤 {lv.level}차 매도 복구 등록 (매수 체결됨, 매도 주문 없음)")
                if self.place_sell(lv, auto_recovery=True):
                    recovery_actions.append(f"{lv.level}차 매도")
                time.sleep(0.2)

            for lv in needs_buy:
                print(f"  🛒 {lv.level}차 매수 복구 등록")
                if self.place_buy(lv, auto_recovery=True):
                    recovery_actions.append(f"{lv.level}차 매수")
                time.sleep(0.2)

            self.persist_state()

            if recovery_actions:
                send_telegram_message(
                    f"✅ [자동복구 완료]\n📍코인: {self.market}\n"
                    f"🔄 복구된 주문: {', '.join(recovery_actions)}"
                )
                print(f"✅ 복구 완료: {', '.join(recovery_actions)}")

        except Exception as e:
            print(f"⚠️ 헬스체크 오류: {e}")
            import traceback
            print(traceback.format_exc())

    def send_status_report(self):
        """정기 상태 보고 (매 정시 전송, 자정에는 일별/월별 성과 추가)"""
        try:
            current_price = get_current_price(self.market) or self.start_price
            update_strategy_info("current_price", current_price)
            
            # 수익 통계 갱신
            today_p, monthly_p = get_profit_stats(self.market)
            update_strategy_info_batch({
                "today_profit": today_p,
                "monthly_profit": monthly_p
            })
            
            active_orders, _ = self.build_active_orders()
            order_lines = []
            for uuid, info in active_orders.items():
                side = "매수" if info['side'] == 'bid' else "매도"
                order_lines.append(f"  • {side}: {info['price']:,.0f}원 ({info['volume']:.6f})")
            
            now = datetime.now()
            
            # 기본 보고 내용
            report = MSG_STATUS_REPORT.format(
                report_time=now.strftime('%Y-%m-%d %H:%M:%S'),
                market=self.market,
                start_price=self.start_price,
                current_price=current_price,
                realized_profit=self.realized_profit,
                order_status="\n".join(order_lines) if order_lines else "미체결 주문 없음",
                strategy_status=f"진행 차수: {max([lv.level for lv in self.levels if lv.buy_filled], default=0)}차"
            )
            
            # 밤 12시(자정)인 경우 수익 요약 추가
            if now.hour == 0:
                summary_report = (
                    "\n💰 <b>[수익 요약 보고]</b>\n"
                    f"📅 오늘 수익: <b>{today_p:,.0f}원</b>\n"
                    f"🗓️ 이번 달 수익: <b>{monthly_p:,.0f}원</b>\n"
                    f"🏆 총 누적 수익: <b>{self.realized_profit:,.0f}원</b>"
                )
                report += summary_report
                
            send_telegram_message(report)
        except Exception as e:
            print(f"⚠️ 보고서 생성 오류: {e}")

    def run(self):
        """메인 실행 루프"""
        print(f"🚀 {self.market} 자동매매 루프 시작")
        self.health_check_counter = 0
        
        while True:
            if self.stop_condition and self.stop_condition():
                print("🛑 중단 요청 감지")
                break
            
            try:
                # 주문 체결 확인 로직
                for lv in self.levels:
                    # 매수 체결 확인
                    if lv.buy_uuid and not lv.buy_filled:
                        detail = get_order_detail(lv.buy_uuid)
                        filled, _, _ = self._is_order_filled(detail.get('data') or detail)
                        if filled:
                            lv.buy_filled = True
                            print(f"✅ [{lv.level}차] 매수 체결")
                            send_telegram_message(MSG_BUY_FILLED.format(market=self.market, level=lv.level, buy_price=lv.buy_price, volume=lv.volume, filled_time=datetime.now().strftime('%H:%M:%S')))
                            if self.status_callback: self.status_callback(lv.level, f"[{lv.level}차] 매수 체결 ✅")
                            self.place_multi_orders(lv.level, MULTI_ORDER_COUNT)
                            self.persist_state()
                    
                    # 매도 체결 확인
                    if lv.sell_uuid and not lv.sell_filled:
                        detail = get_order_detail(lv.sell_uuid)
                        filled, _, _ = self._is_order_filled(detail.get('data') or detail)
                        if filled:
                            lv.sell_filled = True
                            buy_cost = lv.buy_price * (1 + FEE_RATE)
                            sell_income = lv.sell_price * (1 - FEE_RATE)
                            profit = (sell_income - buy_cost) * lv.volume
                            self.realized_profit += profit
                            update_strategy_info("realized_profit", self.realized_profit)
                            
                            append_trade_log(self.market, lv.level, lv.buy_price, lv.sell_price, lv.volume, profit, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            
                            print(f"💰 [{lv.level}차] 매도 체결 / 수익 {profit:.0f}원")
                            send_telegram_message(MSG_SELL_FILLED.format(market=self.market, level=lv.level, sell_price=lv.sell_price, volume=lv.volume, profit=profit, realized_profit=self.realized_profit, filled_time=datetime.now().strftime('%H:%M:%S')))
                            
                            # 초기화
                            lv.buy_uuid = lv.sell_uuid = None
                            lv.buy_filled = lv.sell_filled = False
                            
                            # 수익 통계 갱신 (GUI 연동용)
                            today_p, monthly_p = get_profit_stats(self.market)
                            update_strategy_info_batch({
                                "today_profit": today_p,
                                "monthly_profit": monthly_p
                            })
                            
                            if self.status_callback: self.status_callback(lv.level, f"[{lv.level}차] 매도 체결 ✅")
                            if self.summary_callback: self.summary_callback()
                            self.place_multi_orders(lv.level, MULTI_ORDER_COUNT, sell_filled_mode=True)
                            self.persist_state()

                # 주기적 작업
                self.health_check_counter += 1
                if self.health_check_counter >= HEALTH_CHECK_INTERVAL:
                    if not self.is_placing_orders:
                        self.perform_health_check()
                        self.health_check_counter = 0
                
                now = datetime.now()
                if now.minute == 0 and now.hour != self.last_report_hour:
                    self.send_status_report()
                    self.last_report_hour = now.hour
                
            except Exception as e:
                print(f"⚠️ 루프 에러: {e}")
                time.sleep(5)
            
            time.sleep(self.sleep_sec)

def run_auto_trade(**kwargs):
    """하위 호환성을 위한 래퍼 함수"""
    manager = AutoTradeManager(**kwargs)
    manager.resume_or_init(resume_level=kwargs.get('resume_level', 0))
    manager.run()

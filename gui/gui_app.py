## File: gui/gui_app.py
# bithumbSplit GUI Application

import os
import sys
import customtkinter as ctk
import threading
import time
import webbrowser
from datetime import datetime
from tkinter import messagebox
import queue
from pathlib import Path

# Windows DPI Awareness 설정 (글씨 흐림 방지)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# 프로젝트 루트를 sys.path에 추가
if getattr(sys, 'frozen', False):
    base_path = Path(sys.executable).parent
else:
    base_path = Path(__file__).parent.parent

if str(base_path) not in sys.path:
    sys.path.insert(0, str(base_path))

from strategy.auto_trade import run_auto_trade
from utils.telegram import send_telegram_message
from api.api import cancel_all_orders, get_current_price
from shared.state import strategy_info
from config.settings import (
    SUPPORTED_COINS, MIN_AMOUNT, MAX_AMOUNT, MIN_LEVELS, MAX_LEVELS,
    MIN_GAP, MAX_GAP, PRICE_UPDATE_INTERVAL, REQUIRED_DIRS
)

# 필수 디렉토리 생성
for dir_name in REQUIRED_DIRS:
    os.makedirs(os.path.join(base_path, dir_name), exist_ok=True)

# CustomTkinter 설정
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# GUI 앱 생성
app = ctk.CTk()
app.title("bithumbSplit")

# 화면 크기 감지 및 창 크기 동적 설정
screen_width = app.winfo_screenwidth()
screen_height = app.winfo_screenheight()

# 화면 크기의 85%로 설정 (최소 600x700, 최대 700x1000)
window_width = min(max(int(screen_width * 0.4), 600), 700)
window_height = min(max(int(screen_height * 0.85), 700), 1000)

# 창을 화면 중앙에 배치
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2

app.geometry(f"{window_width}x{window_height}+{x}+{y}")
app.minsize(600, 700)  # 최소 크기 설정

# 전역 변수
stop_flag = False
running_flag = False
summary_labels = {}
status_queue = queue.Queue()  # 스레드 간 통신을 위한 큐
current_buy_level = 0  # 현재 매수 차수
current_sell_level = 0  # 현재 매도 차수
label_status = None
current_level_label = None
status_text_label = None

def stop_condition():
    return stop_flag

realized_profit = 0.0

# 실시간 시세 표시용 변수
price_labels = {}

# 실시간 시세 업데이트 함수
def update_price_info():
    """실시간 시세 업데이트 함수 - 수정된 버전"""
    def loop():
        while True:
            try:
                # 현재 시간 업데이트
                now = datetime.now().strftime("%H:%M:%S")
                
                # 메인 스레드에서 안전하게 시간 업데이트
                def update_time():
                    if "time" in price_labels:
                        price_labels["time"].configure(text=f"⏱️ {now}")
                
                app.after(0, update_time)
                
                # 코인 가격 업데이트
                coins = ["BTC", "ETH", "USDT", "XRP"]
                strategy_market = strategy_info.get("market")  # 이미 "KRW-XRP" 형식
                
                # strategy_market이 있으면 코인 이름만 추출하여 추가
                if strategy_market and isinstance(strategy_market, str) and "-" in strategy_market:
                    parts = strategy_market.split("-")
                    if len(parts) == 2 and parts[1]:  # "KRW-XRP" 형식 확인
                        strategy_coin_name = parts[1]
                        if strategy_coin_name and strategy_coin_name not in coins:
                            coins.append(strategy_coin_name)
                    
                for coin in coins:
                    # 빈 문자열 체크
                    if not coin or not isinstance(coin, str):
                        continue
                    try:
                        market_code = f"KRW-{coin}"
                        price = get_current_price(market_code)  # api.py 함수 사용
                        
                        def update_coin_price(c=coin, p=price):
                            if c in price_labels:
                                if p:
                                    price_labels[c].configure(text=f"{c}: {p:,.0f} KRW")
                                else:
                                    price_labels[c].configure(text=f"{c}: 조회 실패")
                        
                        app.after(0, update_coin_price)
                        
                        # 전략 코인의 현재가 업데이트
                        if market_code == strategy_market:
                            strategy_info["current_price"] = price
                            app.after(0, update_strategy_summary)

                    except Exception as e:
                        print(f"[ERROR] {coin} 가격 조회 중 오류: {e}")
                        
                        def update_error(c=coin):
                            if c in price_labels:
                                price_labels[c].configure(text=f"{c}: 오류")
                        
                        app.after(0, update_error)
                
            except Exception as e:
                print(f"[ERROR] 전체 가격 업데이트 오류: {e}")

            # 설정된 간격만큼 대기
            time.sleep(PRICE_UPDATE_INTERVAL)
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    print("[INFO] 실시간 가격 업데이트 스레드 시작됨")

# 전략 요약 정보 업데이트 함수
def update_strategy_summary():
    try:
        info = get_strategy_info()
        current = info.get("current_price", 0)
        start = info.get("start_price", 0)
        profit = info.get("realized_profit", 0)

        summary_labels["market"].configure(text=f"코인: {info['market']}")
        summary_labels["start_price"].configure(text=f"시작가: {start:,.0f} KRW")
        summary_labels["current_price"].configure(text=f"현재가: {current:,.0f} KRW")
        summary_labels["today_profit"].configure(
            text=f"오늘 수익: {info.get('today_profit', 0):,.0f} KRW",
            text_color="green" if info.get('today_profit', 0) >= 0 else "red"
        )
        summary_labels["monthly_profit"].configure(
            text=f"이번 달 수익: {info.get('monthly_profit', 0):,.0f} KRW"
        )
        summary_labels["profit"].configure(
            text=f"총 누적 수익: {profit:,.0f} KRW", 
            text_color="green" if profit >= 0 else "red"
        )
    except Exception as e:
        print(f"[ERROR] update_strategy_summary: {e}")


def update_order_status(level, text):
    """주문 상태 업데이트 - 매수/매도 동시 표시"""
    try:
        # 큐에 업데이트 정보 추가
        status_queue.put(("order_status", level, text))
        # 메인 스레드에서 처리하도록 스케줄링
        app.after(0, process_status_updates)
    except Exception as e:
        print(f"[ERROR] update_order_status: {e}")

def process_status_updates():
    """큐에서 상태 업데이트 처리"""
    global current_buy_level, current_sell_level
    try:
        while not status_queue.empty():
            update_type, level, text = status_queue.get_nowait()
            
            if update_type == "order_status":
                # 매수/매도 상태 추적
                if "매수 주문" in text or "매수 체결" in text:
                    current_buy_level = level
                if "매도 주문" in text or "매도 체결" in text:
                    current_sell_level = level
                
                # 현재 차수 정보 표시
                def update_current_level():
                    # 매수 정보 표시
                    buy_info = f"🛒 {current_buy_level}차 매수" if current_buy_level > 0 else "🛒 매수 대기"
                    sell_info = f"📤 {current_sell_level}차 매도" if current_sell_level > 0 else "📤 매도 대기"
                    
                    current_level_label.configure(text=f"{buy_info}  |  {sell_info}")
                    
                    # 상태 텍스트 표시
                    status_text_label.configure(text=text)
                    
                    # 상태에 따라 색상 변경
                    if "매도 체결" in text:
                        status_text_label.configure(text_color="green")
                    elif "매수 체결" in text:
                        status_text_label.configure(text_color="orange")
                    elif "매수 주문" in text or "매도 주문" in text:
                        status_text_label.configure(text_color="yellow")
                    else:
                        status_text_label.configure(text_color="white")
                
                app.after(0, update_current_level)
                        
    except Exception as e:
        print(f"[ERROR] process_status_updates: {e}")

def initialize_order_cards(max_levels):
    """주문 상태 초기화 - 현재 차수만 표시하므로 불필요"""
    try:
        # 초기 상태 표시
        current_level_label.configure(text="🛒 매수 대기  |  📤 매도 대기")
        status_text_label.configure(text="⏳ 주문 상태를 기다리는 중...")
    except Exception as e:
        print(f"[ERROR] initialize_order_cards: {e}")

def start_strategy():
    """전략 시작"""
    global stop_flag, running_flag

    if running_flag:
        messagebox.showwarning("알림", "이미 전략이 실행 중입니다.")
        return

    # 입력값 파싱 및 기본 검증
    try:
        market = entry_market.get().strip().upper()
        start_price = float(entry_price.get())
        krw_amount = float(entry_amount.get())
        max_levels = int(entry_rounds.get())
        buy_gap = float(entry_buy_gap.get())
        sell_gap = float(entry_sell_gap.get())
        resume_level_str = entry_resume_level.get().strip()
        resume_level = int(resume_level_str) if resume_level_str else 0
    except ValueError:
        messagebox.showerror("입력 오류", "숫자 필드에 올바른 값을 입력해주세요.")
        return

    if not market:
        messagebox.showerror("입력 오류", "코인을 입력해주세요.")
        return
    
    # 코인 검증
    if market not in SUPPORTED_COINS:
        if not messagebox.askyesno(
            "확인 필요",
            f"{market}은(는) 확인되지 않은 코인입니다.\n\n"
            f"지원 코인: {', '.join(SUPPORTED_COINS[:15])} 외 {len(SUPPORTED_COINS)-15}개\n\n"
            f"계속 진행하시겠습니까?"
        ):
            return
    
    if start_price <= 0:
        messagebox.showerror("입력 오류", "시작가는 0보다 커야 합니다.")
        return
    
    # 매수 금액 범위 검증
    if not (MIN_AMOUNT <= krw_amount <= MAX_AMOUNT):
        messagebox.showerror(
            "입력 오류",
            f"매수금액은 {MIN_AMOUNT:,}원 ~ {MAX_AMOUNT:,}원 사이여야 합니다."
        )
        return
    
    # 차수 범위 검증
    if not (MIN_LEVELS <= max_levels <= MAX_LEVELS):
        messagebox.showerror(
            "입력 오류",
            f"최대차수는 {MIN_LEVELS} ~ {MAX_LEVELS} 사이여야 합니다."
        )
        return
    
    # 간격 범위 검증 (퍼센트 모드일 때)
    if buy_mode.get() == 'percent' and not (MIN_GAP <= buy_gap <= MAX_GAP):
        messagebox.showerror(
            "입력 오류",
            f"매수 간격은 {MIN_GAP}% ~ {MAX_GAP}% 사이여야 합니다."
        )
        return
    
    if sell_mode.get() == 'percent' and not (MIN_GAP <= sell_gap <= MAX_GAP):
        messagebox.showerror(
            "입력 오류",
            f"매도 간격은 {MIN_GAP}% ~ {MAX_GAP}% 사이여야 합니다."
        )
        return
    
    # 가격 모드일 때 간격 검증 (시작가의 50% 이내)
    if buy_mode.get() == 'price' and buy_gap > start_price * 0.5:
        messagebox.showerror(
            "입력 오류",
            f"매수 간격은 시작가({start_price:,.0f}원)의 50% 이하여야 합니다."
        )
        return
    
    if sell_mode.get() == 'price' and sell_gap > start_price * 0.5:
        messagebox.showerror(
            "입력 오류",
            f"매도 간격은 시작가({start_price:,.0f}원)의 50% 이하여야 합니다."
        )
        return
    if resume_level < 0 or resume_level > max_levels:
        messagebox.showerror("입력 오류", f"재시작 차수는 0~{max_levels} 사이여야 합니다.")
        return

    # 간격 경고 (수수료 대비 수익성)
    from config.settings import FEE_RATE
    min_profitable_gap = FEE_RATE * 2 * 100 * 1.5  # 수수료의 1.5배 이상 권장
    if buy_mode.get() == 'percent' and buy_gap < min_profitable_gap:
        if not messagebox.askyesno("주의", f"매수 간격({buy_gap}%)이 매우 좁습니다.\n수수료({FEE_RATE*100:.3f}%)를 고려할 때 수익성이 낮을 수 있습니다.\n계속하시겠습니까?"):
            return

    estimated_cost = krw_amount * max_levels
    if estimated_cost > 10000000:  # 1000만원 이상
        if not messagebox.askokcancel(
            "확인",
            f"예상 총 비용: {estimated_cost:,.0f}원\n\n진행하시겠습니까?"
        ):
            return

    # 최종 실행 확인 (오입력/오클릭 방지)
    confirm_msg = (
        "전략을 시작하시겠습니까?\n\n"
        f"코인: {market}\n"
        f"시작가: {start_price:,.0f}원\n"
        f"매수금액: {krw_amount:,.0f}원\n"
        f"최대차수: {max_levels}차\n"
        f"매수간격: {buy_gap} ({buy_mode.get()})\n"
        f"매도간격: {sell_gap} ({sell_mode.get()})\n"
        f"재시작 차수: {resume_level if resume_level else '새 시작'}"
    )
    if not messagebox.askokcancel("전략 실행 확인", confirm_msg):
        return

    # 상태 플래그/버튼 업데이트
    stop_flag = False
    running_flag = True
    btn_start.configure(state="disabled")
    btn_stop.configure(state="normal")
    label_status.configure(text="🚀 전략 실행 중", text_color="green")

    def run_strategy_thread():
        """전략 실행 스레드"""
        global stop_flag, running_flag
        try:
            # 초기 상태 표시
            app.after(0, lambda: initialize_order_cards(max_levels))

            # 전략 메타 업데이트
            update_strategy_info_batch({
                "market": market,
                "start_price": start_price,
                "realized_profit": 0.0
            })

            print(f"[DEBUG] 전략 실행 시작 - {market}, 시작가: {start_price}")

            run_auto_trade(
                start_price=start_price,
                krw_amount=krw_amount,
                max_levels=max_levels,
                market_code=market,
                buy_gap=buy_gap,
                buy_mode=buy_mode.get(),
                sell_gap=sell_gap,
                sell_mode=sell_mode.get(),
                stop_condition=stop_condition,
                sleep_sec=5,
                status_callback=update_order_status,
                summary_callback=update_strategy_summary,
                resume_level=resume_level,
            )

            if stop_flag:
                app.after(0, lambda: messagebox.showwarning("전략 중단", "사용자에 의해 전략이 중단되었습니다."))
                app.after(0, lambda: label_status.configure(text="🛑 전략 중단됨", text_color="red"))
            else:
                app.after(0, lambda: messagebox.showinfo("전략 완료", "전략이 성공적으로 완료되었습니다."))
                app.after(0, lambda: label_status.configure(text="✅ 전략 완료", text_color="gray"))
        except Exception as e:
            import traceback

            error_msg = f"전략 실행 중 오류 발생:\n{str(e)}"
            print(f"[ERROR] {error_msg}")
            print(f"[TRACEBACK] {traceback.format_exc()}")
            app.after(0, lambda: messagebox.showerror("오류", error_msg))
            app.after(0, lambda: label_status.configure(text="❌ 전략 오류", text_color="red"))
        finally:
            running_flag = False
            app.after(0, lambda: btn_start.configure(state="normal"))
            app.after(0, lambda: btn_stop.configure(state="disabled"))

    threading.Thread(target=run_strategy_thread, daemon=True).start()

def stop_strategy():
    """전략 중단"""
    global stop_flag
    
    if not running_flag:
        messagebox.showwarning("알림", "실행 중인 전략이 없습니다.")
        return

    if not messagebox.askokcancel("전략 중단 확인", "전략을 중단하고 모든 주문을 취소할까요?"):
        return
    
    stop_flag = True
    
    try:
        market = entry_market.get().strip().upper()
        full_market = f"KRW-{market}"
        
        # 모든 주문 취소
        cancel_all_orders(full_market)
        send_telegram_message(f"🛑 {market} 전략 중단 및 주문 전체 취소 완료")
        
        label_status.configure(text="🛑 전략 중단 중...", text_color="orange")
        current_level_label.configure(text="🛒 중단됨  |  📤 중단됨")
        status_text_label.configure(text="⛔ 전략이 중단되었습니다.", text_color="red")
            
    except Exception as e:
        error_msg = f"전략 중단 중 오류: {str(e)}"
        print(f"[ERROR] {error_msg}")
        send_telegram_message(f"⚠️ {error_msg}")
        messagebox.showerror("오류", error_msg)

# 정기적으로 상태 업데이트 처리
def periodic_update():
    """정기적인 업데이트 처리"""
    try:
        process_status_updates()
    except Exception as e:
        print(f"[ERROR] periodic_update: {e}")
    finally:
        app.after(100, periodic_update)  # 100ms마다 실행

# UI 디자인 상수
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUBTITLE = ("Segoe UI", 15, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_LABEL = ("Segoe UI", 12)
COLOR_BG = "#0F111A"      # Deep Navy/Black
COLOR_CARD = "#1A1D2B"    # Slate Card
COLOR_ACCENT = "#00D4AA"  # Mint
COLOR_TEXT = "#E0E0E0"
COLOR_MUTED = "#8E94A5"

# 앱 전체 테마 적용
app.configure(fg_color=COLOR_BG)

# UI 구성 - 스크롤 가능한 메인 프레임
main_scrollable = ctk.CTkScrollableFrame(
    app, 
    fg_color=COLOR_BG,
    corner_radius=0,
    border_width=0
)
main_scrollable.grid(row=0, column=0, sticky="nsew")
main_scrollable.grid_columnconfigure(0, weight=1)

# 앱 그리드 설정
app.grid_rowconfigure(0, weight=1)
app.grid_columnconfigure(0, weight=1)

def create_card(parent, title=None):
    card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#2A2F45")
    card.columnconfigure(0, weight=1)
    if title:
        ctk.CTkLabel(card, text=title, font=FONT_SUBTITLE, text_color=COLOR_ACCENT).pack(pady=(18, 12), padx=22, anchor="w")
    return card
        
### 1. 상단 티커 카드 (슬림 바 스타일)
ticker_card = ctk.CTkFrame(main_scrollable, fg_color="#141721", height=45, corner_radius=0)
ticker_card.pack(fill="x", pady=(0, 15))

ticker_inner = ctk.CTkFrame(ticker_card, fg_color="transparent")
ticker_inner.pack(pady=8, padx=25)

price_labels["time"] = ctk.CTkLabel(ticker_inner, text="⏱️ --:--:--", font=("Segoe UI", 12, "bold"), text_color=COLOR_ACCENT)
price_labels["time"].pack(side="left", padx=(0, 30))

for coin in ["BTC", "ETH", "USDT", "XRP"]:
    frame = ctk.CTkFrame(ticker_inner, fg_color="transparent")
    frame.pack(side="left", padx=15)
    price_labels[coin] = ctk.CTkLabel(frame, text=f"{coin}: -", font=("Segoe UI", 12))
    price_labels[coin].pack()

### 2. 수익 현황 섹션 (대시보드 카드 스타일)
stats_container = ctk.CTkFrame(main_scrollable, fg_color="transparent")
stats_container.pack(fill="x", padx=18, pady=10)
stats_container.columnconfigure((0, 1, 2), weight=1)

def create_stat_card(parent, col, title, key, color=COLOR_TEXT):
    card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#2A2F45")
    card.grid(row=0, column=col, padx=6, sticky="nsew")
    ctk.CTkLabel(card, text=title, font=FONT_LABEL, text_color=COLOR_MUTED).pack(pady=(15, 0))
    summary_labels[key] = ctk.CTkLabel(card, text="- KRW", font=("Segoe UI", 16, "bold"), text_color=color)
    summary_labels[key].pack(pady=(6, 18))
    return card

create_stat_card(stats_container, 0, "오늘 수익", "today_profit", COLOR_ACCENT)
create_stat_card(stats_container, 1, "이번 달 수익", "monthly_profit", "#5E8DFF")
create_stat_card(stats_container, 2, "총 누적 수익", "profit", "#F9CB40")


### 3. 입력 및 전략 설정 섹션
config_card = create_card(main_scrollable, "⚙️ 전략 설정")
config_card.pack(fill="x", padx=18, pady=10)

grid_config = ctk.CTkFrame(config_card, fg_color="transparent")
grid_config.pack(fill="x", padx=25, pady=(0, 20))
grid_config.columnconfigure((1, 3), weight=1)

# 설정 행 1: 코인 / 시작가
ctk.CTkLabel(grid_config, text="코인", font=FONT_LABEL).grid(row=0, column=0, sticky="w", pady=10)
entry_market = ctk.CTkEntry(grid_config, placeholder_text="BTC", height=38, border_color="#3A3F55", fg_color="#12141F")
entry_market.grid(row=0, column=1, padx=(12, 25), sticky="ew")

ctk.CTkLabel(grid_config, text="시작가", font=FONT_LABEL).grid(row=0, column=2, sticky="w", pady=10)
entry_price = ctk.CTkEntry(grid_config, placeholder_text="0", height=38, border_color="#3A3F55", fg_color="#12141F")
entry_price.grid(row=0, column=3, padx=12, sticky="ew")

# 설정 행 2: 매수금액 / 최대차수
ctk.CTkLabel(grid_config, text="매수금액", font=FONT_LABEL).grid(row=1, column=0, sticky="w", pady=10)
entry_amount = ctk.CTkEntry(grid_config, placeholder_text="5,000", height=38, border_color="#3A3F55", fg_color="#12141F")
entry_amount.grid(row=1, column=1, padx=(12, 25), sticky="ew")

ctk.CTkLabel(grid_config, text="최대차수", font=FONT_LABEL).grid(row=1, column=2, sticky="w", pady=10)
entry_rounds = ctk.CTkEntry(grid_config, placeholder_text="20", height=38, border_color="#3A3F55", fg_color="#12141F")
entry_rounds.grid(row=1, column=3, padx=12, sticky="ew")

# 설정 행 3: 재시작 차수 / 대상 정보
ctk.CTkLabel(grid_config, text="재시작 차수", font=FONT_LABEL).grid(row=2, column=0, sticky="w", pady=10)
entry_resume_level = ctk.CTkEntry(grid_config, placeholder_text="0=신규", height=38, border_color="#3A3F55", fg_color="#12141F")
entry_resume_level.insert(0, "0")
entry_resume_level.grid(row=2, column=1, padx=(12, 25), sticky="ew")

summary_labels["market"] = ctk.CTkLabel(grid_config, text="대상: -", font=FONT_LABEL, text_color=COLOR_MUTED)
summary_labels["market"].grid(row=2, column=2, columnspan=2, sticky="w")

# 재시작 차수 입력 시 가격 정보 업데이트 함수
def update_resume_price_info(*args):
    try:
        from strategy.auto_trade import calculate_price
        from config.tick_table import get_tick_size
        import math
        
        resume_level_val = entry_resume_level.get().strip()
        if not resume_level_val or resume_level_val == "0":
            summary_labels["market"].configure(text="대상: -", text_color=COLOR_MUTED)
            return
        
        resume_level = int(resume_level_val)
        start_price = float(entry_price.get())
        buy_gap = float(entry_buy_gap.get())
        sell_gap = float(entry_sell_gap.get())
        buy_mode_val = buy_mode.get()
        sell_mode_val = sell_mode.get()
        coin = entry_market.get().strip().upper()
        if not coin: return
        
        market = f"KRW-{coin}"
        tick = get_tick_size(market)
        
        # 재시작 차수의 매수/매도가 계산
        raw_buy_price = calculate_price(start_price, buy_gap * (resume_level - 1), buy_mode_val, 'down')
        raw_sell_price = calculate_price(raw_buy_price, sell_gap, sell_mode_val, 'up')
        buy_price = math.floor(raw_buy_price / tick) * tick
        sell_price = math.floor(raw_sell_price / tick) * tick
        
        # 이전 차수 매도가 계산 (resume_level - 1차)
        prev_sell_price = None
        if resume_level > 1:
            prev_raw_buy_price = calculate_price(start_price, buy_gap * (resume_level - 2), buy_mode_val, 'down')
            prev_raw_sell_price = calculate_price(prev_raw_buy_price, sell_gap, sell_mode_val, 'up')
            prev_sell_price = math.floor(prev_raw_sell_price / tick) * tick
        
        # 현재가 조회
        current_price = get_current_price(market)
        
        if current_price:
            # 즉시 체결 위험 판단
            if current_price <= buy_price:
                info = f"⚠️ 위험: {resume_level}차 매수({buy_price:,.0f}) 즉시체결!"
                summary_labels["market"].configure(text=info, text_color="#FF4B4B")
            elif prev_sell_price and current_price >= prev_sell_price:
                info = f"⚠️ 위험: {resume_level-1}차 매도({prev_sell_price:,.0f}) 즉시체결!"
                summary_labels["market"].configure(text=info, text_color="#FF4B4B")
            else:
                info = f"✅ {resume_level}차 매수: {buy_price:,.0f} | 현재가: {current_price:,.0f}"
                summary_labels["market"].configure(text=info, text_color=COLOR_ACCENT)
        else:
            summary_labels["market"].configure(text=f"📊 {resume_level}차 매수: {buy_price:,.0f}", text_color="yellow")
    
    except Exception:
        summary_labels["market"].configure(text="대상: -", text_color=COLOR_MUTED)


# 구분선
ctk.CTkFrame(config_card, fg_color="#2A2F45", height=1).pack(fill="x", padx=25, pady=5)

# 간격 설정 서브 섹션
gap_container = ctk.CTkFrame(config_card, fg_color="transparent")
gap_container.pack(fill="x", padx=25, pady=(15, 25))
gap_container.columnconfigure((1, 2), weight=1)

# 매수 간격
buy_mode = ctk.StringVar(value="percent")
ctk.CTkLabel(gap_container, text="매수 간격", font=FONT_LABEL).grid(row=0, column=0, sticky="w", pady=8)
entry_buy_gap = ctk.CTkEntry(gap_container, height=38, border_color="#3A3F55", fg_color="#12141F")
entry_buy_gap.insert(0, "0.2")
entry_buy_gap.grid(row=0, column=1, padx=12, sticky="ew")

buy_mode_frame = ctk.CTkFrame(gap_container, fg_color="transparent")
buy_mode_frame.grid(row=0, column=2, sticky="e")
ctk.CTkRadioButton(buy_mode_frame, text="%", variable=buy_mode, value="percent", font=FONT_LABEL, width=55, hover_color=COLOR_ACCENT).pack(side="left")
ctk.CTkRadioButton(buy_mode_frame, text="원", variable=buy_mode, value="price", font=FONT_LABEL, width=55, hover_color=COLOR_ACCENT).pack(side="left")

# 매도 간격
sell_mode = ctk.StringVar(value="percent")
ctk.CTkLabel(gap_container, text="매도 간격", font=FONT_LABEL).grid(row=1, column=0, sticky="w", pady=8)
entry_sell_gap = ctk.CTkEntry(gap_container, height=38, border_color="#3A3F55", fg_color="#12141F")
entry_sell_gap.insert(0, "0.3")
entry_sell_gap.grid(row=1, column=1, padx=12, sticky="ew")

sell_mode_frame = ctk.CTkFrame(gap_container, fg_color="transparent")
sell_mode_frame.grid(row=1, column=2, sticky="e")
ctk.CTkRadioButton(sell_mode_frame, text="%", variable=sell_mode, value="percent", font=FONT_LABEL, width=55, hover_color=COLOR_ACCENT).pack(side="left")
ctk.CTkRadioButton(sell_mode_frame, text="원", variable=sell_mode, value="price", font=FONT_LABEL, width=55, hover_color=COLOR_ACCENT).pack(side="left")


def open_dashboard():
    """수익 대시보드 웹페이지 열기"""
    try:
        from utils.dashboard import start_dashboard
        import webbrowser
        port = start_dashboard()
        webbrowser.open(f"http://localhost:{port}")
    except Exception as e:
        messagebox.showerror("오류", f"대시보드 실행 실패: {e}")

### 4. 제어 버튼 섹션
ctrl_frame = ctk.CTkFrame(main_scrollable, fg_color="transparent")
ctrl_frame.pack(fill="x", padx=18, pady=5)
ctrl_frame.columnconfigure((0, 1, 2), weight=1)

btn_start = ctk.CTkButton(ctrl_frame, text="🚀 전략 실행", command=start_strategy, 
                         fg_color="#28A745", hover_color="#218838", height=50, 
                         font=("Segoe UI", 15, "bold"), corner_radius=12)
btn_stop = ctk.CTkButton(ctrl_frame, text="🛑 전략 중단", command=stop_strategy, 
                        fg_color="#DC3545", hover_color="#C82333", state="disabled", height=50,
                        font=("Segoe UI", 15, "bold"), corner_radius=12)
btn_dashboard = ctk.CTkButton(ctrl_frame, text="📊 대시보드", command=open_dashboard,
                             fg_color="#6F42C1", hover_color="#5A32A3", height=50,
                             font=("Segoe UI", 15, "bold"), corner_radius=12)

btn_start.grid(row=0, column=0, padx=6, sticky="ew")
btn_stop.grid(row=0, column=1, padx=6, sticky="ew")
btn_dashboard.grid(row=0, column=2, padx=6, sticky="ew")

### 5. 실시간 상태 정보 카드
status_card = create_card(main_scrollable, "📡 실시간 상태")
status_card.pack(fill="x", padx=18, pady=10)

status_box = ctk.CTkFrame(status_card, fg_color="transparent")
status_box.pack(fill="x", padx=25, pady=(0, 25))

label_status = ctk.CTkLabel(status_box, text="⏸️ 대기 중", font=FONT_SUBTITLE, text_color=COLOR_MUTED)
label_status.pack(pady=6)

current_level_label = ctk.CTkLabel(status_box, text="🛒 매수 대기  |  📤 매도 대기", font=("Segoe UI", 14, "bold"))
current_level_label.pack(pady=6)

status_text_label = ctk.CTkLabel(status_box, text="⏳ 전략 실행을 기다리는 중...", font=FONT_BODY, text_color=COLOR_MUTED)
status_text_label.pack(pady=6)


### 6. 차수별 현황 테이블
table_card = create_card(main_scrollable, "📋 차수별 상세 현황")
table_card.pack(fill="x", padx=15, pady=10, expand=True)

# 테이블 헤더 프레임
table_header = ctk.CTkFrame(table_card, fg_color="#1E1E22", height=30, corner_radius=0)
table_header.pack(fill="x", padx=2, pady=(0, 1))
table_header.columnconfigure((0, 1, 2, 3), weight=1)

for col, header in enumerate(["차수", "매수가", "매도가", "상태"]):
    ctk.CTkLabel(table_header, text=header, font=("Pretendard", 11, "bold"), text_color=COLOR_MUTED).grid(row=0, column=col, sticky="ew")

# 테이블 스크롤 프레임
table_scroll = ctk.CTkScrollableFrame(table_card, height=300, fg_color="transparent", corner_radius=0)
table_scroll.pack(fill="both", expand=True, padx=2, pady=5)
table_scroll.columnconfigure((0, 1, 2, 3), weight=1)

grid_table_rows = {}  # {level: [label_level, label_buy, label_sell, label_status]}

def refresh_grid_table():
    """차수별 테이블 갱신 (전략 실행 중 주기적 호출)"""
    try:
        from shared.state import get_strategy_info
        info = get_strategy_info()
        market = info.get('market', '').replace("KRW-", "")
        if not market or market == '-':
            return
        
        # 상태 파일에서 levels 로드
        from utils.file_io import load_state
        state = load_state(f"KRW-{market}")
        if not state or 'levels' not in state:
            return
        
        levels_data = state['levels']
        
        for lv_data in levels_data:
            lvl = lv_data['level']
            buy_p = lv_data['buy_price']
            sell_p = lv_data['sell_price']
            
            # 상태 판별
            if lv_data.get('buy_filled') and not lv_data.get('sell_filled'):
                status = "🟢 보유중"
                color = COLOR_ACCENT
            elif lv_data.get('buy_uuid') and not lv_data.get('buy_filled'):
                status = "🟡 매수대기"
                color = "#FFC107"
            elif lv_data.get('sell_uuid') and not lv_data.get('sell_filled'):
                status = "🔵 매도대기"
                color = "#17A2B8"
            else:
                status = "⚪ 대기"
                color = COLOR_MUTED
            
            if lvl not in grid_table_rows:
                # 홀수/짝수 줄 배경색 차이 시도 (CTkLabel은 배경색 변경이 제한적이므로 테두리나 텍스트로 구분)
                row_frame = ctk.CTkFrame(table_scroll, fg_color="transparent", height=25)
                row_frame.grid(row=lvl, column=0, columnspan=4, sticky="ew", pady=1)
                row_frame.columnconfigure((0, 1, 2, 3), weight=1)
                
                labels = [
                    ctk.CTkLabel(row_frame, text=f"{lvl}차", font=("Pretendard", 11)),
                    ctk.CTkLabel(row_frame, text=f"{buy_p:,.0f}", font=("Pretendard", 11)),
                    ctk.CTkLabel(row_frame, text=f"{sell_p:,.0f}", font=("Pretendard", 11)),
                    ctk.CTkLabel(row_frame, text=status, font=("Pretendard", 11, "bold"), text_color=color),
                ]
                for c, label in enumerate(labels):
                    label.grid(row=0, column=c, sticky="ew")
                grid_table_rows[lvl] = labels
            else:
                grid_table_rows[lvl][3].configure(text=status, text_color=color)
    except Exception as e:
        pass

def periodic_table_refresh():
    refresh_grid_table()
    app.after(5000, periodic_table_refresh)  # 5초마다 갱신

# 정기 업데이트 시작
periodic_update()
periodic_table_refresh()

# 실시간 시세 정보 업데이트 시작
update_price_info()

# 재시작 차수 입력 필드에 이벤트 바인딩 (모든 위젯 생성 후)
entry_resume_level.bind("<KeyRelease>", update_resume_price_info)
entry_price.bind("<KeyRelease>", update_resume_price_info)
# 이벤트 바인딩
entry_market.bind("<KeyRelease>", update_resume_price_info)
entry_price.bind("<KeyRelease>", update_resume_price_info)
entry_buy_gap.bind("<KeyRelease>", update_resume_price_info)
entry_sell_gap.bind("<KeyRelease>", update_resume_price_info)
entry_resume_level.bind("<KeyRelease>", update_resume_price_info)


# 시스템 트레이 최소화
_tray_icon = None

def minimize_to_tray():
    """창을 시스템 트레이로 최소화"""
    global _tray_icon
    try:
        import pystray
        from PIL import Image
        
        app.withdraw()  # 창 숨기기
        
        # 트레이 아이콘 이미지 생성 (16x16 녹색 사각형)
        icon_image = Image.new('RGB', (64, 64), color=(0, 180, 120))
        
        def on_open(icon, item):
            icon.stop()
            app.after(0, app.deiconify)
        
        def on_quit(icon, item):
            icon.stop()
            app.after(0, app.destroy)
        
        menu = pystray.Menu(
            pystray.MenuItem("열기", on_open, default=True),
            pystray.MenuItem("종료", on_quit)
        )
        
        _tray_icon = pystray.Icon("bithumbSplit", icon_image, "BithumbSplit", menu)
        threading.Thread(target=_tray_icon.run, daemon=True).start()
    except ImportError:
        # pystray가 없으면 그냥 최소화
        app.iconify()
    except Exception as e:
        print(f"트레이 최소화 실패: {e}")
        app.iconify()

def on_close():
    """창 닫기 시 트레이로 최소화 (전략 실행 중일 때)"""
    if running_flag:
        minimize_to_tray()
    else:
        app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)

if __name__ == "__main__":
    app.mainloop()
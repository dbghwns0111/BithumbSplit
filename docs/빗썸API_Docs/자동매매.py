import tkinter as tk
from threading import Thread
from time import sleep
import requests
import os
import uuid
import time
import hmac
import hashlib
import base64
from datetime import datetime
from dotenv import load_dotenv

# .env에서 API 키 로드
load_dotenv()
API_KEY = os.getenv("BITHUMB_API_KEY")
API_SECRET = os.getenv("BITHUMB_API_SECRET")

# 로그 파일 생성
def write_error_log(message):
    os.makedirs("logs", exist_ok=True)
    with open("logs/trade_errors.log", "a", encoding="utf-8") as f:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{now}] {message}\n")

# 빗썸 API 서명
def get_signature(api_key, api_secret, endpoint, body):
    nonce = str(uuid.uuid4())
    str_data = endpoint + chr(0) + body + chr(0) + nonce
    utf8_str = str_data.encode('utf-8')
    key = base64.b64decode(api_secret)
    signature = base64.b64encode(hmac.new(key, utf8_str, hashlib.sha512).digest()).decode()
    headers = {
        'Api-Key': api_key,
        'Api-Sign': signature,
        'Api-Nonce': nonce,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    return headers

# 빗썸 API 함수들
def get_btc_price():
    try:
        res = requests.get("https://api.bithumb.com/public/ticker/BTC_KRW")
        return float(res.json()['data']['closing_price'])
    except:
        return None

def buy_market_order(units):
    url_path = "/trade/market_buy"
    url = "https://api.bithumb.com" + url_path
    body = f"order_currency=BTC&payment_currency=KRW&units={units}"
    headers = get_signature(API_KEY, API_SECRET, url_path, body)
    res = requests.post(url, data=body, headers=headers)
    return res.json()

def sell_market_order(units):
    url_path = "/trade/market_sell"
    url = "https://api.bithumb.com" + url_path
    body = f"order_currency=BTC&payment_currency=KRW&units={units}"
    headers = get_signature(API_KEY, API_SECRET, url_path, body)
    res = requests.post(url, data=body, headers=headers)
    return res.json()

def get_balance():
    url_path = "/info/balance"
    url = "https://api.bithumb.com" + url_path
    body = "currency=BTC"
    headers = get_signature(API_KEY, API_SECRET, url_path, body)
    res = requests.post(url, data=body, headers=headers)
    return res.json()

# 자동매매 클래스
class AutoTrader:
    def __init__(self, start_price, buy_step, sell_trigger, buy_amounts):
        self.start_price = start_price
        self.buy_step = buy_step
        self.sell_trigger = sell_trigger
        self.buy_amounts = buy_amounts
        self.reset()
        

    def reset(self):
        self.levels = [self.start_price * (1 - self.buy_step/100 * i) for i in range(len(self.buy_amounts))]
        self.total_krw = 0
        self.total_btc = 0
        self.avg_price = 0
        self.bought_steps = 0

    def check_trade(self):
        price = get_btc_price()
        if price is None:
            return "⚠️ 시세조회 실패\n"

        result = f"📈 현재가: {price:,.0f}원\n"

        # 매수
        if self.bought_steps < len(self.levels) and price <= self.levels[self.bought_steps]:
            amt = self.buy_amounts[self.bought_steps]
            btc = round(amt / price, 8)  # 소수 8자리
            res = buy_market_order(btc)
            if res.get('status') == '0000':
                self.total_krw += amt
                self.total_btc += btc
                self.avg_price = self.total_krw / self.total_btc
                result += f"🟢 매수 {self.bought_steps+1}회차: {btc} BTC @ {price:,.0f}원\n"
                self.bought_steps += 1
            else:
                error_msg = f"매수 실패: {res.get('message')}"
                write_error_log(error_msg)
                result += f"❌ {error_msg}\n"

        # 익절 매도
        elif self.total_btc > 0 and price >= self.avg_price * (1 + self.sell_trigger / 100):
            res = sell_market_order(round(self.total_btc, 8))
            if res.get('status') == '0000':
                result += f"🔴 익절 매도: 전체 {self.total_btc:.8f} BTC @ {price:,.0f}원\n"
                self.reset()
            else:
                error_msg = f"매도 실패: {res.get('message')}"
                write_error_log(error_msg)
                result += f"❌ {error_msg}\n"

        return result

# GUI 어플
class TraderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("비트코인 자동매매")
        self.trader = None
        self.running = False

        self.label = tk.Label(root, text="자동매매 상태", font=("맑은 고딕", 14))
        self.label.pack(pady=10)

        self.text = tk.Text(root, height=20, width=60)
        self.text.pack()

        self.start_btn = tk.Button(root, text="시작", command=self.start)
        self.start_btn.pack(pady=5)

        self.stop_btn = tk.Button(root, text="정지", command=self.stop)
        self.stop_btn.pack()

        # 사용자 입력창 추가
        tk.Label(root, text="시작가 (원)").pack()
        self.entry_price = tk.Entry(root)
        self.entry_price.insert(0, "140000000")
        self.entry_price.pack()

        tk.Label(root, text="하락 매수 퍼센트 (%)").pack()
        self.entry_step = tk.Entry(root)
        self.entry_step.insert(0, "3")
        self.entry_step.pack()

        tk.Label(root, text="상승 매도 퍼센트 (%)").pack()
        self.entry_trigger = tk.Entry(root)
        self.entry_trigger.insert(0, "5")
        self.entry_trigger.pack()

        tk.Label(root, text="회차별 매수 금액 (원)").pack()
        self.entry_amount = tk.Entry(root)
        self.entry_amount.insert(0, "10000")
        self.entry_amount.pack()

        tk.Label(root, text="최대 매수 차수 (횟수)").pack()
        self.entry_max_steps = tk.Entry(root)
        self.entry_max_steps.insert(0, "3")
        self.entry_max_steps.pack()

    def start(self):
        try:
            start_price = int(self.entry_price.get())
            buy_step = float(self.entry_step.get())
            sell_trigger = float(self.entry_trigger.get())
            buy_amount = int(self.entry_amount.get())
            max_steps = int(self.entry_max_steps.get())
            buy_amounts = [buy_amount] * max_steps  # 동일 금액으로 리스트 생성

            self.trader = AutoTrader(
                start_price=start_price,
                buy_step=buy_step,
                sell_trigger=sell_trigger,
                buy_amounts=buy_amounts
            )
            self.running = True
            Thread(target=self.run, daemon=True).start()
            self.text.insert(tk.END, "▶️ 자동매매 시작\n")
        except Exception as e:
            self.text.insert(tk.END, f"❌ 입력값 오류: {e}\n")


    def stop(self):
        self.running = False
        self.text.insert(tk.END, "⛔ 자동매매 정지됨\n")

    def run(self):
        while self.running:
            result = self.trader.check_trade()
            self.text.insert(tk.END, result + "\n")
            self.text.see(tk.END)
            sleep(5)


# 실행
if __name__ == "__main__":
    #root = tk.Tk()
    #app = TraderApp(root)
    #root.mainloop()
    result = get_balance()
    print("잔고조회 결과:")
    print(result)

# utils/dashboard.py
# 수익 대시보드 (Flask 웹 서버)

import os
import sys
import csv
import threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from flask import Flask, render_template_string

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BithumbSplit Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI',sans-serif; background:#0f0f23; color:#e0e0e0; padding:20px; }
  h1 { text-align:center; color:#00d4aa; margin-bottom:8px; font-size:1.8em; }
  .subtitle { text-align:center; color:#888; margin-bottom:24px; font-size:0.9em; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:24px; }
  .card { background:#1a1a3e; border-radius:12px; padding:20px; text-align:center; border:1px solid #2a2a5e; }
  .card .label { color:#888; font-size:0.85em; margin-bottom:4px; }
  .card .value { font-size:1.6em; font-weight:bold; }
  .card .positive { color:#00d4aa; }
  .card .negative { color:#ff4d6a; }
  .chart-container { background:#1a1a3e; border-radius:12px; padding:20px; margin-bottom:20px; border:1px solid #2a2a5e; }
  .chart-title { font-size:1.1em; font-weight:bold; margin-bottom:12px; color:#ccc; }
  table { width:100%; border-collapse:collapse; }
  th,td { padding:8px 12px; text-align:right; border-bottom:1px solid #2a2a5e; font-size:0.9em; }
  th { color:#888; font-weight:normal; }
  td:first-child, th:first-child { text-align:left; }
</style>
</head>
<body>
<h1>📈 BithumbSplit Dashboard</h1>
<p class="subtitle">마지막 갱신: {{ last_updated }}</p>

<div class="cards">
  <div class="card">
    <div class="label">오늘 수익</div>
    <div class="value {{ 'positive' if today_profit >= 0 else 'negative' }}">{{ "{:,.0f}".format(today_profit) }}원</div>
  </div>
  <div class="card">
    <div class="label">이번 달 수익</div>
    <div class="value {{ 'positive' if monthly_profit >= 0 else 'negative' }}">{{ "{:,.0f}".format(monthly_profit) }}원</div>
  </div>
  <div class="card">
    <div class="label">총 누적 수익</div>
    <div class="value {{ 'positive' if total_profit >= 0 else 'negative' }}">{{ "{:,.0f}".format(total_profit) }}원</div>
  </div>
  <div class="card">
    <div class="label">총 체결 건수</div>
    <div class="value" style="color:#7b9fff;">{{ total_trades }}건</div>
  </div>
</div>

<div class="chart-container">
  <div class="chart-title">📅 일별 수익 (최근 30일)</div>
  <canvas id="dailyChart" height="80"></canvas>
</div>

<div class="chart-container">
  <div class="chart-title">🗓️ 월별 수익</div>
  <canvas id="monthlyChart" height="60"></canvas>
</div>

<div class="chart-container">
  <div class="chart-title">📋 최근 거래 내역</div>
  <table>
    <tr><th>시간</th><th>차수</th><th>매수가</th><th>매도가</th><th>수익</th></tr>
    {% for t in recent_trades %}
    <tr>
      <td>{{ t.timestamp }}</td><td>{{ t.level }}차</td>
      <td>{{ "{:,.0f}".format(t.buy_price) }}원</td>
      <td>{{ "{:,.0f}".format(t.sell_price) }}원</td>
      <td style="color:{{ '#00d4aa' if t.profit >= 0 else '#ff4d6a' }}">{{ "{:,.0f}".format(t.profit) }}원</td>
    </tr>
    {% endfor %}
  </table>
</div>

<script>
const dailyLabels = {{ daily_labels | tojson }};
const dailyData = {{ daily_data | tojson }};
const monthlyLabels = {{ monthly_labels | tojson }};
const monthlyData = {{ monthly_data | tojson }};

const barColors = (data) => data.map(v => v >= 0 ? 'rgba(0,212,170,0.7)' : 'rgba(255,77,106,0.7)');

new Chart(document.getElementById('dailyChart'), {
  type:'bar', data:{labels:dailyLabels, datasets:[{data:dailyData, backgroundColor:barColors(dailyData), borderRadius:4}]},
  options:{plugins:{legend:{display:false}}, scales:{x:{ticks:{color:'#888'}}, y:{ticks:{color:'#888',callback:v=>v.toLocaleString()+'원'}, grid:{color:'#2a2a5e'}}}}
});
new Chart(document.getElementById('monthlyChart'), {
  type:'bar', data:{labels:monthlyLabels, datasets:[{data:monthlyData, backgroundColor:barColors(monthlyData), borderRadius:4}]},
  options:{plugins:{legend:{display:false}}, scales:{x:{ticks:{color:'#888'}}, y:{ticks:{color:'#888',callback:v=>v.toLocaleString()+'원'}, grid:{color:'#2a2a5e'}}}}
});
</script>
</body></html>
"""

class Trade:
    def __init__(self, row):
        self.timestamp = row.get('timestamp', '')
        self.level = int(row.get('level', 0))
        self.buy_price = float(row.get('buy_price', 0))
        self.sell_price = float(row.get('sell_price', 0))
        self.profit = float(row.get('profit', 0))

def load_all_trades():
    trades = []
    log_dir = os.path.join(BASE_DIR, 'logs')
    if not os.path.exists(log_dir):
        return trades
    for f in os.listdir(log_dir):
        if f.startswith('trade_log_') and f.endswith('.csv'):
            path = os.path.join(log_dir, f)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    for row in csv.DictReader(fh):
                        trades.append(Trade(row))
            except Exception:
                pass
    trades.sort(key=lambda t: t.timestamp, reverse=True)
    return trades

@app.route('/')
def index():
    trades = load_all_trades()
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    month_str = now.strftime('%Y-%m')
    
    today_profit = sum(t.profit for t in trades if t.timestamp.startswith(today_str))
    monthly_profit = sum(t.profit for t in trades if t.timestamp.startswith(month_str))
    total_profit = sum(t.profit for t in trades)
    
    # 일별 집계 (최근 30일)
    daily = defaultdict(float)
    for t in trades:
        day = t.timestamp[:10]
        daily[day] += t.profit
    
    date_range = [(now - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(29, -1, -1)]
    daily_labels = [d[5:] for d in date_range]  # MM-DD
    daily_data = [round(daily.get(d, 0), 0) for d in date_range]
    
    # 월별 집계
    monthly = defaultdict(float)
    for t in trades:
        m = t.timestamp[:7]
        monthly[m] += t.profit
    monthly_sorted = sorted(monthly.items())
    monthly_labels = [m[0] for m in monthly_sorted] or [month_str]
    monthly_data = [round(m[1], 0) for m in monthly_sorted] or [0]
    
    return render_template_string(
        DASHBOARD_HTML,
        last_updated=now.strftime('%Y-%m-%d %H:%M:%S'),
        today_profit=today_profit, monthly_profit=monthly_profit,
        total_profit=total_profit, total_trades=len(trades),
        daily_labels=daily_labels, daily_data=daily_data,
        monthly_labels=monthly_labels, monthly_data=monthly_data,
        recent_trades=trades[:20]
    )

_server_thread = None

def start_dashboard(port=5000):
    """대시보드를 백그라운드 스레드로 시작"""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return port
    
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    
    def run():
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()
    return port

if __name__ == '__main__':
    print("📊 대시보드 실행 중: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)

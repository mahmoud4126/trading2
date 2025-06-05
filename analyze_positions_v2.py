import time
import streamlit as st
import pandas as pd
import MetaTrader5 as mt5
import plotly.graph_objects as go
from datetime import datetime, date
import pytz
import requests

# ✅ إعداد الاتصال بمنصة MetaTrader
if not mt5.initialize():
    st.error("فشل الاتصال بـ MetaTrader 5")
    st.stop()

st.set_page_config(page_title="تحليل الصفقات المفتوحة", layout="wide")
st.title("📊 تحليل ذكي للصفقات المفتوحة")

WEBHOOK_URL = "https://discord.com/api/webhooks/1380020424016138280/ANHPxVzCqKSVgtS3P6JhsGjblHdo_KPqyg5fULBLbS7NtjUUBpLEm5EDWZSvCyi6s1c2"  # ضع رابط Webhook الصحيح
previous_positions = {}
previous_analysis = {}
previous_balance = None
previous_equity = None
initial_daily_balance = None
last_recorded_day = None
previous_tickets = set()

# إرسال رسالة إلى Discord مع فاصل ومسافة بسيطة
def send_discord(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted = f"\n\n🔔 إشعار جديد 🔔\n🕒 {timestamp}\n{message}"
    payload = {"content": formatted}
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code != 204:
            print("⚠️ فشل إرسال الرسالة إلى Discord:", response.status_code)
    except Exception as e:
        print("فشل الإرسال إلى Discord:", e)

# تحليل الصفقات المفتوحة
def analyze_live_positions():
    global previous_positions, previous_analysis, previous_balance, previous_equity, initial_daily_balance, last_recorded_day, previous_tickets

    open_positions = mt5.positions_get()
    if open_positions is None:
        return

    current_positions = {}
    current_tickets = set()
    message_changed = ""

    for pos in open_positions:
        ticket = pos.ticket
        symbol = pos.symbol
        entry_price = pos.price_open
        volume = pos.volume
        direction = "Buy" if pos.type == 0 else "Sell"

        current_positions[ticket] = pos
        current_tickets.add(ticket)

        if ticket not in previous_positions:
            msg = f"📥 صفقة جديدة: {symbol} | {direction} @ {entry_price:.2f} | كمية: {volume:.2f}"

            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
            if rates is not None and len(rates) > 50:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df['EMA20'] = df['close'].ewm(span=20).mean()
                df['EMA50'] = df['close'].ewm(span=50).mean()
                latest = df.iloc[-1]

                if direction == 'Buy' and latest['EMA20'] > latest['EMA50']:
                    status = "✅ دخول صحيح (ترند صاعد)"
                elif direction == 'Sell' and latest['EMA20'] < latest['EMA50']:
                    status = "✅ دخول صحيح (ترند هابط)"
                else:
                    status = "❌ دخول خاطئ (عكس الاتجاه)"

                msg += f"\n📊 التحليل: {status}"
                previous_analysis[ticket] = status

            send_discord(msg)

        elif ticket in previous_analysis:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
            if rates is not None and len(rates) > 50:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df['EMA20'] = df['close'].ewm(span=20).mean()
                df['EMA50'] = df['close'].ewm(span=50).mean()
                latest = df.iloc[-1]

                if direction == 'Buy' and latest['EMA20'] > latest['EMA50']:
                    status = "✅ دخول صحيح (ترند صاعد)"
                elif direction == 'Sell' and latest['EMA20'] < latest['EMA50']:
                    status = "✅ دخول صحيح (ترند هابط)"
                else:
                    status = "❌ دخول خاطئ (عكس الاتجاه)"

                if previous_analysis[ticket] != status:
                    message_changed += f"🔄 تغير التحليل: {symbol} | {direction} | {status}\n"
                    previous_analysis[ticket] = status

    # 🔔 تحقق من الصفقات المغلقة
    closed_tickets = previous_tickets - current_tickets
    if closed_tickets:
        closed_msg = "🔴 صفقات مغلقة:\n"
        for t in closed_tickets:
            closed_msg += f"📤 تم غلق الصفقة رقم {t}\n"
        send_discord(closed_msg)

    previous_positions = current_positions
    previous_tickets = current_tickets

    # 🔔 إشعار عند تغير الرصيد أو Equity
    account_info = mt5.account_info()
    if account_info:
        current_balance = account_info.balance
        current_equity = account_info.equity

        today = datetime.now().date()
        if initial_daily_balance is None or today != last_recorded_day:
            initial_daily_balance = current_balance
            last_recorded_day = today

        if previous_balance is not None and current_balance != previous_balance:
            diff = current_balance - previous_balance
            daily_diff = current_balance - initial_daily_balance
            change = "📈 زيادة" if diff > 0 else "📉 نقصان"
            daily_status = "⬆️ ربح" if daily_diff > 0 else "⬇️ خسارة"
            msg = (
                f"💰 تغير في الرصيد: {change}\n"
                f"🔢 الرصيد السابق: {previous_balance:.2f}\n"
                f"🔢 الرصيد الحالي: {current_balance:.2f}\n"
                f"🔁 الفرق اللحظي: {diff:.2f}\n"
                f"📆 إجمالي اليوم {today}: {daily_status} {daily_diff:.2f} 💵"
            )
            send_discord(msg)

        # إشعار إذا تغير Equity بشكل كبير
        if previous_equity is not None:
            equity_diff = current_equity - previous_equity
            if abs(equity_diff) >= 100:
                eq_msg = (
                    f"⚠️ تغير كبير في Equity\n"
                    f"🔢 Equity السابق: {previous_equity:.2f}\n"
                    f"🔢 Equity الحالي: {current_equity:.2f}\n"
                    f"📉 الفرق: {equity_diff:.2f} 💵"
                )
                send_discord(eq_msg)

        previous_balance = current_balance
        previous_equity = current_equity

    if message_changed:
        send_discord(message_changed)

while True:
    analyze_live_positions()
    time.sleep(5)

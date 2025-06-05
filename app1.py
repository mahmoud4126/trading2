import streamlit as st
import pandas as pd
import MetaTrader5 as mt5
import openai
import os
from dotenv import load_dotenv

# تحميل مفاتيح البيئة
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.set_page_config(page_title="تحليل فني ذكي", layout="wide")
st.title("📊 لوحة التحليل الفني باستخدام GPT + SMC")

# الاتصال بـ MetaTrader 5
if not mt5.initialize():
    st.error("❌ فشل الاتصال بمنصة MetaTrader 5")
    st.stop()

# 🔽 دالة لحساب المؤشرات الفنية
@st.cache_data
def fetch_data(symbol, timeframe=mt5.TIMEFRAME_M15, bars=200):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['rsi'] = compute_rsi(df['close'])
    return df

# 🔽 دالة لحساب RSI

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 🔽 دالة التحقق من قرب الدعم والمقاومة

def is_near_support_resistance(data, entry_price, threshold=5):
    recent_lows = data['low'].rolling(window=20).min()
    recent_highs = data['high'].rolling(window=20).max()
    last_support = recent_lows.iloc[-1]
    last_resistance = recent_highs.iloc[-1]

    if isinstance(entry_price, pd.Series):
        entry_price = entry_price.iloc[-1]

    is_near = abs(entry_price - last_support) <= threshold or abs(entry_price - last_resistance) <= threshold
    return is_near, round(float(last_support), 2), round(float(last_resistance), 2)

# 🔽 دالة التحقق من وجود كسر هيكل (Break of Structure)
def detect_structure_break(data):
    recent_highs = data['high'].rolling(window=5).max()
    recent_lows = data['low'].rolling(window=5).min()
    last_high = recent_highs.iloc[-1]
    last_low = recent_lows.iloc[-1]
    current_close = data['close'].iloc[-1]
    return current_close > last_high or current_close < last_low

# 🔽 دالة تقدير SL/TP أكثر دقة

def estimate_targets(data, trend_direction):
    recent_lows = data['low'].rolling(window=10).min()
    recent_highs = data['high'].rolling(window=10).max()
    close = data['close'].iloc[-1]

    if trend_direction == "صاعد 🔼":
        entry = close + 1.5
        sl = recent_lows.iloc[-1] - 2
        tp = entry + (entry - sl) * 1.5
    else:
        entry = close - 1.5
        sl = recent_highs.iloc[-1] + 2
        tp = entry - (sl - entry) * 1.5

    return round(entry, 2), round(sl, 2), round(tp, 2)

# 🔽 دالة تنسيق النتيجة

def format_analysis(trend, rsi_comment, entry, sl, tp, support, resistance):
    entry = float(entry)
    sl = float(sl)
    tp = float(tp)
    support = float(support)
    resistance = float(resistance)
    return f"""
### 🧠 تحليل SMC المختصر:

🔹 **الاتجاه العام:** {trend}  
📊 **مؤشر RSI:** {rsi_comment}  
🛑 **الدعم:** `{support:.2f}` — 📈 **المقاومة:** `{resistance:.2f}`  

🟢 **صفقة محتملة:**  
✅ دخول: `{entry:.2f}`  
❌ وقف خسارة (SL): `{sl:.2f}`  
🎯 الهدف (TP): `{tp:.2f}`
"""

# 🔽 تحليل مباشر
symbol = st.text_input("🔍 أدخل رمز الزوج (مثال: XAUUSD أو EURUSD)", "XAUUSD")

if symbol:
    df = fetch_data(symbol)
    latest = df.iloc[-1]

    trend = "صاعد 🔼" if latest['ema20'] > latest['ema50'] else "هابط 🔽"
    rsi = latest['rsi']
    rsi_comment = (
        "تشبع شرائي 🟠" if rsi > 70 else
        "تشبع بيعي 🔵" if rsi < 30 else
        "ضمن النطاق الطبيعي 🟢"
    )

    entry, sl, tp = estimate_targets(df, trend)
    near_support_resistance, support, resistance = is_near_support_resistance(df, entry)
    structure_break = detect_structure_break(df)

    st.markdown(format_analysis(trend, rsi_comment, entry, sl, tp, support, resistance))

    # إرسال إلى GPT لعرض تقييم فني دقيق
    proximity = "✅ السعر قريب من دعم/مقاومة" if near_support_resistance else "❌ السعر بعيد عن مستويات هامة"
    structure_note = "✅ توجد سيولة أو كسر هيكل" if structure_break else "❌ لا توجد بيانات كافية"

    prompt = f"""
أجب فقط بهذه الصيغة، دون شرح إضافي:
- ✅ الاتجاه يدعم الصفقة / ❌ الاتجاه لا يدعم الصفقة
- ✅ RSI يؤكد الاتجاه / ❌ RSI يعارض الاتجاه
- {proximity}
- {structure_note}
- 📌 التوصية النهائية: شراء / بيع / تجنب

المعطيات:
الاتجاه: {trend}
RSI: {rsi_comment}
دخول من: {entry}, SL: {sl}, TP: {tp}
الدعم: {support}, المقاومة: {resistance}
"""

    if st.button("📩 تحليل GPT"):
        with st.spinner("جاري التحليل عبر GPT ..."):
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "أنت خبير تداول محترف. التزم فقط بنقاط واضحة ✅ أو ❌ لكل عنصر، دون شرح مطول أو توقعات."},
                    {"role": "user", "content": prompt}
                ]
            )
            gpt_reply = response.choices[0].message.content
            st.success("✅ تحليل GPT")
            st.markdown(gpt_reply)

# historical_dashboard.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def show_csv_analysis():
    uploaded_file = st.file_uploader("⬆️ ارفع ملف الصفقات بصيغة CSV", type="csv")
    if uploaded_file is None:
        return

    try:
        df = pd.read_csv(uploaded_file, sep=None, engine='python')
    except pd.errors.EmptyDataError:
        st.error("⚠️ الملف فارغ أو لا يحتوي على بيانات صالحة.")
        return

    expected_cols = ["Profit", "Time", "Symbol"]
    if not all(col in df.columns for col in expected_cols):
        st.error("❌ الملف لا يحتوي على الأعمدة المطلوبة: Profit و Time و Symbol.")
        st.write(f"الأعمدة الموجودة: {df.columns.tolist()}")
        return

    df["Profit"] = df["Profit"].astype(str).str.replace("−", "-", regex=False)
    df["Profit"] = df["Profit"].str.replace(",", "", regex=False)
    df["Profit"] = df["Profit"].str.replace(r"[^\d\.-]", "", regex=True)
    df["Profit"] = pd.to_numeric(df["Profit"], errors="coerce")
    df.loc[df["Profit"].abs() > 1_000_000, "Profit"] = None

    df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
    df = df.dropna(subset=["Profit", "Time", "Symbol"])
    df["Hour"] = df["Time"].dt.hour
    df["Day"] = df["Time"].dt.day_name()
    df["Date"] = df["Time"].dt.date
    df["Month"] = df["Time"].dt.month
    df["Year"] = df["Time"].dt.year
    df["Symbol"] = df["Symbol"].astype(str)

    st.subheader("🔍 إحصائيات عامة")
    total_trades = len(df)
    avg_duration = df.groupby("Symbol")["Time"].apply(lambda x: (x.max() - x.min()) / len(x)).mean()
    top_pair = df["Symbol"].value_counts().idxmax()
    top_pair_trades = df["Symbol"].value_counts().max()

    st.markdown(f"**📈 إجمالي عدد الصفقات:** {total_trades}")
    st.markdown(f"**⏳ متوسط مدة الصفقة لكل زوج:** {avg_duration.round('1min')}")
    st.markdown(f"**💹 الزوج الأكثر تداولاً:** `{top_pair}` بعدد {top_pair_trades} صفقة")

    volume_per_symbol = df.groupby("Symbol")["Profit"].count().sort_values(ascending=False)
    st.subheader("📊 عدد الصفقات حسب الأزواج")
    fig_volume = px.bar(volume_per_symbol, x=volume_per_symbol.index, y=volume_per_symbol.values,
                        labels={"x": "زوج العملة", "y": "عدد الصفقات"},
                        title="📊 عدد الصفقات لكل زوج")
    st.plotly_chart(fig_volume, use_container_width=True)

    st.subheader("📈 تطور Balance و Equity")
    df_sorted = df.sort_values("Time")
    df_sorted["Balance"] = df_sorted["Profit"].cumsum()
    df_sorted["Equity"] = df_sorted["Balance"] + df_sorted["Profit"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_sorted["Time"], y=df_sorted["Balance"], mode='lines', name='Balance'))
    fig.add_trace(go.Scatter(x=df_sorted["Time"], y=df_sorted["Equity"], mode='lines', name='Equity'))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("""<h4 style='color:#FF4B4B;font-size:26px;'>🎯 اختر زوج التداول للتحليل</h4>""", unsafe_allow_html=True)
    available_symbols = df["Symbol"].unique().tolist()
    selected_symbol = st.radio("", options=available_symbols, horizontal=True)
    df = df[df["Symbol"] == selected_symbol]

    df["النتيجة"] = df["Profit"].apply(lambda x: "رابحة ✅" if x > 0 else ("خاسرة ❌" if x < 0 else "متعادلة"))
    نتائج = df["النتيجة"].value_counts().rename_axis("نوع الصفقة").reset_index(name="عدد الصفقات")
    st.subheader("📊 عدد الصفقات حسب النتيجة")
    st.dataframe(نتائج)

    st.subheader("🕐 إجمالي الأرباح لكل ساعة")
    sum_hour = df.groupby("Hour")["Profit"].sum().reset_index()
    st.bar_chart(sum_hour.set_index("Hour"))

    st.subheader("📅 إجمالي الأرباح لكل يوم من الأسبوع")
    sum_day = df.groupby("Day")["Profit"].sum().reindex([
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ])
    st.bar_chart(sum_day)

    st.subheader("📦 تحليل الأيام بشكل إحصائي")
    col1, col2, col3, col4 = st.columns(4)
    for i, (day, total) in enumerate(sum_day.items()):
        with [col1, col2, col3, col4][i % 4]:
            st.metric(label=day, value=f"{total:.2f} 💰")

    st.subheader("⛔ أكثر أوقات الخسارة")
    خسائر = df[df["Profit"] < 0]
    خسائر["ساعة"] = خسائر["Time"].dt.hour
    loss_by_hour = خسائر.groupby("ساعة")["Profit"].sum()
    st.bar_chart(loss_by_hour)

    worst_hour = loss_by_hour.idxmin()
    worst_amount = loss_by_hour.min()
    st.markdown(f"**❗أسوأ ساعة تداول:** الساعة {worst_hour}:00 بخسارة قدرها {worst_amount:.2f} 💸")

    st.subheader("✅ أكثر أوقات الربح")
    ارباح = df[df["Profit"] > 0]
    ارباح["ساعة"] = ارباح["Time"].dt.hour
    profit_by_hour = ارباح.groupby("ساعة")["Profit"].sum()
    st.bar_chart(profit_by_hour)

    best_hour = profit_by_hour.idxmax()
    best_amount = profit_by_hour.max()
    st.markdown(f"**🏆 أفضل ساعة تداول:** الساعة {best_hour}:00 بربح قدره {best_amount:.2f} 💰")

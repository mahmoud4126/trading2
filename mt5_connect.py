
# mt5_connect.py

import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

load_dotenv()  # تحميل المتغيرات من .env

login = int(os.getenv("MT5_LOGIN"))
password = os.getenv("MT5_PASSWORD")
server = os.getenv("MT5_SERVER")

def connect_mt5():
    if not mt5.initialize():
        print("❌ فشل الاتصال بـ MetaTrader 5")
        return False

    if not mt5.login(login, password=password, server=server):
        print("❌ فشل تسجيل الدخول - تحقق من البيانات")
        return False

    print("✅ تم الاتصال بنجاح بـ MT5")
    return True

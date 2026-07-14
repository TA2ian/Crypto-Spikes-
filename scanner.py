"""
ماسح العملات الحلال - سكربت مجاني بالكامل
يسحب بيانات KuCoin العامة (بدون مفتاح API)، يفحص شروط دخول كلاسيكية،
ويرسل تنبيهات عبر بوت تيليغرام.

يعمل عبر GitHub Actions كل ساعة (مجاني).
"""
import os
import sys
import time
import requests
import pandas as pd

from coins import WATCHLIST
from indicators import calc_rsi, find_support_resistance, avg_volume

# ============ الإعدادات ============
KUCOIN_KLINE_URL = "https://api.kucoin.com/api/v1/market/candles"
TIMEFRAME = "1hour"          # الإطار الزمني: يمكن تغييره إلى 4hour أو 1day
CANDLE_LIMIT = 60            # عدد الشموع المطلوبة للتحليل

RESISTANCE_LOOKBACK = 20     # فترة حساب المقاومة
SUPPORT_LOOKBACK = 20        # فترة حساب الدعم
VOLUME_MULTIPLIER = 1.618      # شرط الحجم لاختراق المقاومة
BOUNCE_MIN_VOLUME_RATIO = 0.8  # حد أدنى لنسبة الحجم عند الارتداد من دعم (دون هذا = ارتداد ضعيف يُستبعد)
RSI_OVERSOLD = 35            # حد التشبع البيعي لإشارة الارتداد
SUPPORT_TOLERANCE = 0.005    # 0.5% نسبة قرب السعر من الدعم

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def fetch_klines(symbol: str, timeframe: str = TIMEFRAME) -> pd.DataFrame | None:
    """جلب بيانات الشموع من KuCoin (عام، بدون مفتاح API)"""
    params = {"symbol": symbol, "type": timeframe}
    try:
        resp = requests.get(KUCOIN_KLINE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[خطأ] فشل جلب بيانات {symbol}: {e}")
        return None

    if data.get("code") != "200000" or not data.get("data"):
        print(f"[تحذير] لا بيانات لـ {symbol}: {data.get('msg', 'غير معروف')}")
        return None

    # ترتيب KuCoin: [time, open, close, high, low, volume, turnover] - الأحدث أولاً
    rows = data["data"][::-1]  # نعكس الترتيب ليصبح الأقدم أولاً
    df = pd.DataFrame(
        rows,
        columns=["time", "open", "close", "high", "low", "volume", "turnover"],
    )

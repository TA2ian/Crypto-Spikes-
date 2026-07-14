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
VOLUME_MULTIPLIER = 1.5      # شرط الحجم لاختراق المقاومة
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
    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = df[col].astype(float)

    return df.tail(CANDLE_LIMIT).reset_index(drop=True)


def analyze_symbol(symbol: str, df: pd.DataFrame) -> list[dict]:
    """فحص شروط الدخول الكلاسيكية على عملة واحدة، يعيد قائمة إشارات إن وجدت"""
    signals = []

    if len(df) < max(RESISTANCE_LOOKBACK, SUPPORT_LOOKBACK) + 5:
        return signals

    close = df["close"]
    last_close = close.iloc[-1]
    last_volume = df["volume"].iloc[-1]

    support, resistance = find_support_resistance(df, RESISTANCE_LOOKBACK)
    avg_vol = avg_volume(df, 20)
    rsi = calc_rsi(close, 14)
    last_rsi = rsi.iloc[-1]

    # --- إشارة 1: اختراق مقاومة بحجم ---
    if last_close > resistance and last_volume > avg_vol * VOLUME_MULTIPLIER:
        signals.append({
            "type": "اختراق مقاومة",
            "emoji": "🟢",
            "symbol": symbol,
            "price": last_close,
            "level": resistance,
            "rsi": last_rsi,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "stop_loss": support,
            "target1": last_close + (last_close - support) * 0.5,
            "target2": last_close + (last_close - support) * 1.0,
        })

    # --- إشارة 2: ارتداد من دعم ---
    prev_open = df["open"].iloc[-1]
    is_bullish_candle = last_close > prev_open
    near_support = df["low"].iloc[-1] <= support * (1 + SUPPORT_TOLERANCE)

    if near_support and is_bullish_candle and last_rsi < RSI_OVERSOLD:
        signals.append({
            "type": "ارتداد من دعم",
            "emoji": "🔵",
            "symbol": symbol,
            "price": last_close,
            "level": support,
            "rsi": last_rsi,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "stop_loss": support * 0.98,
            "target1": resistance,
            "target2": None,
        })

    return signals


def format_message(sig: dict) -> str:
    lines = [
        f"{sig['emoji']} إشارة {sig['type']}",
        f"العملة: {sig['symbol'].replace('-', '/')}",
        f"السعر الحالي: {sig['price']:.4f}$",
        f"المستوى: {sig['level']:.4f}$",
        f"RSI: {sig['rsi']:.1f}",
        f"الحجم: {sig['volume_ratio']:.1f}x المعدل",
        "",
        "📊 مستويات مقترحة (راجعها بنفسك قبل الدخول):",
        f"وقف الخسارة: {sig['stop_loss']:.4f}$",
    ]
    if sig.get("target1"):
        lines.append(f"هدف 1: {sig['target1']:.4f}$")
    if sig.get("target2"):
        lines.append(f"هدف 2: {sig['target2']:.4f}$")

    lines.append("")
    lines.append("⚠️ تذكير: هذه تنبيهات آلية وليست توصية، تحقق من القرار بنفسك")
    return "\n".join(lines)


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[خطأ] لم يتم تعيين TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID")
        print("--- الرسالة التي كانت ستُرسل ---")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"[تم الإرسال] {text[:40]}...")
    except Exception as e:
        print(f"[خطأ] فشل إرسال رسالة تيليغرام: {e}")


def main():
    print(f"بدء الفحص لعدد {len(WATCHLIST)} عملة...")
    total_signals = 0

    for symbol in WATCHLIST:
        df = fetch_klines(symbol)
        if df is None:
            continue

        signals = analyze_symbol(symbol, df)
        for sig in signals:
            msg = format_message(sig)
            send_telegram_message(msg)
            total_signals += 1

        time.sleep(0.3)  # تجنب تجاوز حدود معدل طلبات KuCoin العامة

    print(f"انتهى الفحص. عدد الإشارات المُرسلة: {total_signals}")


if __name__ == "__main__":
    main()

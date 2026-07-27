"""
=============================================================
ماسح العملات الرقمية الحلال (Halal Crypto Scanner & Bot)
محدث مع التحسين رقم 2: Caching, Rate Limiting & Retry Mechanism
=============================================================
"""
import os
import json
import logging
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from cachetools import cached, TTLCache

# إعداد السجل (Logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ==================== الإعدادات والثوابت ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BACKTEST_RESULTS_FILE = "backtest_results.json"

# قائمة العملات الحلال المعتمدة (مثال)
HALAL_COINS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", 
    "NEAR/USDT", "MATIC/USDT", "ATOM/USDT", "DOT/USDT"
]

TIMEFRAMES = ["4h", "1h"]

# تخزين مؤقت للماكرو والأسعار (صالح لمدة 60 ثانية لمنع حظر الطلبات)
macro_cache = TTLCache(maxsize=10, ttl=60)


# ==================== 1. جلب البيانات مع نظام إعادة المحاولة (Retry Mechanism) ====================

def fetch_from_okx(symbol: str, timeframe: str = "1h", limit: int = 100, retries: int = 3, delay: float = 2.0) -> pd.DataFrame | None:
    """جلب الشموع التاريخية من منصة OKX مع آلية إعادة المحاولة عند الفشل"""
    okx_symbol = symbol.replace("/", "-")
    tf_map = {"1h": "1H", "4h": "4H", "1d": "1D", "15m": "15m"}
    bar = tf_map.get(timeframe, "1H")
    
    url = f"https://www.okx.com/api/v5/market/candles?instId={okx_symbol}&bar={bar}&limit={limit}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("code") == "0" and res_json.get("data"):
                    raw_data = res_json["data"]
                    df = pd.DataFrame(raw_data, columns=["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
                    df = df.iloc[::-1].reset_index(drop=True)
                    for col in ["open", "high", "low", "close", "vol"]:
                        df[col] = df[col].astype(float)
                    df["time"] = pd.to_datetime(df["ts"].astype(int), unit="ms")
                    return df[["time", "open", "high", "low", "close", "vol"]].rename(columns={"vol": "volume"})
            elif resp.status_code == 429:
                logging.warning(f"تم تجاوز الحد المسموح (Rate Limit) لـ {symbol}. الانتظار قليلاً...")
                time.sleep(delay * (attempt + 1))
        except requests.exceptions.RequestException as e:
            logging.warning(f"محاولة {attempt + 1}/{retries} فشلت لـ {symbol}: {e}")
            time.sleep(delay)
            
    logging.error(f"فشل نهائي في جلب بيانات {symbol} بعد {retries} محاولات.")
    return None


def get_live_price(symbol: str, fallback_price: float = 0.0) -> float:
    """جلب السعر الفوري الحي مع معالجة الاستثناءات"""
    okx_symbol = symbol.replace("/", "-")
    url = f"https://www.okx.com/api/v5/market/ticker?instId={okx_symbol}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                return float(data[0].get("last", fallback_price))
    except Exception:
        pass
    return fallback_price


# ==================== 2. المؤشرات الفنية المتقدمة ====================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """حساب مؤشر متوسط المدى الحقيقي (ATR)"""
    if df is None or len(df) < period + 1:
        return 0.0
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    tr = np.zeros(len(df))
    for i in range(1, len(df)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
    
    return float(np.mean(tr[-period:]))


def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> dict:
    """حساب نطاقات بولينجر وضغط السعر (Squeeze)"""
    if df is None or len(df) < window:
        return {}
    
    close = df['close']
    middle = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    
    last_mid = float(middle.iloc[-1])
    last_up = float(upper.iloc[-1])
    last_low = float(lower.iloc[-1])
    last_close = float(close.iloc[-1])
    
    bandwidth = (last_up - last_low) / last_mid if last_mid > 0 else 0.0
    is_squeeze = bandwidth < 0.06
    
    return {
        "upper": last_up,
        "middle": last_mid,
        "lower": last_low,
        "bandwidth": round(bandwidth, 4),
        "is_squeeze": is_squeeze,
        "is_oversold_bb": last_close <= last_low,
        "is_overbought_bb": last_close >= last_up,
    }


def calculate_ema_indicators(df: pd.DataFrame) -> dict:
    """حساب المتوسطات الأسية والتقاطعات الذهبية"""
    if df is None or len(df) < 200:
        return {}
    
    ema_50 = df['close'].ewm(span=50, adjust=False).mean()
    ema_200 = df['close'].ewm(span=200, adjust=False).mean()
    
    l_close = float(df['close'].iloc[-1])
    l_50 = float(ema_50.iloc[-1])
    l_200 = float(ema_200.iloc[-1])
    
    return {
        "ema_50": l_50,
        "ema_200": l_200,
        "above_ema50": l_close > l_50,
        "above_ema200": l_close > l_200,
        "golden_cross": l_50 > l_200,
    }


def detect_market_structure(df: pd.DataFrame) -> dict:
    """كشف كسر الهيكل (BOS) وتغير الطابع (CHoCH)"""
    if df is None or len(df) < 20:
        return {"bos_bullish": False, "choch_bullish": False, "last_high": 0, "last_low": 0}
    
    recent_highs = df['high'].tail(15).values
    recent_lows = df['low'].tail(15).values
    current_close = float(df['close'].iloc[-1])
    
    prev_high = float(np.max(recent_highs[:-3]))
    prev_low = float(np.min(recent_lows[:-3]))
    
    bos_bullish = current_close > prev_high
    choch_bullish = current_close > prev_high and float(df['close'].iloc[-2]) <= prev_high
    
    return {
        "bos_bullish": bool(bos_bullish),
        "choch_bullish": bool(choch_bullish),
        "last_high": prev_high,
        "last_low": prev_low,
    }


# ==================== 3. فلاتر الماكرو مع التخزين المؤقت (Caching) ====================

@cached(macro_cache)
def evaluate_btc_dominance_filter() -> dict:
    """فلتر هيمنة البيتكوين مع استخدام الـ Caching لمنع حظر الطلبات المتكررة"""
    url = "https://api.coingecko.com/api/v3/global"
    headers = {"User-Agent": "Mozilla/5.0"}
    result = {"allow_signals": True, "signal_weight": 1.0, "market_phase": "neutral"}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            btc_d = data.get("market_cap_percentage", {}).get("btc", 50.0)
            if btc_d >= 58.0:
                result["signal_weight"] = 0.5
                result["market_phase"] = "btc_dominant"
            elif btc_d <= 50.0:
                result["signal_weight"] = 1.2
                result["market_phase"] = "alt_season"
    except Exception:
        pass
    return result


def detect_market_regime(df: pd.DataFrame) -> dict:
    """تحديد حالة السوق (Trending / Ranging / Squeeze)"""
    if df is None or len(df) < 30:
        return {"regime": "neutral", "allowed_strategies": ["all"]}
    
    bb = calculate_bollinger_bands(df)
    bandwidth = bb.get("bandwidth", 0.1)
    
    if bandwidth < 0.05:
        return {"regime": "squeeze", "allowed_strategies": ["VOLATILE_BREAKOUT", "FVG_SCALP"]}
    elif bandwidth > 0.18:
        return {"regime": "volatile", "allowed_strategies": ["OVERSOLD_REVERSAL"]}
    
    return {"regime": "trend", "allowed_strategies": ["GOLDEN_TREND", "MASTER_SIGNAL", "WYCKOFF_SMC"]}


# ==================== 4. شجرة التصنيف والاستراتيجيات ====================

def classify_and_format_signal(sig: dict, macro_info: dict) -> tuple[str, str]:
    """تصنيف الإشارة الاستراتيجية وتحديد نوع الخطة"""
    confluences = sig.get("confluence", [])
    bollinger = sig.get("bollinger", {})
    wyckoff = sig.get("wyckoff", {})
    ema = sig.get("ema", {})
    
    strategy_type = "STANDARD"
    
    if wyckoff.get("is_wyckoff_setup"):
        strategy_type = "WYCKOFF_SMC"
    elif bollinger.get("is_squeeze"):
        strategy_type = "VOLATILE_BREAKOUT"
    elif ema.get("golden_cross") and ema.get("above_ema50"):
        strategy_type = "GOLDEN_TREND"
    elif bollinger.get("is_oversold_bb"):
        strategy_type = "OVERSOLD_REVERSAL"
    elif len(confluences) >= 3:
        strategy_type = "MASTER_SIGNAL"
    else:
        strategy_type = "FVG_SCALP"
        
    msg = f"🚀 <b>إشارة تداول: {sig['symbol']}</b> ({strategy_type})\n- السعر: {sig['price']}\n- الوقف: {sig['stop_loss']}"
    return strategy_type, msg


# ==================== 5. إرسال التنبيهات عبر تيليغرام ====================

def send_telegram_message(message: str):
    """إرسال التنبيه مع حماية ضد أخطاء الشبكة"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.info(f"[محاكاة تيليغرام]\n{message}")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"فشل إرسال رسالة تيليغرام: {e}")


# ==================== التشغيل الرئيسي (Main Execution) ====================

def main():
    logging.info("--- بدء دورة فحص العملات (مع تفعيل الحماية والـ Caching) ---")
    
    macro_btc = evaluate_btc_dominance_filter()
    logging.info(f"حالة هيمنة البيتكوين: {macro_btc['market_phase']} (وزن الإشارة: {macro_btc['signal_weight']})")
    
    for symbol in HALAL_COINS:
        for tf in TIMEFRAMES:
            try:
                df = fetch_from_okx(symbol, timeframe=tf, limit=100)
                if df is None or len(df) < 50:
                    continue
                    
                regime = detect_market_regime(df)
                bb = calculate_bollinger_bands(df)
                ema = calculate_ema_indicators(df)
                ms = detect_market_structure(df)
                
                current_price = float(df['close'].iloc[-1])
                atr = calculate_atr(df)
                
                sig = {
                    "symbol": symbol,
                    "price": current_price,
                    "stop_loss": current_price - (atr * 1.5),
                    "target1": current_price + (atr * 1.5),
                    "target3": current_price + (atr * 3.5),
                    "confluence": ["دعم قوي", "تقاطع ايجابي"],
                    "bollinger": bb,
                    "ema": ema,
                    "wyckoff": {"is_wyckoff_setup": False}
                }
                
                strat_type, msg = classify_and_format_signal(sig, macro_btc)
                
                if strat_type not in regime.get("allowed_strategies", ["all"]) and "all" not in regime.get("allowed_strategies", []):
                    continue
                    
                if macro_btc["signal_weight"] > 0.4:
                    send_telegram_message(msg)
                    
                # فاصل زمني قصير لمنع الضغط على السيرفرات (Rate Limiting احترازي)
                time.sleep(0.5)
                
            except Exception as loop_err:
                logging.error(f"حدث خطأ غير متوقع أثناء معالجة العملة {symbol} على فريم {tf}: {loop_err}")
                
    logging.info("--- اكتملت دورة الفحص بنجاح تام ---")

if __name__ == "__main__":
    main()

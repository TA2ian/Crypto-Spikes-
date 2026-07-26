"""
ماسح العملات الحلال - السكربت الرئيسي الموحد (Binance + Modules Edition)
يقوم بجلب البيانات من باينانس، الفحص الفني، إدارة نظام النقاط التراكمي،
وحساب الأهداف الديناميكية وتقييم SMC والمشاعر.
"""
import os
import json
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import pandas as pd

# استدعاء الملفات الأساسية
from coins import WATCHLIST
from indicators import calc_rsi, find_support_resistance, avg_volume
from patterns import (
    detect_candle_patterns,
    find_bullish_order_block,
    find_bearish_order_block,
    price_near_zone,
)
from divergence import analyze_divergence
from fibonacci import analyze_fibonacci
# استدعاء آمن لـ chart_patterns
try:
    from chart_patterns import detect_all_patterns
except ImportError:
    def detect_all_patterns(df): 
        return []

from multi_timeframe import scan_multi_timeframe, TIMEFRAMES
from candle_state import (
    load_state as load_candle_state,
    save_state as save_candle_state,
    is_new_candle,
    mark_alerted,
)
from cvd import analyze_cvd
# --- استدعاء coin_score بشكل آمن ---
try:
    from coin_score import (
        load_state as load_score_state,
        save_state as save_score_state,
        add_points,
        should_alert,
        mark_alert_sent,
        get_score_breakdown,
        current_score,
        clean_old_events,
        WEIGHTS,
        SCORE_THRESHOLD,
        WINDOW_HOURS,
    )
except ImportError:
    try:
        from coin_score import add_points, should_alert, mark_alert_sent, WEIGHTS
        def load_score_state(): return {}
        def save_score_state(s): pass
        def get_score_breakdown(s, c): return ""
        def current_score(s, c): return 0
        def clean_old_events(s): pass
        SCORE_THRESHOLD = 5.0
        WINDOW_HOURS = 24
    except ImportError:
        WEIGHTS = {"base_signal": 1.0}
        SCORE_THRESHOLD = 5.0
        WINDOW_HOURS = 24
        def load_score_state(): return {}
        def save_score_state(s): pass
        def add_points(*args, **kwargs): pass
        def should_alert(*args, **kwargs): return True
        def mark_alert_sent(*args, **kwargs): pass
        def get_score_breakdown(*args, **kwargs): return ""
        def current_score(*args, **kwargs): return 0
        def clean_old_events(*args, **kwargs): pass


# --- استدعاء الموديولات الذكية الجديدة ---
# --- استدعاء الموديولات الذكية الجديدة بشكل آمن ---
try:
    from modules.smc import detect_fvg, detect_liquidity_sweep
    from modules.sentiment import get_fear_and_greed_index
    from modules.dynamic_risk import calculate_atr, calculate_dynamic_targets, rate_signal_confidence
except ImportError:
    from smc import detect_fvg, detect_liquidity_sweep
    from sentiment import get_fear_and_greed_index
    from dynamic_risk import calculate_atr, calculate_dynamic_targets, rate_signal_confidence

# ============ الإعدادات ============
BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"
TIMEFRAME = "1h"
CANDLE_LIMIT = 80

RESISTANCE_LOOKBACK = 20
SUPPORT_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5
RSI_OVERSOLD = 35
SUPPORT_TOLERANCE = 0.005
DIVERGENCE_VOLUME_MULTIPLIER = 2.0

SHOW_DIVERGENCE = True
SHOW_FIBONACCI = True
SHOW_CHART_PATTERNS = True
SHOW_CVD = True

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
SIGNALS_JSON_PATH = os.path.join(DOCS_DIR, "signals.json")
CONFIG_JSON_PATH = os.path.join(DOCS_DIR, "config.json")


BINANCE_ENDPOINTS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api1.binance.com/api/v3/klines",
    "https://api2.binance.com/api/v3/klines",
    "https://api3.binance.com/api/v3/klines",
    "https://api.binance.com/api/v3/klines"
]

def fetch_from_okx(symbol: str, timeframe: str) -> pd.DataFrame | None:
    """جلب من OKX"""
    clean_symbol = symbol.replace("/", "-").upper()
    if not clean_symbol.endswith("-USDT"):
        clean_symbol = f"{clean_symbol}-USDT"

    tf_map = {"1h": "1H", "4h": "4H", "1d": "1D", "1hour": "1H", "4hour": "4H", "1day": "1D"}
    okx_tf = tf_map.get(timeframe, "1H")

    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": clean_symbol, "bar": okx_tf, "limit": str(CANDLE_LIMIT)}

    try:
        resp = requests.get(url, params=params, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == "0" and data.get("data"):
                raw_candles = list(reversed(data["data"]))
                df = pd.DataFrame(raw_candles, columns=["time", "open", "high", "low", "close", "volume", "volCcy", "volCcyQuote", "confirm"])
                df = df[["time", "open", "high", "low", "close", "volume"]]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df.reset_index(drop=True)
    except Exception:
        pass
    return None


def fetch_from_bybit(symbol: str, timeframe: str) -> pd.DataFrame | None:
    """جلب من Bybit"""
    clean_symbol = symbol.replace("-", "").replace("/", "").upper()
    tf_map = {"1h": "60", "4h": "240", "1d": "D", "1hour": "60", "4hour": "240", "1day": "D"}
    bybit_tf = tf_map.get(timeframe, "60")

    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "spot", "symbol": clean_symbol, "interval": bybit_tf, "limit": CANDLE_LIMIT}

    try:
        resp = requests.get(url, params=params, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                raw_candles = list(reversed(data["result"]["list"]))
                df = pd.DataFrame(raw_candles, columns=["time", "open", "high", "low", "close", "volume", "turnover"])
                df = df[["time", "open", "high", "low", "close", "volume"]]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df.reset_index(drop=True)
    except Exception:
        pass
    return None


def fetch_from_mexc(symbol: str, timeframe: str) -> pd.DataFrame | None:
    """جلب من MEXC"""
    clean_symbol = symbol.replace("-", "").replace("/", "").upper()
    tf_map = {"1h": "60m", "4h": "4h", "1d": "1D", "1hour": "60m", "4hour": "4h", "1day": "1D"}
    mexc_tf = tf_map.get(timeframe, "60m")

    url = "https://api.mexc.com/api/v3/klines"
    params = {"symbol": clean_symbol, "interval": mexc_tf, "limit": CANDLE_LIMIT}

    try:
        resp = requests.get(url, params=params, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "close_time", "quote_vol"])
                df = df[["time", "open", "high", "low", "close", "volume"]]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df.reset_index(drop=True)
    except Exception:
        pass
    return None


def fetch_klines(symbol: str, timeframe: str = TIMEFRAME) -> pd.DataFrame | None:
    """جلب البيانات بالتتابع: OKX -> Bybit -> MEXC"""
    
    # 1. OKX
    df = fetch_from_okx(symbol, timeframe)
    if df is not None:
        return df

    # 2. Bybit
    df = fetch_from_bybit(symbol, timeframe)
    if df is not None:
        return df

    # 3. MEXC
    df = fetch_from_mexc(symbol, timeframe)
    if df is not None:
        return df

    print(f"[خطأ] فشل جلب بيانات {symbol} من جميع المنصات الثلاث (OKX, Bybit, MEXC)")
    return None



def build_extra_analysis(df: pd.DataFrame, rsi: pd.Series) -> dict:
    """تحليلات الطبقات الفنية الإضافية"""
    extra = {}
    if SHOW_DIVERGENCE:
        try:
            extra["divergence"] = analyze_divergence(df, rsi, volume_multiplier=DIVERGENCE_VOLUME_MULTIPLIER)
        except Exception: pass
    if SHOW_FIBONACCI:
        try:
            extra["fibonacci"] = analyze_fibonacci(df, lookback=30)
        except Exception: pass
    if SHOW_CHART_PATTERNS:
        try:
            extra["chart_patterns"] = detect_all_patterns(df)
        except Exception: pass
    if SHOW_CVD:
        try:
            extra["cvd"] = analyze_cvd(df)
        except Exception: pass
    return extra

def detect_market_structure(df: pd.DataFrame, window: int = 5) -> dict:
    """
    محاكاة مؤشر PA Toolkit في تحديد القمم والقيعان وكسر الهيكل (BOS / CHoCH)
    """
    result = {"bos_bullish": False, "choch_bullish": False, "last_high": None, "last_low": None}
    
    if len(df) < window * 2 + 5:
        return result

    # تحديد القمم والقيعان المحلية (Pivots)
    highs = df['high']
    lows = df['low']
    
    # البحث عن آخر قمة وقاع محليين
    pivot_highs = highs[(highs == highs.rolling(window * 2 + 1, center=True).max())]
    pivot_lows = lows[(lows == lows.rolling(window * 2 + 1, center=True).min())]

    if not pivot_highs.empty:
        result["last_high"] = pivot_highs.iloc[-1]
    if not pivot_lows.empty:
        result["last_low"] = pivot_lows.iloc[-1]

    last_close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2]

    # كسر هيكل صعودي (BOS): إغلاق الشمعة الحالية أعلى من آخر قمة سابقة
    if result["last_high"] and last_close > result["last_high"] and prev_close <= result["last_high"]:
        result["bos_bullish"] = True

    # تغير الاتجاه للصعود (CHoCH): كسر قمة رئيسية بعد اتجاه هابط
    if result["last_high"] and last_close > result["last_high"]:
        # إذا كان الاتجاه السابق هابطاً وتم كسر آخر قمة
        result["choch_bullish"] = True

    return result


def detect_volume_imbalance_and_effort(df: pd.DataFrame, vol_mult: float = 2.0) -> bool:
    """
    محاكاة شموع الجهد والسيولة المرتفعة (Volume Spikes) الخاصة بـ PA Toolkit
    """
    if len(df) < 20:
        return False
    
    avg_vol = df['volume'].iloc[-21:-1].mean()
    last_vol = df['volume'].iloc[-1]
    last_close = df['close'].iloc[-1]
    last_open = df['open'].iloc[-1]

    # شمعة صعودية بحجم تداول مضاعف مع إغلاق قوي
    is_bullish_effort = (last_vol > avg_vol * vol_mult) and (last_close > last_open)
    return is_bullish_effort

def analyze_symbol(symbol: str, df: pd.DataFrame, score_state: dict = None) -> list[dict]:
    """تحليل الشمعة وتطبيق منطق الموديولات الجديدة"""
    signals = []
    if df is None or len(df) < max(RESISTANCE_LOOKBACK, SUPPORT_LOOKBACK) + 5:
        return signals

    closed_df = df.iloc[:-1]
    last_row = closed_df.iloc[-1]
    last_close = float(last_row["close"])
    last_volume = float(last_row["volume"])

    support, resistance = find_support_resistance(closed_df, RESISTANCE_LOOKBACK)
    avg_vol = avg_volume(closed_df, 20)
    rsi = calc_rsi(closed_df["close"], 14)
    last_rsi = float(rsi.iloc[-1])

    candle_patterns = detect_candle_patterns(closed_df)
    bull_ob = find_bullish_order_block(closed_df)
    near_bull_ob = price_near_zone(last_close, bull_ob)

    # استخراج الأسماء بأمان
    pattern_names = [p.get("pattern", "") if isinstance(p, dict) else str(p) for p in candle_patterns]
    has_bullish_pattern = any(p in {"مطرقة (ارتداد صعودي)", "ابتلاع صعودي"} for p in pattern_names)

    extra_analysis = build_extra_analysis(closed_df, rsi)

    # --- حاسبات الموديولات المبتكرة (SMC & Dynamic Risk) ---
    atr = calculate_atr(closed_df)
    fvg = detect_fvg(closed_df)
    is_sweep = detect_liquidity_sweep(closed_df)
    # --- تحليلات PA Toolkit Lite المضافة ---
    ms = detect_market_structure(closed_df)
    is_bos = ms["bos_bullish"]
    is_choch = ms["choch_bullish"]
    is_effort_candle = detect_volume_imbalance_and_effort(closed_df)

        def confluence_note() -> list[str]:
        notes = []
        if has_bullish_pattern: notes.append("نمط شمعة صعودي")
        if near_bull_ob: notes.append("قرب Order Block")
        if fvg: notes.append(f"وجود FVG ({fvg['size_pct']:.2f}%)")
        if is_sweep: notes.append("سحب سيولة (Liquidity Sweep)")

        # إضافة تأكيدات PA Toolkit
        if is_bos: notes.append("كسر هيكل صعودي (BOS ⚡)")
        if is_choch: notes.append("تغير اتجاه صعودي (CHoCH 🔄)")
        if is_effort_candle: notes.append("شمعة جهد وسيولة عالية (Volume Spike 📊)")

        return notes


    # --- 1. إشارة اختراق المقاومة ---
    if last_close > resistance and last_volume > avg_vol * VOLUME_MULTIPLIER:
        notes = confluence_note()
        stop_loss, target1, target2 = calculate_dynamic_targets(last_close, atr, "LONG")
        stars = rate_signal_confidence(bool(notes), fvg, is_sweep)

        signals.append({
            "type": "اختراق مقاومة",
            "emoji": "🟢🔥" if notes else "🟢",
            "stars": stars,
            "symbol": symbol,
            "price": last_close,
            "level": resistance,
            "rsi": last_rsi,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "stop_loss": stop_loss,
            "target1": target1,
            "target2": target2,
            "confluence": notes,
            "extra": extra_analysis,
        })
        if score_state:
            add_points(score_state, symbol, "bullish", WEIGHTS.get("base_signal", 1.0), "اختراق مقاومة")

    # --- 2. إشارة ارتداد من دعم ---
    is_bullish_candle = last_close > float(last_row["open"])
    near_support = float(last_row["low"]) <= support * (1 + SUPPORT_TOLERANCE)

    if near_support and is_bullish_candle and last_rsi < RSI_OVERSOLD:
        notes = confluence_note()
        stop_loss, target1, target2 = calculate_dynamic_targets(last_close, atr, "LONG")
        stars = rate_signal_confidence(bool(notes), fvg, is_sweep)

        signals.append({
            "type": "ارتداد من دعم",
            "emoji": "🔵🔥" if notes else "🔵",
            "stars": stars,
            "symbol": symbol,
            "price": last_close,
            "level": support,
            "rsi": last_rsi,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "stop_loss": stop_loss,
            "target1": target1,
            "target2": target2,
            "confluence": notes,
            "extra": extra_analysis,
        })
        if score_state:
            add_points(score_state, symbol, "bullish", WEIGHTS.get("base_signal", 1.0), "ارتداد من دعم")

    return signals


def format_message(sig: dict, fng: dict = None) -> str:
    """تنسيق رسالة التنبيه لـ Telegram بأسلوب محترف"""
    stars_str = f" [{sig.get('stars', '⭐')}]" if sig.get('stars') else ""
    lines = [
        f"<b>{sig['emoji']} إشارة {sig['type']}{stars_str}</b>",
        f"<b>العملة:</b> {sig['symbol'].replace('-', '/')}",
        f"<b>السعر الحالي:</b> {sig['price']:.4f}$",
        f"<b>المستوى:</b> {sig['level']:.4f}$",
        f"<b>RSI:</b> {sig['rsi']:.1f} | <b>الحجم:</b> {sig['volume_ratio']:.1f}x",
    ]

    if fng:
        lines.append(f"🧠 <b>مؤشر المشاعر العام:</b> {fng['value']} ({fng['status']})")

    if sig.get("confluence"):
        lines.append("")
        lines.append("✅ <b>تأكيدات السيولة والنماذج:</b> " + "، ".join(sig["confluence"]))

    lines += [
        "",
        "📊 <b>مستويات إدارة المخاطر (مبنية على ATR):</b>",
        f"• <b>وقف الخسارة:</b> {sig['stop_loss']:.4f}$",
        f"• <b>هدف 1:</b> {sig['target1']:.4f}$",
        f"• <b>هدف 2:</b> {sig['target2']:.4f}$",
        "\n⚠️ <i>تنبيه آلي استرشادي - راجع الشارت بنفسك قبل اتخاذ القرار</i>"
    ]
    return "\n".join(lines)


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[تنبيه] لم يتم تعيين مفاتيح تيليغرام. طباعة الرسالة:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
    except Exception as e:
        print(f"[خطأ] فشل إرسال رسالة تيليغرام: {e}")


def main():
    print(f"بدء فحص باينانس لعدد {len(WATCHLIST)} عملة...")
    all_signals_for_app = []
    score_state = load_score_state()

    # جلب مؤشر الخوف والجشع لفلترة المشاعر
    fng_status = get_fear_and_greed_index()

    def process_worker(sym):
        df = fetch_klines(sym)
        if df is None: return []
        try:
            return analyze_symbol(sym, df, score_state=score_state)
        except Exception as e:
            print(f"[خطأ تحليل] {sym}: {e}")
            return []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_worker, sym) for sym in WATCHLIST]
        for future in futures:
            signals = future.result()
            for sig in signals:
                msg = format_message(sig, fng=fng_status)
                send_telegram_message(msg)
                all_signals_for_app.append(sig)

    save_score_state(score_state)
    print(f"انتهى الفحص بنجاح. تم اكتشاف {len(all_signals_for_app)} إشارة.")


if __name__ == "__main__":
    main()

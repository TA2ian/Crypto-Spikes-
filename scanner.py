"""
ماسح العملات الحلال - السكربت الرئيسي الموحد (Multi-Timeframe Edition: 1h, 4h, 1d, 3d, 1w)
يتضمن التحليل الشامل عبر 5 فريمات زَمَنِيّة، الشجرة الشرطية للخطط الـ 7 بدون تعارض، 
ودمج مؤشرات (Bollinger Bands, EMA 50/200, Wyckoff, SMC, CVD, Fibonacci, Chart Patterns).
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

# --- استدعاء الموديولات الذكية ---
try:
    from modules.smc import detect_fvg, detect_liquidity_sweep
    from modules.sentiment import get_fear_and_greed_index
    from modules.dynamic_risk import calculate_atr, rate_signal_confidence
except ImportError:
    from smc import detect_fvg, detect_liquidity_sweep
    from sentiment import get_fear_and_greed_index
    from dynamic_risk import calculate_atr, rate_signal_confidence

# ============ الإعدادات ============
ACTIVE_TIMEFRAMES = ["1h", "4h", "1d", "3d", "1w"]
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

# ============ جلب البيانات من المنصات ============
def fetch_from_okx(symbol: str, timeframe: str) -> pd.DataFrame | None:
    clean_symbol = symbol.replace("/", "-").upper()
    if not clean_symbol.endswith("-USDT"):
        clean_symbol = f"{clean_symbol}-USDT"

    tf_map = {"1h": "1H", "4h": "4H", "1d": "1D", "3d": "3D", "1w": "1W"}
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
    clean_symbol = symbol.replace("-", "").replace("/", "").upper()
    tf_map = {"1h": "60", "4h": "240", "1d": "D", "3d": "3D", "1w": "W"}
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
    clean_symbol = symbol.replace("-", "").replace("/", "").upper()
    tf_map = {"1h": "60m", "4h": "4h", "1d": "1D", "3d": "3D", "1w": "1W"}
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

def fetch_klines(symbol: str, timeframe: str = "1h") -> pd.DataFrame | None:
    df = fetch_from_okx(symbol, timeframe)
    if df is not None: return df
    df = fetch_from_bybit(symbol, timeframe)
    if df is not None: return df
    df = fetch_from_mexc(symbol, timeframe)
    if df is not None: return df
    return None

# ============ أدوات التحليل الفني ============
def calculate_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> dict:
    if len(df) < window:
        return {}
    
    sma = df['close'].rolling(window=window).mean()
    std = df['close'].rolling(window=window).std()
    
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    
    last_close = df['close'].iloc[-1]
    last_upper = upper_band.iloc[-1]
    last_lower = lower_band.iloc[-1]
    
    bandwidth = (last_upper - last_lower) / sma.iloc[-1] if sma.iloc[-1] else 0
    
    return {
        "upper": float(last_upper),
        "middle": float(sma.iloc[-1]),
        "lower": float(last_lower),
        "is_oversold_bb": float(last_close) <= float(last_lower),
        "is_overbought_bb": float(last_close) >= float(last_upper),
        "is_squeeze": bandwidth < 0.10,
        "bandwidth": float(bandwidth)
    }

def calculate_ema_indicators(df: pd.DataFrame) -> dict:
    if len(df) < 50:
        return {}
    
    df_copy = df.copy()
    df_copy['ema_50'] = df_copy['close'].ewm(span=50, adjust=False).mean()
    df_copy['ema_200'] = df_copy['close'].ewm(span=min(len(df_copy), 200), adjust=False).mean()
    
    last_close = float(df_copy['close'].iloc[-1])
    ema50 = float(df_copy['ema_50'].iloc[-1])
    ema200 = float(df_copy['ema_200'].iloc[-1])
    
    return {
        "ema_50": ema50,
        "ema_200": ema200,
        "above_ema50": last_close > ema50,
        "above_ema200": last_close > ema200,
        "golden_cross": ema50 > ema200
    }

def build_extra_analysis(df: pd.DataFrame, rsi: pd.Series) -> dict:
    extra = {}
    if SHOW_DIVERGENCE:
        try: extra["divergence"] = analyze_divergence(df, rsi, volume_multiplier=DIVERGENCE_VOLUME_MULTIPLIER)
        except Exception: pass
    if SHOW_FIBONACCI:
        try: extra["fibonacci"] = analyze_fibonacci(df, lookback=30)
        except Exception: pass
    if SHOW_CHART_PATTERNS:
        try: extra["chart_patterns"] = detect_all_patterns(df)
        except Exception: pass
    if SHOW_CVD:
        try: extra["cvd"] = analyze_cvd(df)
        except Exception: pass
    return extra

def detect_market_structure(df: pd.DataFrame, window: int = 5) -> dict:
    result = {"bos_bullish": False, "choch_bullish": False, "last_high": None, "last_low": None}
    if len(df) < window * 2 + 5: return result

    highs, lows = df['high'], df['low']
    pivot_highs = highs[(highs == highs.rolling(window * 2 + 1, center=True).max())]
    pivot_lows = lows[(lows == lows.rolling(window * 2 + 1, center=True).min())]

    if not pivot_highs.empty: result["last_high"] = pivot_highs.iloc[-1]
    if not pivot_lows.empty: result["last_low"] = pivot_lows.iloc[-1]

    last_close, prev_close = df['close'].iloc[-1], df['close'].iloc[-2]

    if result["last_high"] and last_close > result["last_high"] and prev_close <= result["last_high"]:
        result["bos_bullish"] = True
    if result["last_high"] and last_close > result["last_high"]:
        result["choch_bullish"] = True

    return result

def detect_volume_imbalance_and_effort(df: pd.DataFrame, vol_mult: float = 2.0) -> bool:
    if len(df) < 20: return False
    avg_vol = df['volume'].iloc[-21:-1].mean()
    last_vol, last_close, last_open = df['volume'].iloc[-1], df['close'].iloc[-1], df['open'].iloc[-1]
    return (last_vol > avg_vol * vol_mult) and (last_close > last_open)

def detect_wyckoff_bull_market(df: pd.DataFrame, ms: dict, is_sweep: bool, is_effort: bool, bull_ob: dict, ema_data: dict) -> dict:
    wyckoff_result = {"is_bull_market": False, "wyckoff_phase": None, "is_wyckoff_setup": False}
    if len(df) < 50: return wyckoff_result

    if ema_data.get("above_ema50") and ema_data.get("golden_cross"):
        wyckoff_result["is_bull_market"] = True

    if is_sweep and bull_ob:
        wyckoff_result["wyckoff_phase"] = "Phase C (Spring - تجميع وسحب سيولة)"
        wyckoff_result["is_wyckoff_setup"] = True
    elif ms.get("bos_bullish") and is_effort:
        wyckoff_result["wyckoff_phase"] = "Phase D (SOS - علامة قوة وااختراق)"
        wyckoff_result["is_wyckoff_setup"] = True
    elif wyckoff_result["is_bull_market"] and bull_ob and ms.get("choch_bullish"):
        wyckoff_result["wyckoff_phase"] = "Phase E (LPS - إعادة اختبار الدعم)"
        wyckoff_result["is_wyckoff_setup"] = True

    return wyckoff_result

# ============ فحص اتجاه الماكرو (3D + 1W) ============
def analyze_macro_trends(symbol: str) -> dict:
    df_3d = fetch_klines(symbol, timeframe="3d")
    df_1w = fetch_klines(symbol, timeframe="1w")

    macro_data = {
        "macro_bullish": False,
        "d3_support": 0, "d3_resistance": 0, "d3_rsi": 50,
        "w1_support": 0, "w1_resistance": 0, "w1_rsi": 50
    }

    if df_3d is not None and len(df_3d) >= 20:
        c_3d = df_3d.iloc[:-1]
        last_3d_close = float(c_3d["close"].iloc[-1])
        ema20_3d = c_3d["close"].ewm(span=20, adjust=False).mean().iloc[-1]
        macro_data["d3_rsi"] = float(calc_rsi(c_3d["close"], 14).iloc[-1])
        macro_data["d3_support"], macro_data["d3_resistance"] = find_support_resistance(c_3d, 10)
        d3_bullish = last_3d_close > ema20_3d and macro_data["d3_rsi"] > 45
    else:
        d3_bullish = False

    if df_1w is not None and len(df_1w) >= 20:
        c_1w = df_1w.iloc[:-1]
        last_1w_close = float(c_1w["close"].iloc[-1])
        ema20_1w = c_1w["close"].ewm(span=20, adjust=False).mean().iloc[-1]
        macro_data["w1_rsi"] = float(calc_rsi(c_1w["close"], 14).iloc[-1])
        macro_data["w1_support"], macro_data["w1_resistance"] = find_support_resistance(c_1w, 10)
        w1_bullish = last_1w_close > ema20_1w and macro_data["w1_rsi"] > 45
    else:
        w1_bullish = False

    macro_data["macro_bullish"] = d3_bullish or w1_bullish
    return macro_data

def calculate_dynamic_targets(last_close: float, atr: float, resistance: float, fvg: dict, ms: dict, extra_analysis: dict, candle_patterns: list) -> tuple:
    stop_loss = last_close - (atr * 1.5)

    pattern_target = 0
    if candle_patterns and isinstance(candle_patterns[0], dict):
        p = candle_patterns[0]
        if "high" in p and "low" in p:
            pattern_target = last_close + (p["high"] - p["low"])

    target1 = pattern_target if pattern_target > last_close else (resistance if resistance > last_close else last_close + (atr * 1.5))

    chart_patterns = extra_analysis.get("chart_patterns", {})
    cp_target = chart_patterns.get("target", 0) if isinstance(chart_patterns, dict) else 0

    if cp_target > target1: target2 = cp_target
    elif fvg and fvg.get("top", 0) > target1: target2 = fvg["top"]
    else: target2 = target1 + (atr * 2.0)

    fib_data = extra_analysis.get("fibonacci", {})
    fib_1618 = fib_data.get("ext_1618", 0) if isinstance(fib_data, dict) else 0
    target3 = ms["last_high"] if (ms.get("last_high") and ms["last_high"] > target2) else (fib_1618 if fib_1618 > target2 else target2 + (atr * 3.5))

    fib_2618 = fib_data.get("ext_2618", 0) if isinstance(fib_data, dict) else 0
    target4 = fib_2618 if fib_2618 > target3 else target3 + (atr * 4.5)

    fib_3618 = fib_data.get("ext_3618", 0) if isinstance(fib_data, dict) else 0
    macro_target = fib_3618 if fib_3618 > target4 else last_close + (atr * 8.0)

    t1 = round(max(target1, last_close * 1.01), 4)
    t2 = round(max(target2, t1 * 1.015), 4)
    t3 = round(max(target3, t2 * 1.02), 4)
    t4 = round(max(target4, t3 * 1.025), 4)
    macro_t = round(max(macro_target, t4 * 1.05), 4)
    sl = round(stop_loss, 4)

    return sl, t1, t2, t3, t4, macro_t

# ============ تحليل العملة ============
def analyze_symbol(symbol: str, df: pd.DataFrame, timeframe: str = "1h", score_state: dict = None) -> list[dict]:
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

    bb_data = calculate_bollinger_bands(closed_df)
    ema_data = calculate_ema_indicators(closed_df)

    candle_patterns = detect_candle_patterns(closed_df)
    bull_ob = find_bullish_order_block(closed_df)
    near_bull_ob = price_near_zone(last_close, bull_ob)

    pattern_names = [p.get("pattern", "") if isinstance(p, dict) else str(p) for p in candle_patterns]
    has_bullish_pattern = any(p in {"مطرقة (ارتداد صعودي)", "ابتلاع صعودي"} for p in pattern_names)

    extra_analysis = build_extra_analysis(closed_df, rsi)

    atr = calculate_atr(closed_df)
    fvg = detect_fvg(closed_df)
    is_sweep = detect_liquidity_sweep(closed_df)
    ms = detect_market_structure(closed_df)
    is_bos = ms["bos_bullish"]
    is_choch = ms["choch_bullish"]
    is_effort_candle = detect_volume_imbalance_and_effort(closed_df)

    wyckoff_data = detect_wyckoff_bull_market(closed_df, ms, is_sweep, is_effort_candle, bull_ob, ema_data)

    def confluence_note() -> list[str]:
        notes = []
        if has_bullish_pattern: notes.append("نمط شمعة صعودي")
        if near_bull_ob: notes.append("قرب Order Block")
        if fvg: notes.append(f"وجود FVG ({fvg['size_pct']:.2f}%)")
        if is_sweep: notes.append("سحب سيولة (Liquidity Sweep)")
        if is_bos: notes.append("كسر هيكل صعودي (BOS)")
        if is_choch: notes.append("تغير اتجاه صعودي (CHoCH)")
        if is_effort_candle: notes.append("شمعة جهد وسيولة عالية (Volume Spike)")

        if bb_data.get("is_oversold_bb"): notes.append("ملامسة حد البولينجر السفلي")
        if bb_data.get("is_squeeze"): notes.append("انكماش البولينجر (تأهب لانفجار سعري)")

        if ema_data.get("above_ema50") and ema_data.get("above_ema200"): notes.append("تداول فوق EMA 50 & 200 (اتجاه صاعد قاطِع)")
        elif ema_data.get("golden_cross"): notes.append("تقاطع ذهبي EMA 50/200")

        div_data = extra_analysis.get("divergence")
        if div_data and isinstance(div_data, dict) and div_data.get("bullish"):
            notes.append(f"دايفرجنس صعودي ({div_data.get('type', 'إيجابي')})")

        cp_data = extra_analysis.get("chart_patterns")
        if cp_data:
            if isinstance(cp_data, dict) and cp_data.get("pattern"):
                notes.append(f"نمط تشارت: {cp_data['pattern']}")
            elif isinstance(cp_data, list) and len(cp_data) > 0:
                p_names = [p.get("pattern", "") if isinstance(p, dict) else str(p) for p in cp_data]
                notes.append(f"أنماط تشارت: {', '.join(p_names)}")

        return notes

    tf_weight_multiplier = 1.0
    if timeframe == "4h": tf_weight_multiplier = 1.3
    elif timeframe == "1d": tf_weight_multiplier = 1.8
    elif timeframe == "3d": tf_weight_multiplier = 2.2
    elif timeframe == "1w": tf_weight_multiplier = 2.8

    # 1. اختراق مقاومة
    if last_close > resistance and last_volume > avg_vol * VOLUME_MULTIPLIER:
        notes = confluence_note()
        sl, t1, t2, t3, t4, macro_t = calculate_dynamic_targets(last_close, atr, resistance, fvg, ms, extra_analysis, candle_patterns)
        stars = rate_signal_confidence(bool(notes), fvg, is_sweep)

        signals.append({
            "type": "اختراق مقاومة",
            "stars": stars,
            "symbol": symbol,
            "price": last_close,
            "level": resistance,
            "rsi": last_rsi,
            "ema": ema_data,
            "bollinger": bb_data,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "timeframe": timeframe,
            "stop_loss": sl,
            "target1": t1, "target2": t2, "target3": t3, "target4": t4,
            "macro_target": macro_t,
            "wyckoff": wyckoff_data,
            "confluence": notes,
            "extra": extra_analysis,
        })
        if score_state is not None: 
            add_points(score_state, symbol, "bullish", WEIGHTS.get("base_signal", 1.0) * tf_weight_multiplier, f"اختراق مقاومة ({timeframe})")

    # 2. ارتداد من دعم
    is_bullish_candle = last_close > float(last_row["open"])
    near_support = float(last_row["low"]) <= support * (1 + SUPPORT_TOLERANCE)

    if near_support and is_bullish_candle and last_rsi < RSI_OVERSOLD:
        notes = confluence_note()
        sl, t1, t2, t3, t4, macro_t = calculate_dynamic_targets(last_close, atr, support, fvg, ms, extra_analysis, candle_patterns)
        stars = rate_signal_confidence(bool(notes), fvg, is_sweep)

        signals.append({
            "type": "ارتداد من دعم",
            "stars": stars,
            "symbol": symbol,
            "price": last_close,
            "level": support,
            "rsi": last_rsi,
            "ema": ema_data,
            "bollinger": bb_data,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "timeframe": timeframe,
            "stop_loss": sl,
            "target1": t1, "target2": t2, "target3": t3, "target4": t4,
            "macro_target": macro_t,
            "wyckoff": wyckoff_data,
            "confluence": notes,
            "extra": extra_analysis,
        })
        if score_state is not None: 
            add_points(score_state, symbol, "bullish", WEIGHTS.get("base_signal", 1.0) * tf_weight_multiplier, f"ارتداد من دعم ({timeframe})")

    return signals

# ============ شجرة الأولويات وتصنيف الخطط الـ 7 (آمنة تماماً) ============
def classify_and_format_signal(sig: dict, macro_info: dict, fng_status: dict = None) -> tuple[str, str]:
    """
    تصنيف التنبيه وفق شجرة الشروط الحصرية - النسخة الآمنة من الرموز المعقدة
    """
    wyckoff = sig.get("wyckoff", {})
    confluence = sig.get("confluence", [])
    extra = sig.get("extra", {})
    ema = sig.get("ema", {})
    bb = sig.get("bollinger", {})
    
    symbol = sig["symbol"]
    tf = sig.get("timeframe", "1h").upper()
    price = sig["price"]
    sl = sig["stop_loss"]
    t1, t2, t3, t4, macro_t = sig["target1"], sig["target2"], sig["target3"], sig["target4"], sig["macro_target"]
    
    macro_bullish = macro_info.get("macro_bullish")
    macro_status = "صاعد" if macro_bullish else "محايد/هابط"
    macro_str = f"3D RSI: <code>{macro_info.get('d3_rsi', 0):.1f}</code> | 1W RSI: <code>{macro_info.get('w1_rsi', 0):.1f}</code> | الاتجاه: {macro_status}"

    confidence_score = sig.get("stars", "عالي")

    # الخطة 7: التوصية الشاملة (Ultimate Master Signal)
    if len(confluence) >= 4 and macro_bullish:
        msg = (
            f"❖ <b>توصية فائقة القوة | Ultimate Master Confluence</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf} + (3D/1W Macro)</code>\n"
            f"🌐 <b>الماكرو:</b> {macro_str}\n\n"
            f"◈ <b>سعر الدخول:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>وقف الخسارة:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>هدف 1:</b> <code>{t1}$</code>\n"
            f"▸ <b>هدف 2:</b> <code>{t2}$</code>\n"
            f"▸ <b>هدف 3:</b> <code>{t3}$</code>\n"
            f"▸ <b>هدف 4:</b> <code>{t4}$</code>\n"
            f"✦ <b>الهدف البعيد (Macro Fib):</b> <code>{macro_t}$</code>\n\n"
            f"📊 <b>التوافق الفني الشامل:</b>\n• " + "\n• ".join(confluence) +
            f"\n\n🧠 <b>المشاعر العامة:</b> {fng_status.get('value', 'N/A') if fng_status else 'N/A'}"
        )
        return "MASTER_SIGNAL", msg

    # الخطة 1: صفقة التجميع المؤسساتي (Wyckoff + SMC)
    if wyckoff.get("is_wyckoff_setup") or ("سحب سيولة (Liquidity Sweep)" in confluence and "قرب Order Block" in confluence):
        phase_str = wyckoff.get('wyckoff_phase', 'تجميع SMC/Order Block')
        msg = (
            f"🏛 <b>توصية مؤسساتية | Smart Money Accumulation</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf}</code>\n"
            f"📍 <b>المرحلة:</b> {phase_str}\n"
            f"🌐 <b>بيانات الماكرو:</b> {macro_str}\n\n"
            f"◈ <b>سعر الدخول:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>وقف الخسارة المحكم:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>الهدف التكتيكي (1):</b> <code>{t1}$</code>\n"
            f"▸ <b>الهدف الهيكلي (2):</b> <code>{t2}$</code>\n"
            f"✦ <b>الهدف الماكرو (3):</b> <code>{macro_t}$</code>\n\n"
            f"📊 <b>الدمج الفني (Confluence):</b>\n• " + "\n• ".join(confluence)
        )
        return "WYCKOFF_SMC", msg

    # الخطة 2: صفقة الانفجار السعري (Volatile Breakout + CVD)
    if bb.get("is_squeeze") or "شمعة جهد وسيولة عالية (Volume Spike)" in confluence:
        msg = (
            f"⚡ <b>توصية اختراق وانفجار سعري | Volatile Breakout</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf}</code>\n"
            f"📍 <b>النموذج:</b> انكماش البولينجر (BB Squeeze) / شمعة سيولة عالية\n\n"
            f"◈ <b>سعر الدخول:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>وقف الخسارة:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>هدف سريع (1):</b> <code>{t1}$</code>\n"
            f"▸ <b>هدف الانفجار (2):</b> <code>{t2}$</code>\n"
            f"▸ <b>الهدف البعيد (3):</b> <code>{t3}$</code>\n\n"
            f"📊 <b>الدمج الفني (Confluence):</b>\n• " + "\n• ".join(confluence)
        )
        return "VOLATILE_BREAKOUT", msg

    # الخطة 3: صفقة الاتجاه العام والتقاطع الذهبي (Trend Following)
    if ema.get("golden_cross") or (ema.get("above_ema50") and ema.get("above_ema200")):
        d3_sup = macro_info.get('d3_support', 0)
        msg = (
            f"▲ <b>توصية ركوب الموجة | Trend Following</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf}</code>\n"
            f"📍 <b>النوع:</b> اتجاه صاعد قوي (EMA Golden Cross / Bullish Trend)\n"
            f"🌐 <b>دعم 3D الماكرو:</b> <code>{d3_sup:.4f}$</code>\n\n"
            f"◈ <b>مناطق الشراء:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>وقف الخسارة:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>هدف أول:</b> <code>{t1}$</code>\n"
            f"▸ <b>هدف ثاني:</b> <code>{t2}$</code>\n"
            f"✦ <b>هدف ماكرو:</b> <code>{macro_t}$</code>\n\n"
            f"📊 <b>الدمج الفني (Confluence):</b>\n• " + "\n• ".join(confluence)
        )
        return "GOLDEN_TREND", msg

    # الخطة 5: أنماط التشارت الكلاسيكية (Chart Patterns)
    if any("نمط تشارت" in c for c in confluence) or extra.get("chart_patterns"):
        msg = (
            f"📐 <b>توصية نموذج كلاسيكي | Chart Pattern Setup</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf}</code>\n"
            f"📍 <b>النموذج المكتشف:</b> نمط تشارت كلاسيكي مدمج\n\n"
            f"◈ <b>سعر الاختراق:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>وقف الخسارة:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>هدف النموذج:</b> <code>{t1}$</code>\n"
            f"▸ <b>امتداد الهدف:</b> <code>{t2}$</code>\n\n"
            f"📊 <b>الدمج الفني (Confluence):</b>\n• " + "\n• ".join(confluence)
        )
        return "CHART_PATTERN", msg

    # الخطة 4: صفقة صيد القيعان والارتداد (Mean Reversion)
    if bb.get("is_oversold_bb") or any("دايفرجنس" in c for c in confluence):
        msg = (
            f"🔄 <b>توصية ارتداد وصيد قاع | Mean Reversion</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf}</code>\n"
            f"📍 <b>النموذج:</b> تشبع بيعي + Bullish Divergence\n\n"
            f"◈ <b>سعر الشراء:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>وقف الخسارة:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>هدف 1 (الارتداد الأول):</b> <code>{t1}$</code>\n"
            f"▸ <b>هدف 2 (الدعم السابق):</b> <code>{t2}$</code>\n\n"
            f"📊 <b>الدمج الفني (Confluence):</b>\n• " + "\n• ".join(confluence)
        )
        return "OVERSOLD_REVERSAL", msg

    # الخطة 6: صفقة صيد الفجوات السريعة (SMC Gap Scalp)
    if any("وجود FVG" in c for c in confluence):
        msg = (
            f"◈ <b>توصية FVG سريعة | Fair Value Gap Fill</b> [{confidence_score}]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>العملة:</b> <code>{symbol}</code> | <b>الفريم:</b> <code>{tf}</code>\n"
            f"📍 <b>الهدف:</b> إغلاق الفجوة السعرية (Imbalance Fill)\n\n"
            f"◈ <b>منطقة الشراء:</b> <code>{price:.4f}$</code>\n"
            f"🛑 <b>الستوب:</b> <code>{sl}$</code>\n\n"
            f"▸ <b>هدف إغلاق الفجوة:</b> <code>{t1}$</code>\n"
            f"▸ <b>هدف سحب السيولة:</b> <code>{t2}$</code>\n\n"
            f"📊 <b>الدمج الفني (Confluence):</b>\n• " + "\n• ".join(confluence)
        )
        return "FVG_SCALP", msg

    # تنبيه قياسي
    return "STANDARD", f"◈ <b>تنبيه حركة سعرية:</b> {symbol} على فريم {tf} بسعر {price:.4f}$"

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

# ============ التشغيل الرئيسي ============
def main():
    print(f"بدء فحص العملات لعدد {len(WATCHLIST)} عملة عبر الفريمات 1h, 4h, 1d, 3d, 1w...")
    score_state = load_score_state()
    clean_old_events(score_state)

    try:
        fng_status = get_fear_and_greed_index()
    except Exception:
        fng_status = None

    def process_worker(sym):
        symbol_signals = []
        macro_info = analyze_macro_trends(sym)

        for tf in ["1h", "4h", "1d", "3d"]:
            df = fetch_klines(sym, timeframe=tf)
            if df is None:
                continue
            try:
                sigs = analyze_symbol(sym, df, timeframe=tf, score_state=score_state)
                for sig in sigs:
                    sig["macro_info"] = macro_info
                    symbol_signals.append(sig)
            except Exception as e:
                print(f"[خطأ تحليل] {sym} على فريم {tf}: {e}")

        return symbol_signals

    all_signals = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_worker, sym) for sym in WATCHLIST]
        for future in futures:
            signals = future.result()
            for sig in signals:
                symbol = sig["symbol"]
                macro_info = sig.get("macro_info", {})

                strategy_type, formatted_msg = classify_and_format_signal(sig, macro_info, fng_status)

                if should_alert(score_state, symbol, SCORE_THRESHOLD):
                    send_telegram_message(formatted_msg)
                    mark_alert_sent(score_state, symbol)

                all_signals.append(sig)

    save_score_state(score_state)
    print(f"انتهى الفحص بنجاح. تم اكتشاف {len(all_signals)} إشارة عبر جميع الفريمات المعتمدة.")

if __name__ == "__main__":
    main()

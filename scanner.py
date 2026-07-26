"""
ماسح العملات الحلال - السكربت الرئيسي الموحد (Binance + Modules Edition)
يقوم بجلب البيانات، الفحص الفني، إدارة نظام النقاط التراكمي،
حساب الأهداف الديناميكية (6 أهداف)، وتقييم SMC والماكرو مع التنبيهات الذكية.
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

# ============ جلب البيانات ============
def fetch_from_okx(symbol: str, timeframe: str) -> pd.DataFrame | None:
    clean_symbol = symbol.replace("/", "-").upper()
    if not clean_symbol.endswith("-USDT"):
        clean_symbol = f"{clean_symbol}-USDT"

    tf_map = {"1h": "1H", "4h": "4H", "1d": "1D"}
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
    tf_map = {"1h": "60", "4h": "240", "1d": "D"}
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
    tf_map = {"1h": "60m", "4h": "4h", "1d": "1D"}
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
    df = fetch_from_okx(symbol, timeframe)
    if df is not None: return df
    df = fetch_from_bybit(symbol, timeframe)
    if df is not None: return df
    df = fetch_from_mexc(symbol, timeframe)
    if df is not None: return df
    print(f"[خطأ] فشل جلب بيانات {symbol} من المنصات")
    return None

# ============ أدوات التحليل الفني ============
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

def detect_wyckoff_bull_market(df: pd.DataFrame, ms: dict, is_sweep: bool, is_effort: bool, bull_ob: dict) -> dict:
    wyckoff_result = {"is_bull_market": False, "wyckoff_phase": None, "is_wyckoff_setup": False}
    if len(df) < 50: return wyckoff_result

    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=min(len(df), 200), adjust=False).mean()

    last_ema50, last_ema200, last_close = df['ema_50'].iloc[-1], df['ema_200'].iloc[-1], df['close'].iloc[-1]

    if last_close > last_ema50 and last_ema50 > last_ema200:
        wyckoff_result["is_bull_market"] = True

    if is_sweep and bull_ob:
        wyckoff_result["wyckoff_phase"] = "Phase C (Spring - تجميع وسحب سيولة)"
        wyckoff_result["is_wyckoff_setup"] = True
    elif ms.get("bos_bullish") and is_effort:
        wyckoff_result["wyckoff_phase"] = "Phase D (SOS - علامة قوة واختراق)"
        wyckoff_result["is_wyckoff_setup"] = True
    elif wyckoff_result["is_bull_market"] and bull_ob and ms.get("choch_bullish"):
        wyckoff_result["wyckoff_phase"] = "Phase E (LPS - إعادة اختبار الدعم)"
        wyckoff_result["is_wyckoff_setup"] = True

    return wyckoff_result

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
def analyze_symbol(symbol: str, df: pd.DataFrame, score_state: dict = None) -> list[dict]:
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

    wyckoff_data = detect_wyckoff_bull_market(closed_df, ms, is_sweep, is_effort_candle, bull_ob)

    def confluence_note() -> list[str]:
        notes = []
        if has_bullish_pattern: notes.append("نمط شمعة صعودي")
        if near_bull_ob: notes.append("قرب Order Block")
        if fvg: notes.append(f"وجود FVG ({fvg['size_pct']:.2f}%)")
        if is_sweep: notes.append("سحب سيولة (Liquidity Sweep)")
        if is_bos: notes.append("كسر هيكل صعودي (BOS ⚡)")
        if is_choch: notes.append("تغير اتجاه صعودي (CHoCH 🔄)")
        if is_effort_candle: notes.append("شمعة جهد وسيولة عالية (Volume Spike 📊)")

        # إضافة الدايفرجنس صراحة إلى الرسالة
        div_data = extra_analysis.get("divergence")
        if div_data and isinstance(div_data, dict) and div_data.get("bullish"):
            notes.append(f"دايفرجنس صعودي ({div_data.get('type', 'إيجابي')} 📈)")

        # إضافة أنماط التشارت صراحة إلى الرسالة
        cp_data = extra_analysis.get("chart_patterns")
        if cp_data:
            if isinstance(cp_data, dict) and cp_data.get("pattern"):
                notes.append(f"نمط تشارت: {cp_data['pattern']} 📐")
            elif isinstance(cp_data, list) and len(cp_data) > 0:
                p_names = [p.get("pattern", "") if isinstance(p, dict) else str(p) for p in cp_data]
                notes.append(f"أنماط تشارت: {', '.join(p_names)} 📐")

        return notes

    # 1. اختراق مقاومة
    if last_close > resistance and last_volume > avg_vol * VOLUME_MULTIPLIER:
        notes = confluence_note()
        sl, t1, t2, t3, t4, macro_t = calculate_dynamic_targets(last_close, atr, resistance, fvg, ms, extra_analysis, candle_patterns)
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
            "timeframe": TIMEFRAME,
            "stop_loss": sl,
            "target1": t1, "target2": t2, "target3": t3, "target4": t4,
            "macro_target": macro_t,
            "wyckoff": wyckoff_data,
            "confluence": notes,
            "extra": extra_analysis,
        })
        if score_state is not None: 
            add_points(score_state, symbol, "bullish", WEIGHTS.get("base_signal", 1.0), "اختراق مقاومة")

    # 2. ارتداد من دعم
    is_bullish_candle = last_close > float(last_row["open"])
    near_support = float(last_row["low"]) <= support * (1 + SUPPORT_TOLERANCE)

    if near_support and is_bullish_candle and last_rsi < RSI_OVERSOLD:
        notes = confluence_note()
        sl, t1, t2, t3, t4, macro_t = calculate_dynamic_targets(last_close, atr, support, fvg, ms, extra_analysis, candle_patterns)
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
            "timeframe": TIMEFRAME,
            "stop_loss": sl,
            "target1": t1, "target2": t2, "target3": t3, "target4": t4,
            "macro_target": macro_t,
            "wyckoff": wyckoff_data,
            "confluence": notes,
            "extra": extra_analysis,
        })
        if score_state is not None: 
            add_points(score_state, symbol, "bullish", WEIGHTS.get("base_signal", 1.0), "ارتداد من دعم")

    return signals

# ============ قوالب التلجرام المنفصلة ============
def format_wyckoff_message(sig: dict, fng: dict = None) -> str:
    """قالب استراتيجي كبيـر لفرص وايكوف والاهداف الممتدة والبعيدة"""
    wyckoff_info = sig.get("wyckoff", {})
    lines = [
        f"🏛️🔥 <b>فرصة استراتيجية (نموذج وايكوف)</b> [{sig.get('stars', '⭐⭐⭐⭐⭐')}]",
        f"<b>العملة:</b> <code>{sig['symbol']}</code> | <b>الفريم:</b> <code>{sig.get('timeframe', '1H').upper()}</code>",
        f"📍 <b>مرحلة التجميع:</b> {wyckoff_info.get('wyckoff_phase')}",
        f"<b>السعر الحالي:</b> <code>{sig['price']:.4f}$</code>\n",
        f"🛑 <b>وقف الخسارة:</b> <code>{sig['stop_loss']}$</code>\n",
        "🔹 <b>الأهداف التكتيكية:</b>",
        f"• <b>هدف 1:</b> <code>{sig['target1']}$</code> 🎯",
        f"• <b>هدف 2:</b> <code>{sig['target2']}$</code> 🎯\n",
        "🚀 <b>الخطة الممتدة والبعيدة:</b>",
        f"• <b>هدف 3:</b> <code>{sig['target3']}$</code> 🔥",
        f"• <b>هدف 4:</b> <code>{sig['target4']}$</code> 💎",
        f"🔮 <b>الهدف البعيد (Macro Target):</b> <code>{sig['macro_target']}$</code> 🌌",
    ]
    if fng:
        lines.append(f"\n🧠 <b>مؤشر المشاعر العام:</b> {fng['value']} ({fng['status']})")
    if sig.get("confluence"):
        lines.append("\n✅ <b>التأكيدات والأنماط:</b> " + "، ".join(sig["confluence"]))
    return "\n".join(lines)

def format_score_message(sig: dict, score: float, breakdown: str) -> str:
    """قالب التنبيه التراكمي (عند تجاوز نقاط العملة للعتبة لتجنب التكرار)"""
    lines = [
        f"⚡ <b>تنبيه زخم تراكمي مرتفع (Score Alert)</b>",
        f"<b>العملة:</b> <code>{sig['symbol']}</code>",
        f"📊 <b>مجموع النقاط:</b> <code>{score:.1f} pts</code>",
        f"<b>السعر الحالي:</b> <code>{sig['price']:.4f}$</code>\n",
        f"🛑 <b>الستوب:</b> <code>{sig['stop_loss']}$</code> | 🎯 <b>الهدف الأول:</b> <code>{sig['target1']}$</code> | 🎯 <b>الهدف الثاني:</b> <code>{sig['target2']}$</code>",
    ]
    if sig.get("confluence"):
        lines.append("\n✅ <b>التأكيدات والأنماط:</b> " + "، ".join(sig["confluence"]))
    if breakdown:
        lines.append(f"\n📝 <b>تفاصيل النقاط:</b>\n{breakdown}")
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

# ============ التشغيل الرئيسي ============
def main():
    print(f"بدء فحص العملات لعدد {len(WATCHLIST)} عملة...")
    all_signals_for_app = []
    score_state = load_score_state()

    # تنظيف الأحداث القديمة في نظام النقاط
    clean_old_events(score_state)

    try:
        fng_status = get_fear_and_greed_index()
    except Exception:
        fng_status = None

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
                symbol = sig["symbol"]
                wyckoff_info = sig.get("wyckoff", {})

                # 1. نمط تنبيه وايكوف الاستراتيجي (يرسل فوراً)
                if wyckoff_info and wyckoff_info.get("is_wyckoff_setup"):
                    msg = format_wyckoff_message(sig, fng=fng_status)
                    send_telegram_message(msg)
                    all_signals_for_app.append(sig)
                    continue

                # 2. نمط التنبيه التراكمي (مع فلتر منع التكرار)
                score = current_score(score_state, symbol)
                if should_alert(score_state, symbol, SCORE_THRESHOLD):
                    breakdown = get_score_breakdown(score_state, symbol)
                    msg = format_score_message(sig, score, breakdown)
                    send_telegram_message(msg)
                    
                    # كتم العملة مؤقتاً بعد الإرسال
                    mark_alert_sent(score_state, symbol)
                
                all_signals_for_app.append(sig)

    save_score_state(score_state)
    print(f"انتهى الفحص بنجاح. تم اكتشاف {len(all_signals_for_app)} إشارة.")

if __name__ == "__main__":
    main()

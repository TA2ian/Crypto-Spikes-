"""
ماسح العملات الحلال - السكربت الرئيسي الموحد المحسّن
(Multi-Timeframe Edition: 15m, 1h, 4h, 1d, 3d, 1w)
مدعوم بنظام تثبيت الأهداف الهيكلية، تتبع إعادة الدخول، وآلة الحالات الـ 11 للخطط الـ 8.
"""
import os
import time
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import requests
import pandas as pd

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ============ استدعاء وحدات إدارة التنبيهات والصفقات ============
from alert_manager import AlertManager
from trade_manager import TradeManager

# ============ Sprint 008-E: V2 Shadow Integration ============
# V2 runs beside the legacy scanner in SHADOW mode.
# It must never interrupt legacy scanning or open an exchange trade.
try:
    from scanner_shadow import (
        ScannerShadowBridge,
        compare_legacy_and_v2,
    )
except ImportError:
    ScannerShadowBridge = None
    compare_legacy_and_v2 = None

# ============ Sprint 008-G: Shadow Outcome Integration ============
# Accepted V2 shadow signals are registered as hypothetical outcomes.
# This layer is observation-only and MUST NOT execute trades.
try:
    from shadow_outcome_integration import ShadowOutcomeIntegration
except ImportError:
    ShadowOutcomeIntegration = None

# تهيئة مدير التنبيهات وإدارة الصفقات
alert_manager = AlertManager(max_active_alerts=20)
trade_manager = TradeManager(alert_manager=alert_manager, account_balance=1000.0, risk_per_trade_pct=1.0)

# استدعاء الملفات الأساسية
from coins import WATCHLIST

# V2 Shadow Bridge is optional at import time so the legacy scanner
# remains operational if the V2 integration module is temporarily absent.
shadow_bridge = (
    ScannerShadowBridge(watchlist=WATCHLIST)
    if ScannerShadowBridge is not None
    else None
)

shadow_outcome_tracker = (
    ShadowOutcomeIntegration()
    if ShadowOutcomeIntegration is not None
    else None
)

from indicators import calc_rsi, find_support_resistance, avg_volume
from patterns import (
    detect_candle_patterns,
    find_bullish_order_block,
    find_bearish_order_block,
    price_near_zone,
)
from divergence import analyze_divergence
from fibonacci import analyze_fibonacci
from dominance_analyzer import analyze_market_dominance

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
    from models.smc import (
        detect_fvg,
        detect_liquidity_sweep,
    )
    from models.sentiment import (
        get_fear_and_greed_index,
    )
    from models.dynamic_risk import (
        calculate_atr,
        rate_signal_confidence,
    )
except ImportError as exc:
    raise ImportError(
        "Failed to import scanner model modules from "
        "'models'. Expected files: "
        "models/smc.py, models/sentiment.py, "
        "models/dynamic_risk.py"
    ) from exc

# ============ الإعدادات والأطر الزمنية ============
ACTIVE_TIMEFRAMES = ["15m", "1h", "4h", "1d", "3d", "1w"]
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

# ============ ذاكرة تتبع الصفقات النشطة (تثبيت الأهداف ومنع التزحزح) ============
ACTIVE_SIGNALS_STATE = {}
MEMORY_EXPIRY_HOURS = 24

# ============ أسماء الخطط الـ 8 لتجميع التنبيهات ============
STRATEGY_NAMES = {
    "WYCKOFF_SMC_ACCUMULATION": "🏛️ التجميع المؤسساتي (Wyckoff + SMC)",
    "CVD_BREAKOUT_CONFIRMED": "🚀 اختراق مدعوم بـ CVD & Squeeze",
    "TREND_FOLLOWING_4_CONFIRMS": "📈 تتبع الاتجاه المؤكد (4 شروط)",
    "MEAN_REVERSION_4_CONFIRMS": "🎯 صيد القيعان والارتداد (Mean Reversion)",
    "CHART_PATTERN_4_CONFIRMS": "📐 النمط الكلاسيكي المؤكد",
    "FVG_SCALP_4_CONFIRMS": "🕳️ صيد الفجوات المؤسساتية (FVG)",
    "ULTIMATE_MASTER_A_PLUS": "👑 التوصية الشاملة الفائقة (A+)",
    "CAPITULATION_RE_ENTRY": "🩸 قاع الاستسلام والرعب (Capitulation)",
    "BEARISH_RISK": "🚨 تحذيرات الهبوط وكسر الدعوم",
    "STANDARD": "◈ حركات سعرية اعتيادية"
}

# ============ جلب البيانات من المنصات ============
def fetch_from_okx(symbol: str, timeframe: str) -> pd.DataFrame | None:
    clean_symbol = symbol.replace("/", "-").upper()
    if not clean_symbol.endswith("-USDT"):
        clean_symbol = f"{clean_symbol}-USDT"

    tf_map = {"15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D", "3d": "3D", "1w": "1W"}
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
    tf_map = {"15m": "15", "1h": "60", "4h": "240", "1d": "D", "3d": "3D", "1w": "W"}
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
    tf_map = {"15m": "15m", "1h": "60m", "4h": "4h", "1d": "1D", "3d": "3D", "1w": "1W"}
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
    if len(df) < window: return {}
    
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
    if len(df) < 50: return {}
    
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

def calculate_market_pressure(df: pd.DataFrame, length: int = 13) -> dict:
    if len(df) < length + 5:
        return {"value": 50.0, "status": "balanced", "display": "N/A"}
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    
    rs = gain / (loss + 1e-9)
    oscillator = 100 - (100 / (1 + rs))
    smoothed_osc = oscillator.ewm(span=length, adjust=False).mean()
    last_val = float(smoothed_osc.iloc[-1])
    
    if last_val >= 75:
        status = "overbought"
        display_str = f"[bold red]▲ [OVERBOUGHT RISK] ({last_val:.1f})[/bold red]"
    elif last_val <= 25:
        status = "oversold"
        display_str = f"[bold green]▼ [OVERSOLD OPPORTUNITY] ({last_val:.1f})[/bold green]"
    else:
        status = "balanced"
        display_str = f"[yellow]◆ [BALANCED] ({last_val:.1f})[/yellow]"
        
    return {"value": last_val, "status": status, "display": display_str}

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

    if not pivot_highs.empty: result["last_high"] = float(pivot_highs.iloc[-1])
    if not pivot_lows.empty: result["last_low"] = float(pivot_lows.iloc[-1])

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
        wyckoff_result["wyckoff_phase"] = "Phase D (SOS - علامة قوة واختراق)"
        wyckoff_result["is_wyckoff_setup"] = True
    elif wyckoff_result["is_bull_market"] and bull_ob and ms.get("choch_bullish"):
        wyckoff_result["wyckoff_phase"] = "Phase E (LPS - إعادة اختبار الدعم)"
        wyckoff_result["is_wyckoff_setup"] = True

    return wyckoff_result

# ============ حساب الأهداف الهيكلية الثابتة ============
def calculate_fixed_targets(entry_price: float, atr: float, resistance: float, fvg: dict, ms: dict, extra_analysis: dict, candle_patterns: list) -> tuple:
    stop_loss = entry_price - (atr * 1.5)

    pattern_target = 0
    if candle_patterns and isinstance(candle_patterns[0], dict):
        p = candle_patterns[0]
        if "high" in p and "low" in p:
            pattern_target = entry_price + (p["high"] - p["low"])

    if pattern_target > entry_price * 1.01:
        target1 = pattern_target
    elif resistance > entry_price * 1.01:
        target1 = resistance
    else:
        target1 = entry_price + (atr * 1.5)

    fib_data = extra_analysis.get("fibonacci", {}) if isinstance(extra_analysis.get("fibonacci"), dict) else {}
    fib_1618 = fib_data.get("ext_1618", 0)

    fvg_top = fvg.get("top", 0) if fvg else 0
    target2 = fvg_top if fvg_top > target1 else target1 + (atr * 1.5)
    
    last_high = ms.get("last_high")
    if last_high and last_high > target2:
        target3 = last_high
    elif fib_1618 > target2:
        target3 = fib_1618
    else:
        target3 = target2 + (atr * 2.0)

    fib_2618 = fib_data.get("ext_2618", 0)
    target4 = fib_2618 if fib_2618 > target3 else target3 + (atr * 3.0)

    fib_3618 = fib_data.get("ext_3618", 0)
    macro_target = fib_3618 if fib_3618 > target4 else entry_price + (atr * 6.0)

    t1 = round(target1, 4)
    t2 = round(max(target2, t1 * 1.015), 4)
    t3 = round(max(target3, t2 * 1.02), 4)
    t4 = round(max(target4, t3 * 1.025), 4)
    macro_t = round(max(macro_target, t4 * 1.05), 4)
    sl = round(stop_loss, 4)

    return sl, t1, t2, t3, t4, macro_t

# ============ لمعالجة حالة الذاكرة ومنع تزحزح الأهداف ============
def process_signal_memory(sig: dict) -> dict:
    tracking_key = f"{sig['symbol']}_{sig['timeframe']}"
    current_price = sig['price']
    now = time.time()
    
    # تنظيف الذاكرة المتقادمة
    expired_keys = [k for k, v in ACTIVE_SIGNALS_STATE.items() if (now - v['timestamp']) > (MEMORY_EXPIRY_HOURS * 3600)]
    for k in expired_keys:
        del ACTIVE_SIGNALS_STATE[k]

    if tracking_key in ACTIVE_SIGNALS_STATE:
        state = ACTIVE_SIGNALS_STATE[tracking_key]
        initial_entry = state['initial_entry']
        price_change_pct = abs(current_price - initial_entry) / initial_entry
        
        if price_change_pct <= 0.015:
            sig['signal_status'] = "🔄 إعادة دخول (Retest / Re-entry)"
            sig['is_reentry'] = True
            sig['current_stage'] = "RETEST_ENTRY"
        else:
            sig['signal_status'] = "📌 متابعة صفقة قائمة (Continuation)"
            sig['is_reentry'] = False
            sig['current_stage'] = "ACTIVE"

        sig['price_entry_original'] = initial_entry
        sig['stop_loss'] = state['stop_loss']
        sig['target1'] = state['target1']
        sig['target2'] = state['target2']
        sig['target3'] = state['target3']
        sig['target4'] = state['target4']
        sig['macro_target'] = state['macro_target']
    else:
        sig['signal_status'] = "🟢 دخول أول (Initial Entry)"
        sig['is_reentry'] = False
        sig['current_stage'] = "FIRST_ENTRY"
        sig['price_entry_original'] = current_price
        
        ACTIVE_SIGNALS_STATE[tracking_key] = {
            "initial_entry": current_price,
            "stop_loss": sig['stop_loss'],
            "target1": sig['target1'],
            "target2": sig['target2'],
            "target3": sig['target3'],
            "target4": sig['target4'],
            "macro_target": sig['macro_target'],
            "timestamp": now
        }
        
    return sig

# ============ رصد تحذيرات الهبوط والمخاطر ============
def analyze_bearish_signals(symbol: str, df: pd.DataFrame, timeframe: str) -> list[dict]:
    bearish_signals = []
    if df is None or len(df) < 30: return bearish_signals

    closed_df = df.iloc[:-1]
    last_row = closed_df.iloc[-1]
    last_close = float(last_row["close"])
    last_volume = float(last_row["volume"])

    support, resistance = find_support_resistance(closed_df, RESISTANCE_LOOKBACK)
    avg_vol = avg_volume(closed_df, 20)
    rsi = calc_rsi(closed_df["close"], 14)
    last_rsi = float(rsi.iloc[-1])

    is_support_broken = last_close < support and last_volume > avg_vol * 1.5
    is_overbought_warning = last_rsi >= 78

    if is_support_broken:
        bearish_signals.append({
            "type": "كسر دعم خطير",
            "symbol": symbol,
            "price": last_close,
            "level": support,
            "timeframe": timeframe,
            "strategy": "BEARISH_RISK",
            "current_stage": "BEARISH_BREAKOUT",
            "message": f"🔴 **تنبيه انهيار دعم:** العملة `{symbol}` كسرت دعم الأمان عند **{support:.4f}$** على فريم `{timeframe.upper()}` مع فوليوم بيع مكثف!"
        })
    elif is_overbought_warning:
        bearish_signals.append({
            "type": "تحذير تشبع شرائي",
            "symbol": symbol,
            "price": last_close,
            "level": resistance,
            "timeframe": timeframe,
            "strategy": "BEARISH_RISK",
            "current_stage": "OVERBOUGHT_RISK",
            "message": f"⚠️ **تحذير تشبع شرائي وقرب انعكاس:** العملة `{symbol}` وصلت لمنطقة تشبع مفرط (RSI: `{last_rsi:.1f}`) بالقرب من المقاومة **{resistance:.4f}$**."
        })

    return bearish_signals

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
        ema20_3d = float(c_3d["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        macro_data["d3_rsi"] = float(calc_rsi(c_3d["close"], 14).iloc[-1])
        s_supp, s_res = find_support_resistance(c_3d, 10)
        macro_data["d3_support"], macro_data["d3_resistance"] = float(s_supp), float(s_res)
        d3_bullish = last_3d_close > ema20_3d and macro_data["d3_rsi"] > 45
    else:
        d3_bullish = False

    if df_1w is not None and len(df_1w) >= 20:
        c_1w = df_1w.iloc[:-1]
        last_1w_close = float(c_1w["close"].iloc[-1])
        ema20_1w = float(c_1w["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        macro_data["w1_rsi"] = float(calc_rsi(c_1w["close"], 14).iloc[-1])
        w_supp, w_res = find_support_resistance(c_1w, 10)
        macro_data["w1_support"], macro_data["w1_resistance"] = float(w_supp), float(w_res)
        w1_bullish = last_1w_close > ema20_1w and macro_data["w1_rsi"] > 45
    else:
        w1_bullish = False

    macro_data["macro_bullish"] = bool(d3_bullish or w1_bullish)
    return macro_data

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
    dpr_data = calculate_market_pressure(closed_df, length=13)

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

        if dpr_data["status"] == "oversold":
            notes.append("مؤشر DPR تحت النطاق 25 (فرصة تشبع بيعي)")
        elif dpr_data["status"] == "overbought":
            notes.append("مؤشر DPR فوق النطاق 75 (هيمنة ضغط الشراء)")

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
    if timeframe == "15m": tf_weight_multiplier = 0.8
    elif timeframe == "4h": tf_weight_multiplier = 1.3
    elif timeframe == "1d": tf_weight_multiplier = 1.8
    elif timeframe == "3d": tf_weight_multiplier = 2.2
    elif timeframe == "1w": tf_weight_multiplier = 2.8

    tracking_key = f"{symbol}_{timeframe}"

    # 1. اختراق مقاومة
    if last_close > resistance and last_volume > avg_vol * VOLUME_MULTIPLIER:
        notes = confluence_note()
        sl, t1, t2, t3, t4, macro_t = calculate_fixed_targets(last_close, atr, resistance, fvg, ms, extra_analysis, candle_patterns)
        stars = rate_signal_confidence(bool(notes), fvg, is_sweep)

        raw_sig = {
            "type": "اختراق مقاومة",
            "stars": stars,
            "symbol": symbol,
            "price": last_close,
            "level": resistance,
            "rsi": last_rsi,
            "ema": ema_data,
            "bollinger": bb_data,
            "dpr_data": dpr_data,
            "volume_ratio": float(last_volume / avg_vol) if avg_vol else 0.0,
            "timeframe": timeframe,
            "stop_loss": sl,
            "target1": t1, "target2": t2, "target3": t3, "target4": t4,
            "macro_target": macro_t,
            "wyckoff": wyckoff_data,
            "confluence": notes,
            "extra": extra_analysis,
        }
        processed_sig = process_signal_memory(raw_sig)
        signals.append(processed_sig)
        if score_state is not None: 
            add_points(score_state, tracking_key, "bullish", WEIGHTS.get("base_signal", 1.0) * tf_weight_multiplier, f"اختراق مقاومة ({timeframe})")

    # 2. ارتداد من دعم
    is_bullish_candle = last_close > float(last_row["open"])
    near_support = float(last_row["low"]) <= support * (1 + SUPPORT_TOLERANCE)

    if near_support and is_bullish_candle and last_rsi < RSI_OVERSOLD:
        notes = confluence_note()
        sl, t1, t2, t3, t4, macro_t = calculate_fixed_targets(last_close, atr, support, fvg, ms, extra_analysis, candle_patterns)
        stars = rate_signal_confidence(bool(notes), fvg, is_sweep)

        raw_sig = {
            "type": "ارتداد من دعم",
            "stars": stars,
            "symbol": symbol,
            "price": last_close,
            "level": support,
            "rsi": last_rsi,
            "ema": ema_data,
            "bollinger": bb_data,
            "dpr_data": dpr_data,
            "volume_ratio": float(last_volume / avg_vol) if avg_vol else 0.0,
            "timeframe": timeframe,
            "stop_loss": sl,
            "target1": t1, "target2": t2, "target3": t3, "target4": t4,
            "macro_target": macro_t,
            "wyckoff": wyckoff_data,
            "confluence": notes,
            "extra": extra_analysis,
        }
        processed_sig = process_signal_memory(raw_sig)
        signals.append(processed_sig)
        if score_state is not None: 
            add_points(score_state, tracking_key, "bullish", WEIGHTS.get("base_signal", 1.0) * tf_weight_multiplier, f"ارتداد من دعم ({timeframe})")

    return signals

# ============ شجرة الأولويات وتصنيف الخطط الـ 8 المطورة ============
def classify_and_format_signal(sig: dict, macro_info: dict, fng_status: dict = None) -> tuple[str, str]:
    wyckoff = sig.get("wyckoff", {})
    confluence = sig.get("confluence", [])
    extra = sig.get("extra", {})
    ema = sig.get("ema", {})
    bb = sig.get("bollinger", {})
    dpr_info = sig.get("dpr_data", {"value": 50.0, "status": "balanced"})
    
    symbol = sig["symbol"]
    tf = sig.get("timeframe", "1h").upper()
    price = sig["price"]
    orig_entry = sig.get("price_entry_original", price)
    status_tag = sig.get("signal_status", "🟢 دخول جديد")

    sl = sig["stop_loss"]
    t1, t2, t3, t4, macro_t = sig["target1"], sig["target2"], sig["target3"], sig["target4"], sig["macro_target"]
    rsi = sig["rsi"]
    
    macro_bullish = macro_info.get("macro_bullish")
    confidence_score = sig.get("stars", "عالي")

    entry_str = f"[bold green]{price:.4f}$[/bold green]"
    if orig_entry != price:
        entry_str += f" [dim](سعر الدخول الأصلي: {orig_entry:.4f}$)[/dim]"

    is_wyckoff_setup = wyckoff.get("is_wyckoff_setup") or ("سحب سيولة (Liquidity Sweep)" in confluence and "قرب Order Block" in confluence)
    if is_wyckoff_setup:
        msg = (
            f"[bold magenta]🏛️ {status_tag} | Wyckoff + SMC Accumulation[/bold magenta] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]النموذج الهيكلي:[/bold] سحب سيولة (Spring/Sweep) + كسر هيكل (BOS) مع منطقة طلب مؤسساتية\n\n"
            f"• [bold]منطقة الدخول:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الرئيسي (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]الهدف البعيد (Macro):[/bold] [bold green]{macro_t}$[/bold green]\n\n"
            f"[bold]📊 مؤشرات التأكيد المؤسساتي:[/bold]\n  [green]✔[/green] تحقق سحب السيولة وإلغاء فخ الدببة\n  [green]✔[/green] ارتداد دقيق من منطقة طلب معتمدة"
        )
        return "WYCKOFF_SMC_ACCUMULATION", msg

    is_breakout_cond = (bb.get("is_squeeze") or "شمعة جهد وسيولة عالية (Volume Spike)" in confluence) and (dpr_info["value"] >= 70 or sig.get("volume_ratio", 1.0) >= 1.5)
    if is_breakout_cond:
        msg = (
            f"[bold cyan]🚀 {status_tag} | CVD-Verified Breakout[/bold cyan] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]طبيعة الاختراق:[/bold] انكماش سُعري (BB Squeeze) + إغلاق قوي + شراء عدواني مفرط\n\n"
            f"• [bold]سعر الدخول:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الممتد (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]الهدف البعيد:[/bold] [bold green]{macro_t}$[/bold green]"
        )
        return "CVD_BREAKOUT_CONFIRMED", msg

    is_trend_cond = (ema.get("golden_cross") or (ema.get("above_ema50") and ema.get("above_ema200"))) and (50 <= dpr_info["value"] <= 75) and (50 <= rsi <= 75)
    if is_trend_cond:
        msg = (
            f"[bold blue]📈 {status_tag} | Precision Trend Following[/bold blue] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]هيكل الاتجاه:[/bold] ترتيب مثالي للمتوسطات + تقاطع ذهبي مدعوم\n\n"
            f"• [bold]سعر الدخول:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الاتجاهي (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]هدف ماكرو:[/bold] [bold green]{macro_t}$[/bold green]"
        )
        return "TREND_FOLLOWING_4_CONFIRMS", msg

    is_reversion_cond = bb.get("is_oversold_bb") or any("دايفرجنس" in c for c in confluence) or dpr_info["status"] == "oversold"
    if is_reversion_cond:
        msg = (
            f"[bold green]🎯 {status_tag} | Mean Reversion Setup[/bold green] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]نموذج الانعكاس:[/bold] تشبع بيعي (BB) + دايفرجنس صعودي + ارتداد تدفق السيولة\n\n"
            f"• [bold]سعر الدخول:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الرئيسي (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]الهدف البعيد:[/bold] [bold green]{macro_t}$[/bold green]"
        )
        return "MEAN_REVERSION_4_CONFIRMS", msg

    is_pattern_cond = any("نمط تشارت" in c for c in confluence) or extra.get("chart_patterns")
    if is_pattern_cond:
        msg = (
            f"[bold yellow]📐 {status_tag} | Verified Chart Pattern[/bold yellow] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]النموذج المرصود:[/bold] نمط تشارت كلاسيكي مدمج\n\n"
            f"• [bold]سعر الدخول:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الرئيسي (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]الهدف البعيد:[/bold] [bold green]{macro_t}$[/bold green]"
        )
        return "CHART_PATTERN_4_CONFIRMS", msg

    is_fvg_cond = any("وجود FVG" in c for c in confluence)
    if is_fvg_cond:
        msg = (
            f"[bold cyan]🕳️ {status_tag} | Verified FVG Scalp Setup[/bold cyan] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]هيكل الفجوة:[/bold] فجوة مؤسسية (FVG) متوافقة مع منطقة طلب\n\n"
            f"• [bold]سعر الدخول:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الممتد (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]الهدف البعيد:[/bold] [bold green]{macro_t}$[/bold green]"
        )
        return "FVG_SCALP_4_CONFIRMS", msg

    if len(confluence) >= 5 and macro_bullish:
        msg = (
            f"[bold gold1]👑 {status_tag} | Ultimate Master Signal [A+][/bold gold1]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]توافق الماكرو (3D/1W):[/bold] إيجابي ومؤكد صعودياً [green]🟢[/green]\n\n"
            f"• [bold]منطقة الدخول المثالية:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الثاني (T2):[/bold] [green]{t2}$[/green]\n"
            f"▸ [bold]الهدف الرئيسي (TP):[/bold] [green]{t3}$[/green]\n"
            f"✦ [bold]الهدف البعيد (Macro):[/bold] [bold green]{macro_t}$[/bold green]\n\n"
            f"[bold]📊 التأكيدات ({len(confluence)}/5+):[/bold]\n• " + "\n• ".join(confluence)
        )
        return "ULTIMATE_MASTER_A_PLUS", msg

    is_capitulation_cond = (rsi <= 22 or dpr_info["value"] <= 20) and any("ارتداد من دعم" in sig.get("type", "") or "تراجع" in c for c in confluence)
    if is_capitulation_cond:
        msg = (
            f"[bold red]🩸 {status_tag} | Capitulation Bottom Setup[/bold red] [[yellow]{confidence_score}[/yellow]]\n"
            f"────────────────────────────────────────\n"
            f"[bold]العملة:[/bold] [cyan]{symbol}[/cyan] | [bold]الفريم:[/bold] [yellow]{tf}[/yellow]\n"
            f"[bold]طبيعة القاع:[/bold] غياب فوليوم البيع والشراء (Dry-up) مع ذعر تشبع بيعي متطرف\n\n"
            f"• [bold]منطقة الشراء والتجميع:[/bold] {entry_str}\n"
            f"• [bold red]وقف الخسارة (الثابت):[/bold red] [bold]{sl}$[/bold]\n\n"
            f"▸ [bold]الهدف الأول (T1):[/bold] [green]{t1}$[/green]\n"
            f"▸ [bold]الهدف الرئيسي (T2):[/bold] [green]{t2}$[/green]\n"
            f"✦ [bold]الهدف البعيد:[/bold] [bold green]{macro_t}$[/bold green]"
        )
        return "CAPITULATION_RE_ENTRY", msg

    return "STANDARD", f"[bold]◈ {status_tag}:[/bold] [cyan]{symbol}[/cyan] على فريم [yellow]{tf}[/yellow] بسعر الدخول {entry_str}"

def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        console.print("[yellow][تنبيه][/yellow] لم يتم تعيين مفاتيح تيليغرام. طباعة الرسالة عبر rich:")
        console.print(Panel(text, title="Telegram Preview"))
        return

    clean_text = text
    for tag in ["[bold magenta]", "[/bold magenta]", "[bold cyan]", "[/bold cyan]", "[bold blue]", "[/bold blue]", 
                "[bold green]", "[/bold green]", "[bold red]", "[/bold red]", "[bold yellow]", "[/bold yellow]", 
                "[bold gold1]", "[/bold gold1]", "[bold]", "[/bold]", "[cyan]", "[/cyan]", "[yellow]", "[/yellow]", 
                "[green]", "[/green]", "[red]", "[/red]", "[dim]", "[/dim]"]:
        clean_text = clean_text.replace(tag, "")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": clean_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
    except Exception as e:
        console.print(f"[bold red][خطأ][/bold red] فشل إرسال رسالة تيليغرام: {e}")

# ============ بناء واجهة لوحة التنبيهات المجمعة (Grouped Alert Dashboard) ============
def render_grouped_alert_dashboard(grouped_signals: dict, all_bearish_alerts: list):
    console.print("\n")
    console.print(Panel.fit("[bold white on blue] 📊 لوحة التنبيهات المجمعة وحصيلة الصفقات والخطط الـ 8 [/bold white on blue]", style="bold cyan"))

    summary_table = Table(title="📈 ملخص إشارات الصفقات حسب الخطة الفنية", header_style="bold yellow", border_style="cyan")
    summary_table.add_column("رمز الخطة", style="dim", width=25)
    summary_table.add_column("اسم الخطة الفنية", style="bold white")
    summary_table.add_column("عدد التوصيات", justify="center", style="bold green")
    summary_table.add_column("العملات المرصودة", style="cyan")

    total_bullish = 0
    for strat_key, strat_name in STRATEGY_NAMES.items():
        if strat_key in ["BEARISH_RISK", "STANDARD"]:
            continue
        sigs = grouped_signals.get(strat_key, [])
        count = len(sigs)
        total_bullish += count
        coins_str = ", ".join(set([s["symbol"] for s in sigs])) if count > 0 else "-"
        
        summary_table.add_row(
            strat_key,
            strat_name,
            str(count) if count > 0 else "[dim]0[/dim]",
            coins_str
        )

    console.print(summary_table)

    if all_bearish_alerts:
        bearish_table = Table(title="🚨 لوحة تحذيرات الهبوط وكسر الدعوم", header_style="bold white on red", border_style="red")
        bearish_table.add_column("العملة", style="bold yellow")
        bearish_table.add_column("الفريم", justify="center", style="cyan")
        bearish_table.add_column("نوع التحذير", style="bold red")
        bearish_table.add_column("السعر الحالي", justify="right")
        bearish_table.add_column("مستوى الدعم/المقاومة", justify="right")

        for b in all_bearish_alerts:
            bearish_table.add_row(
                b["symbol"],
                b["timeframe"].upper(),
                b["type"],
                f"{b['price']:.4f}$",
                f"{b['level']:.4f}$"
            )
        console.print(bearish_table)
    else:
        console.print(Panel("[bold green]✔ لا توجد تحذيرات هبوط خطيرة أو كسر دعوم في هذه الجلسة.[/bold green]", border_style="green"))

    if total_bullish > 0:
        detail_table = Table(title="💎 تفاصيل الصفقات ونوع التنبيه (ثابت الأهداف)", header_style="bold blue", border_style="yellow")
        detail_table.add_column("العملة", style="bold cyan")
        detail_table.add_column("الفريم", justify="center", style="yellow")
        detail_table.add_column("حالة الدخول", style="bold white")
        detail_table.add_column("سعر الدخول", justify="right", style="green")
        detail_table.add_column("الستوب الثابت", justify="right", style="red")
        detail_table.add_column("الهدف (TP1)", justify="right", style="green")
        detail_table.add_column("الهدف البعيد", justify="right", style="bold green")

        for strat_key, sigs in grouped_signals.items():
            if strat_key in ["BEARISH_RISK", "STANDARD"]:
                continue
            for s in sigs:
                detail_table.add_row(
                    s["symbol"],
                    s.get("timeframe", "1H").upper(),
                    s.get("signal_status", "دخول أول"),
                    f"{s['price']:.4f}$",
                    f"{s['stop_loss']:.4f}$",
                    f"{s['target1']:.4f}$",
                    f"{s['macro_target']:.4f}$"
                )
        console.print(detail_table)

# ============ التشغيل الرئيسي ============
def main():
    console.print(Panel.fit(f"[bold cyan]بدء فحص العملات لعدد {len(WATCHLIST)} عملة عبر الفريمات (15m, 1h, 4h, 1d, 3d, 1w)...[/bold cyan]", title="[bold green]Halal Crypto Scanner[/bold green]"))
    
    score_state = load_score_state()
    clean_old_events(score_state)

    try:
        fng_status = get_fear_and_greed_index()
    except Exception:
        fng_status = None

    btc_d_df = fetch_klines("BTC.D", timeframe="1d")
    usdt_d_df = fetch_klines("USDT.D", timeframe="1d")
    dominance_report = analyze_market_dominance(btc_d_df, usdt_d_df)

    if dominance_report["status"] != "NEUTRAL":
        console.print(Panel(dominance_report["message"], title="[bold yellow]Macro Dominance Alert[/bold yellow]", border_style="yellow"))
        alert_manager.send_alert("MACRO_DOMINANCE", "MARKET", "1D", dominance_report["message"], ignore_cooldown=True)
        send_telegram_message(dominance_report["message"])

    current_market_prices = {}

    def process_worker(sym):
        symbol_signals = []
        symbol_bearish = []
        macro_info = analyze_macro_trends(sym)
        local_prices = {}

        for tf in ["15m", "1h", "4h", "1d", "3d"]:
            df = fetch_klines(sym, timeframe=tf)
            if df is None:
                continue
            
            latest_price = float(df['close'].iloc[-1])
            local_prices[sym] = latest_price

            try:
                sigs = analyze_symbol(sym, df, timeframe=tf, score_state=score_state)
                for sig in sigs:
                    sig["macro_info"] = macro_info
                    symbol_signals.append(sig)
                
                bearish_alerts = analyze_bearish_signals(sym, df, timeframe=tf)
                for b_alert in bearish_alerts:
                    symbol_bearish.append(b_alert)

            except Exception as e:
                console.print(f"[red][خطأ تحليل][/red] {sym} على فريم {tf}: {e}")

        return symbol_signals, symbol_bearish, local_prices

    all_signals = []
    all_bearish_alerts = []
    grouped_signals = {k: [] for k in STRATEGY_NAMES.keys()}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_worker, sym) for sym in WATCHLIST]
        for future in futures:
            signals, bearish_list, local_prices = future.result()
            current_market_prices.update(local_prices)
            
            for sig in signals:
                symbol = sig["symbol"]
                tf = sig.get("timeframe", "1h")
                tracking_key = f"{symbol}_{tf}"
                macro_info = sig.get("macro_info", {})
                strategy_type, formatted_msg = classify_and_format_signal(sig, macro_info, fng_status)
                
                sig["strategy_type"] = strategy_type
                sig["formatted_message"] = formatted_msg

                # ---------------------------------------------------------
                # Sprint 008-E: V2 Shadow Integration
                # ---------------------------------------------------------
                # V2 receives the exact legacy signal after classification.
                # SHADOW mode performs Decision + Risk + Eligibility + Audit,
                # but NEVER creates a TradeState and NEVER sends an exchange
                # order. Any V2 failure is isolated from the legacy scanner.
                if shadow_bridge is not None:
                    try:
                        v2_result = shadow_bridge.evaluate(
                            signal=sig,
                            strategy_type=strategy_type,
                            macro_info=macro_info,
                            active_positions=len(
                                getattr(
                                    trade_manager,
                                    "open_trades",
                                    [],
                                )
                            ),
                            account_equity=float(
                                getattr(
                                    trade_manager,
                                    "account_balance",
                                    1000.0,
                                )
                            ),
                            risk_percent=float(
                                getattr(
                                    trade_manager,
                                    "risk_per_trade_pct",
                                    1.0,
                                )
                            ),
                        )

                        sig["v2_shadow"] = compare_legacy_and_v2(
                            legacy_strategy=strategy_type,
                            result=v2_result,
                        )

                        # Sprint 008-G: register accepted V2 outcome.
                        # Observation-only: never opens/modifies/closes a trade.
                        if shadow_outcome_tracker is not None:
                            try:
                                shadow_outcome = (
                                    shadow_outcome_tracker.register_if_accepted(
                                        signal=sig,
                                        strategy_type=strategy_type,
                                        result=v2_result,
                                    )
                                )

                                if shadow_outcome is not None:
                                    sig["v2_shadow_outcome"] = {
                                        "signal_id": shadow_outcome.signal_id,
                                        "status": shadow_outcome.status.value,
                                        "registered": True,
                                    }
                                else:
                                    sig["v2_shadow_outcome"] = {
                                        "registered": False,
                                    }
                            except Exception as outcome_error:
                                sig["v2_shadow_outcome"] = {
                                    "registered": False,
                                    "error": str(outcome_error),
                                }
                        else:
                            sig["v2_shadow_outcome"] = {
                                "registered": False,
                                "status": "tracker_unavailable",
                            }

                    except Exception as shadow_error:
                        sig["v2_shadow"] = {
                            "status": "shadow_error",
                            "legacy_strategy": strategy_type,
                            "error": str(shadow_error),
                        }
                        sig["v2_shadow_outcome"] = {
                            "registered": False,
                            "status": "shadow_error",
                        }
                else:
                    sig["v2_shadow"] = {
                        "status": "shadow_unavailable",
                        "legacy_strategy": strategy_type,
                    }
                    sig["v2_shadow_outcome"] = {
                        "registered": False,
                        "status": "shadow_unavailable",
                    }

                console.print(
                    Panel(
                        formatted_msg,
                        title=f"[bold yellow]{symbol}[/bold yellow] - [cyan]{tf.upper()}[/cyan]",
                        border_style="cyan",
                    )
                )

                # إرسال التنبيه وتدوينه في AlertManager
                alert_manager.send_alert(
                    alert_type=strategy_type,
                    symbol=symbol,
                    timeframe=tf,
                    message=formatted_msg,
                    extra_data=sig
                )

                if should_alert(score_state, tracking_key, SCORE_THRESHOLD):
                    send_telegram_message(formatted_msg)
                    mark_alert_sent(score_state, tracking_key)

                # فتح وإدارة الصفقة داخل TradeManager عند التوافق مع الخطط الفعالة
                if strategy_type in ["WYCKOFF_SMC_ACCUMULATION", "CVD_BREAKOUT_CONFIRMED", "ULTIMATE_MASTER_A_PLUS", "TREND_FOLLOWING_4_CONFIRMS"]:
                    trade_manager.open_trade(
                        symbol=symbol,
                        side="BUY",
                        entry_price=sig["price"],
                        tp_price=sig["target2"],
                        sl_price=sig["stop_loss"],
                        use_trailing=True,
                        trailing_activation_pct=1.5,
                        trailing_callback_pct=1.0,
                        plan_id=strategy_type,
                        target1=sig["target1"],
                        target2=sig["target2"],
                        target3=sig["target3"],
                        target4=sig["target4"],
                        macro_target=sig["macro_target"]
                    )

                all_signals.append(sig)
                
                if strategy_type in grouped_signals:
                    grouped_signals[strategy_type].append(sig)
                else:
                    grouped_signals["STANDARD"].append(sig)

            for b_alert in bearish_list:
                console.print(Panel(b_alert["message"], title="[bold red]Bearish Risk Alert[/bold red]", border_style="red"))
                alert_manager.send_alert(
                    alert_type=b_alert["type"],
                    symbol=b_alert["symbol"],
                    timeframe=b_alert["timeframe"],
                    message=b_alert["message"],
                    extra_data=b_alert
                )
                send_telegram_message(b_alert["message"])
                all_bearish_alerts.append(b_alert)
                grouped_signals["BEARISH_RISK"].append(b_alert)

    render_grouped_alert_dashboard(grouped_signals, all_bearish_alerts)

    # تحديث وتتبع الصفقات المفتوحة مع تغير الأسعار اللحظية
    if current_market_prices:
        trade_manager.update_and_check_trades(current_market_prices)

    save_score_state(score_state)

    # مزامنة الصفقات المفتوحة والمغلقة في AlertManager وإخراج ملف market_status.json الموحد
    open_trades_list = getattr(trade_manager, "open_trades", [])
    closed_trades_list = getattr(trade_manager, "closed_trades", [])
    alert_manager.update_trades_in_status(open_trades=open_trades_list, closed_trades_history=closed_trades_list)

    market_macro_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dominance_status": dominance_report.get("status", "NEUTRAL"),
        "dominance_summary": dominance_report.get("message", ""),
        "bullish_signals_count": len(all_signals),
        "bearish_signals_count": len(all_bearish_alerts),
        "grouped_signals_summary": {k: len(v) for k, v in grouped_signals.items()},
        "bullish_signals": all_signals,
        "bearish_signals": all_bearish_alerts,
        "open_trades": open_trades_list,
        "recent_closed_trades": closed_trades_list[-10:],
        "signals": all_signals + all_bearish_alerts,
        "v2_shadow_mode": "SHADOW",
        "v2_shadow_summary": {
            "evaluated": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
                in {"agreement", "v2_reject"}
            ),
            "agreements": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
                == "agreement"
            ),
            "v2_rejections": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
                == "v2_reject"
            ),
            "unmapped_or_insufficient": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
                == "unmapped_or_insufficient_evidence"
            ),
            "errors": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
                == "shadow_error"
            ),
            "unavailable": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
                == "shadow_unavailable"
            ),
            "outcomes_registered": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow_outcome", {}).get("registered")
                is True
            ),
        },
    }

    with open("market_status.json", "w", encoding="utf-8") as f:
        json.dump(market_macro_data, f, ensure_ascii=False, indent=4, default=str)

    os.makedirs("docs", exist_ok=True)
    with open("docs/market_status.json", "w", encoding="utf-8") as f:
        json.dump(market_macro_data, f, ensure_ascii=False, indent=4, default=str)

    with open("docs/signals.json", "w", encoding="utf-8") as f:
        json.dump(market_macro_data, f, ensure_ascii=False, indent=4, default=str)

    console.print(Panel.fit(f"[bold green]انتهى الفحص بنجاح. تم رصد {len(all_signals)} إشارة صعود و {len(all_bearish_alerts)} تحذير هبوط وحفظ التقرير المجمع في market_status.json و docs/.[/bold green]", title="[bold]Summary[/bold]"))

if __name__ == "__main__":
    main()

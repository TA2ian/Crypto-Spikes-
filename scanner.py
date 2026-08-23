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
# V2 validation mode: 1H only.
# Other signal timeframes are intentionally disabled until the 1H
# pipeline has been validated independently.
ACTIVE_TIMEFRAMES = ["1h"]
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
        target1 = min(pattern_target, resistance) if resistance > entry_price else pattern_target
    elif resistance > entry_price * 1.01:
        target1 = resistance
    elif fvg.get("target") and fvg["target"] > entry_price * 1.01:
        target1 = fvg["target"]
    else:
        target1 = entry_price + (atr * 1.5)

    risk = entry_price - stop_loss
    target2 = entry_price + (risk * 2.0)
    target3 = entry_price + (risk * 3.0)
    target4 = entry_price + (risk * 4.0)
    macro_target = max(target3, target1 * 1.05)

    return (
        float(stop_loss),
        float(target1),
        float(target2),
        float(target3),
        float(target4),
        float(macro_target),
    )

# ============ تحليل الإشارات الصعودية ============
def analyze_bullish_signals(sym: str, df: pd.DataFrame, timeframe: str = "1h", score_state: dict | None = None) -> list:
    signals = []
    try:
        rsi_series = calc_rsi(df['close'], 14)
        rsi = float(rsi_series.iloc[-1])
        if pd.isna(rsi): return signals

        ema_data = calculate_ema_indicators(df)
        bb_data = calculate_bollinger_bands(df)
        ms = detect_market_structure(df)
        avg_vol = avg_volume(df)
        current_vol = float(df['volume'].iloc[-1])
        is_sweep = bool(df['low'].iloc[-1] < df['low'].iloc[-2])
        is_effort = detect_volume_imbalance_and_effort(df)
        bull_ob = find_bullish_order_block(df)
        extra = build_extra_analysis(df, rsi_series)
        atr = calculate_atr(df)
        resistance = find_support_resistance(df)['nearest_resistance']
        fvg = detect_fvg(df)

        wyckoff = detect_wyckoff_bull_market(df, ms, is_sweep, is_effort, bull_ob, ema_data)
        if wyckoff.get("is_wyckoff_setup"):
            signals.append({"symbol": sym, "timeframe": timeframe, "type": "wyckoff_bull", "price": float(df['close'].iloc[-1]), "signal_status": "دخول أول", "stop_loss": calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))[0], "target1": calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))[1], "target2": calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))[2], "target3": calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))[3], "target4": calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))[4], "macro_target": calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))[5], "confluence": ["Wyckoff", "SMC", "EMA", "Volume"]})

        if len(df) >= 50 and current_vol > avg_vol * VOLUME_MULTIPLIER and rsi > 50 and bb_data.get("is_squeeze"):
            targets = calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))
            signals.append({"symbol": sym, "timeframe": timeframe, "type": "cvd_breakout_confirmed", "price": float(df['close'].iloc[-1]), "signal_status": "دخول أول", "stop_loss": targets[0], "target1": targets[1], "target2": targets[2], "target3": targets[3], "target4": targets[4], "macro_target": targets[5], "confluence": ["CVD", "Volume", "RSI", "Bollinger Squeeze"]})

        if len(df) >= 50 and rsi > 55 and ema_data.get("golden_cross") and ema_data.get("above_ema50"):
            targets = calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))
            signals.append({"symbol": sym, "timeframe": timeframe, "type": "trend_following", "price": float(df['close'].iloc[-1]), "signal_status": "دخول أول", "stop_loss": targets[0], "target1": targets[1], "target2": targets[2], "target3": targets[3], "target4": targets[4], "macro_target": targets[5], "confluence": ["EMA", "RSI", "Trend"]})

        if rsi < RSI_OVERSOLD and bb_data.get("is_oversold_bb"):
            targets = calculate_fixed_targets(float(df['close'].iloc[-1]), atr, resistance, fvg, ms, extra, detect_candle_patterns(df))
            signals.append({"symbol": sym, "timeframe": timeframe, "type": "mean_reversion", "price": float(df['close'].iloc[-1]), "signal_status": "دخول أول", "stop_loss": targets[0], "target1": targets[1], "target2": targets[2], "target3": targets[3], "target4": targets[4], "macro_target": targets[5], "confluence": ["RSI Oversold", "Bollinger Lower Band"]})

        return signals
    except Exception as e:
        console.print(f"[red][خطأ تحليل صعودي][/red] {sym}: {e}")
        return signals

def analyze_bearish_signals(sym: str, df: pd.DataFrame, timeframe: str = "1h") -> list:
    alerts = []
    try:
        rsi_series = calc_rsi(df['close'], 14)
        rsi = float(rsi_series.iloc[-1])
        ema_data = calculate_ema_indicators(df)
        ms = detect_market_structure(df)
        if ema_data.get("above_ema50") is False and ema_data.get("above_ema200") is False and rsi < 45:
            alerts.append({"symbol": sym, "timeframe": timeframe, "type": "bearish_trend", "price": float(df['close'].iloc[-1]), "level": float(ms.get('last_high') or df['close'].iloc[-1])})
        return alerts
    except Exception as e:
        console.print(f"[red][خطأ تحليل هبوطي][/red] {sym}: {e}")
        return alerts

def analyze_symbol(sym: str, df: pd.DataFrame, timeframe: str = "1h", score_state: dict | None = None) -> list:
    bullish = analyze_bullish_signals(sym, df, timeframe=timeframe, score_state=score_state)
    return bullish

def classify_and_format_signal(sig: dict, macro_info: dict, fng_status: str) -> tuple:
    symbol = sig.get("symbol", "UNKNOWN")
    tf = sig.get("timeframe", "1h")
    entry = float(sig.get("price", 0.0))
    stop_loss = float(sig.get("stop_loss", 0.0))
    t1 = float(sig.get("target1", entry))
    t2 = float(sig.get("target2", t1))
    macro_t = float(sig.get("macro_target", t2))
    entry_str = f"{entry:.4f}"
    status_tag = sig.get("signal_status", "دخول أول")

    if sig.get("type") == "wyckoff_bull":
        msg = f"[bold]🏛️ إشــــارة تجميع مؤسساتي (Wyckoff + SMC)[/bold]\n\n"
        msg += f"• العملة: [cyan]{symbol}[/cyan]\n"
        msg += f"• الفريم: [yellow]{tf.upper()}[/yellow]\n"
        msg += f"• السعر: [green]{entry_str}$[/green]\n"
        msg += f"• وقف الخسارة: [red]{stop_loss:.4f}$[/red]\n"
        msg += f"• الهدف الأول: [green]{t1:.4f}$[/green]\n"
        msg += f"• الهدف الثاني: [green]{t2:.4f}$[/green]\n"
        msg += f"• الهدف البعيد: [green]{macro_t:.4f}$[/green]\n"
        return "WYCKOFF_SMC_ACCUMULATION", msg

    if sig.get("type") == "cvd_breakout_confirmed":
        msg = f"[bold]🚀 اختراق مدعوم بـ CVD & Squeeze[/bold]\n\n"
        msg += f"• العملة: [cyan]{symbol}[/cyan]\n"
        msg += f"• الفريم: [yellow]{tf.upper()}[/yellow]\n"
        msg += f"• السعر: [green]{entry_str}$[/green]\n"
        msg += f"• وقف الخسارة: [red]{stop_loss:.4f}$[/red]\n"
        msg += f"• الهدف الأول: [green]{t1:.4f}$[/green]\n"
        msg += f"• الهدف الثاني: [green]{t2:.4f}$[/green]\n"
        msg += f"• الهدف البعيد: [green]{macro_t:.4f}$[/green]\n"
        return "CVD_BREAKOUT_CONFIRMED", msg

    if sig.get("type") == "trend_following":
        msg = f"[bold]📈 تتبع الاتجاه المؤكد (4 شروط)[/bold]\n\n"
        msg += f"• العملة: [cyan]{symbol}[/cyan]\n"
        msg += f"• الفريم: [yellow]{tf.upper()}[/yellow]\n"
        msg += f"• السعر: [green]{entry_str}$[/green]\n"
        msg += f"• وقف الخسارة: [red]{stop_loss:.4f}$[/red]\n"
        msg += f"• الهدف الأول: [green]{t1:.4f}$[/green]\n"
        msg += f"• الهدف الثاني: [green]{t2:.4f}$[/green]\n"
        msg += f"• الهدف البعيد: [green]{macro_t:.4f}$[/green]\n"
        return "TREND_FOLLOWING_4_CONFIRMS", msg

    if sig.get("type") == "mean_reversion":
        msg = f"[bold]🎯 صيد القيعان والارتداد (Mean Reversion)[/bold]\n\n"
        msg += f"• العملة: [cyan]{symbol}[/cyan]\n"
        msg += f"• الفريم: [yellow]{tf.upper()}[/yellow]\n"
        msg += f"• السعر: [green]{entry_str}$[/green]\n"
        msg += f"• وقف الخسارة: [red]{stop_loss:.4f}$[/red]\n"
        msg += f"• الهدف الأول: [green]{t1:.4f}$[/green]\n"
        msg += f"• الهدف الثاني: [green]{t2:.4f}$[/green]\n"
        msg += f"• الهدف البعيد: [green]{macro_t:.4f}$[/green]\n"
        return "MEAN_REVERSION_4_CONFIRMS", msg

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
    console.print(Panel.fit(f"[bold cyan]بدء فحص العملات على فريم 1h فقط لعدد {len(WATCHLIST)} عملة...[/bold cyan]", title="[bold green]Halal Crypto Scanner[/bold green]"))
    
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

        for tf in ACTIVE_TIMEFRAMES:
            df = fetch_klines(sym, timeframe=tf)
            if df is None:
                continue
            
            latest_price = float(df['close'].iloc[-1])
            local_prices[sym] = latest_price

            # Sprint 008-I: feed each completed market bar into the
            # observation-only Shadow Outcome tracker BEFORE registering
            # signals from the current candle. This allows previously
            # accepted V2 shadow outcomes to resolve on later candles
            # while preserving the no-same-candle rule.
            if shadow_outcome_tracker is not None:
                try:
                    shadow_outcome_tracker.process_market_bar(
                        symbol=sym,
                        timeframe=tf,
                        high=float(df["high"].iloc[-1]),
                        low=float(df["low"].iloc[-1]),
                        timestamp=str(df["time"].iloc[-1]),
                    )
                except Exception as outcome_error:
                    console.print(
                        f"[yellow][Shadow Outcome][/yellow] "
                        f"{sym} {tf}: {outcome_error}"
                    )

            try:
                sigs = analyze_symbol(sym, df, timeframe=tf, score_state=score_state)
                for sig in sigs:
                    sig["macro_info"] = macro_info

                    # Sprint 008-H:
                    # Record the candle that produced this signal.
                    # Shadow outcomes must never resolve against
                    # the same candle that created the signal.
                    sig["candle_timestamp"] = str(
                        df["time"].iloc[-1]
                    )
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
                        border_style="green",
                    )
                )

                all_signals.append(sig)
                grouped_signals.setdefault(strategy_type, []).append(sig)

            all_bearish_alerts.extend(bearish_list)

    render_grouped_alert_dashboard(grouped_signals, all_bearish_alerts)

    # مزامنة الصفقات المفتوحة والمغلقة في AlertManager وإخراج ملف market_status.json الموحد
    for sig in all_signals:
        tracking_key = f"{sig['symbol']}_{sig.get('timeframe', '1h')}"
        alert_manager.add_signal(tracking_key, sig)

    for b_alert in all_bearish_alerts:
        tracking_key = f"{b_alert['symbol']}_{b_alert.get('timeframe', '1h')}_bearish"
        alert_manager.add_signal(tracking_key, b_alert)

    market_status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "v2_shadow_mode": "SHADOW",
        "v2_shadow_summary": {
            "signals_total": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status")
            ),
            "agreement": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status") == "agreement"
            ),
            "v2_reject": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status") == "v2_reject"
            ),
            "unmapped_or_insufficient_evidence": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow", {}).get("status") == "unmapped_or_insufficient_evidence"
            ),
            "shadow_outcomes_registered": sum(
                1
                for signal in all_signals
                if signal.get("v2_shadow_outcome", {}).get("registered")
            ),
        },
        "bullish_signals_count": len(all_signals),
        "bearish_signals_count": len(all_bearish_alerts),
        "grouped_signals_summary": {
            k: len(v) for k, v in grouped_signals.items()
        },
        "bullish_signals": all_signals,
        "bearish_signals": all_bearish_alerts,
        "open_trades": alert_manager.get_open_alerts(),
        "closed_trades": alert_manager.get_closed_alerts(),
    }

    with open("market_status.json", "w", encoding="utf-8") as f:
        json.dump(market_status, f, ensure_ascii=False, indent=4, default=str)

    os.makedirs("docs", exist_ok=True)
    with open("docs/signals.json", "w", encoding="utf-8") as f:
        json.dump(all_signals, f, ensure_ascii=False, indent=4, default=str)
    with open("docs/market_status.json", "w", encoding="utf-8") as f:
        json.dump(market_status, f, ensure_ascii=False, indent=4, default=str)

    console.print(Panel.fit(f"[bold green]انتهى الفحص بنجاح. تم رصد {len(all_signals)} إشارة صعود و {len(all_bearish_alerts)} تحذير هبوط وحفظ التقرير المجمع في market_status.json و docs/.[/bold green]", title="[bold]Summary[/bold]"))

if __name__ == "__main__":
    main()

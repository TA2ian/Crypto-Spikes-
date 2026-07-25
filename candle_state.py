"""
تتبع آخر شمعة تم إرسال تنبيه عنها لكل (عملة، فريم)
يمنع تكرار نفس التنبيه بكل تشغيلة طالما الشمعة نفسها لسا الأحدث المقفولة
"""
import os
import json

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docs", "last_alerted.json"
)


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def make_key(symbol: str, timeframe: str) -> str:
    return f"{symbol}:{timeframe}"


def is_new_candle(state: dict, symbol: str, timeframe: str, candle_time) -> bool:
    """يتحقق إن كانت هذه الشمعة مختلفة عن آخر شمعة سُجّلت لهذه التوليفة"""
    key = make_key(symbol, timeframe)
    return state.get(key) != candle_time


def mark_alerted(state: dict, symbol: str, timeframe: str, candle_time):
    key = make_key(symbol, timeframe)
    state[key] = candle_time

"""
نظام النقاط المرجّحة لتتبع تراكم الإشارات على نفس العملة (نفس الاتجاه)
خلال نافذة زمنية معينة، وإرسال تذكير عند تجاوز حد معين.

كل نوع إشارة له وزن مختلف حسب قوته التحليلية النسبية.
"""
import os
import json
import time

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docs", "coin_score_state.json"
)

# ============ إعدادات الأوزان ============
WEIGHTS = {
    "base_signal": 1.0,              # اختراق مقاومة / ارتداد دعم عادي
    "candle_pattern_confirm": 0.5,    # نمط شمعة أو Order Block مؤكد
    "divergence_confirm": 1.5,        # دايفرجنس RSI/MACD مؤكد بفوليوم
    "mtf_candle_close": 1.0,          # إغلاق شمعة كاسر مستوى (لكل فريم)
    "mtf_multi_alignment": 2.0,       # تطابق فريمين+ بنفس الاتجاه بنفس الوقت
    "cvd_confirm": 1.0,               # تأكيد اتجاه CVD (شراء/بيع متزايد يطابق الاتجاه)
    "cvd_divergence": 1.5,            # دايفرجنس CVD (تحذير قوي)
}

SCORE_THRESHOLD = 5.0        # الحد الذي يستوجب إرسال تذكير
WINDOW_HOURS = 24            # النافذة الزمنية لتجميع النقاط
DECAY_AFTER_HOURS = 48       # حذف السجلات الأقدم من هالمدة نهائياً (تنظيف الملف)


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


def _key(symbol: str, direction: str) -> str:
    return f"{symbol}:{direction}"


def add_points(state: dict, symbol: str, direction: str, points: float, reason: str):
    """يضيف نقاط جديدة لعملة+اتجاه معين، مع تسجيل الوقت والسبب"""
    key = _key(symbol, direction)
    now = int(time.time())

    if key not in state:
        state[key] = {"events": [], "already_alerted_at": None}

    state[key]["events"].append({"time": now, "points": points, "reason": reason})


def clean_old_events(state: dict):
    """يحذف الأحداث الأقدم من DECAY_AFTER_HOURS لتجنب تضخم الملف بلا حدود"""
    cutoff = int(time.time()) - DECAY_AFTER_HOURS * 3600
    for key in list(state.keys()):
        state[key]["events"] = [e for e in state[key]["events"] if e["time"] >= cutoff]
        if not state[key]["events"]:
            del state[key]


def current_score(state: dict, symbol: str, direction: str) -> float:
    """يحسب مجموع النقاط الحالي ضمن نافذة WINDOW_HOURS فقط"""
    key = _key(symbol, direction)
    if key not in state:
        return 0.0

    cutoff = int(time.time()) - WINDOW_HOURS * 3600
    return sum(e["points"] for e in state[key]["events"] if e["time"] >= cutoff)


def should_alert(state: dict, symbol: str, direction: str) -> bool:
    """
    يتحقق إن كان مجموع النقاط تجاوز الحد، ولم يُرسل تذكير له خلال آخر WINDOW_HOURS
    (لتجنب تكرار نفس رسالة التذكير بكل تشغيلة بعد ما تتجاوز العملة الحد مرة)
    """
    key = _key(symbol, direction)
    score = current_score(state, symbol, direction)

    if score < SCORE_THRESHOLD:
        return False

    last_alert = state.get(key, {}).get("already_alerted_at")
    if last_alert is None:
        return True

    hours_since_alert = (int(time.time()) - last_alert) / 3600
    return hours_since_alert >= WINDOW_HOURS


def mark_alert_sent(state: dict, symbol: str, direction: str):
    key = _key(symbol, direction)
    if key in state:
        state[key]["already_alerted_at"] = int(time.time())


def get_score_breakdown(state: dict, symbol: str, direction: str) -> list[dict]:
    """يعيد قائمة الأحداث المساهمة بالنقاط الحالية (للعرض بالرسالة)"""
    key = _key(symbol, direction)
    if key not in state:
        return []

    cutoff = int(time.time()) - WINDOW_HOURS * 3600
    return [e for e in state[key]["events"] if e["time"] >= cutoff]

"""
تتبع آخر شمعة تم إرسال تنبيه عنها لكل (عملة، فريم)
يمنع تكرار نفس التنبيه بكل تشغيلة طالما الشمعة نفسها لسا الأحدث المقفولة
"""
"""
تتبع آخر شمعة تم إرسال تنبيه عنها لكل (عملة، فريم)
يمنع تكرار نفس التنبيه بكل تشغيلة طالما الشمعة نفسها لسا الأحدث المقفولة
"""
import os
import json
import tempfile

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
        # في حال حدوث خطأ بقراءة الملف يتم إرجاع قاموس فارغ لتجنب تعطل البوت
        return {}


def save_state(state: dict):
    dir_name = os.path.dirname(STATE_FILE)
    os.makedirs(dir_name, exist_ok=True)
    
    # 1. إنشاء ملف مؤقت في نفس المجلد
    temp_fd, temp_path = tempfile.mkstemp(dir=dir_name)
    try:
        # 2. الكتابة في الملف المؤقت أولاً
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        # 3. استبدال الملف الأصلي بالمؤقت لحظياً (Atomic Replace)
        os.replace(temp_path, STATE_FILE)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e
        
def cleanup_state(state: dict, max_entries: int = 500) -> dict:
    """
    تقوم بتنظيف القاموس والاحتفاظ بأحدث `max_entries` عنصر فقط لتجنب تضخم الملف.
    """
    if len(state) <= max_entries:
        return state

    # إذا كانت القيمة التابعة لكل مفتاح هي Timestamp (وقت الشمعة)
    # نقوم بفرز العناصر بناءً على الوقت واختيار أحدث max_entries
    try:
        sorted_items = sorted(
            state.items(),
            key=lambda item: str(item[1]),
            reverse=True  # الأحدث أولاً
        )
        return dict(sorted_items[:max_entries])
    except Exception:
        # في حال وجود خطأ في المقارنة يتم إرجاع القاموس كما هو
        return state




def make_key(symbol: str, timeframe: str) -> str:
    # توحيد الأحرف لتجنب مشاكل الأحرف الكبيرة والصغيرة
    return f"{symbol.strip().upper()}:{timeframe.strip().lower()}"


def is_new_candle(state: dict, symbol: str, timeframe: str, candle_time) -> bool:
    """يتحقق إن كانت هذه الشمعة مختلفة عن آخر شمعة سُجّلت لهذه التوليفة"""
    key = make_key(symbol, timeframe)
    # تحويل candle_time لـ str لضمان سلامة المقارنة
    return state.get(key) != str(candle_time)


def mark_alerted(state: dict, symbol: str, timeframe: str, candle_time):
    key = make_key(symbol, timeframe)
    state[key] = str(candle_time)

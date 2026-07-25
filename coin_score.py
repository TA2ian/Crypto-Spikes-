"""
نظام النقاط المرجّحة لتتبع تراكم الإشارات على نفس العملة (نفس الاتجاه)
خلال نافذة زمنية معينة، وإرسال تذكير عند تجاوز حد معين.

كل نوع إشارة له وزن مختلف حسب قوته التحليلية النسبية.
"""
import requests  # تأكد من تثبيت المكتبة: pip install requests

# ============ إعدادات بوت تيليغرام ============
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ضع توكن البوت الخاص بك هنا
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # ضع Chat ID لقناتك أو حسابك هنا


def send_telegram_message(text: str) -> bool:
    """دالة مساعدة لإرسال الرسائل عبر API تيليغرام المباشر"""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not TELEGRAM_CHAT_ID:
        print("⚠️ لم يتم ضبط توكن البوت أو Chat ID الخاص بتيليغرام.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"  # لدعم التنسيق الغامق والرموز
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطأ أثناء إرسال رسالة تيليغرام: {e}")
        return False


def format_alert_message(symbol: str, direction: str, score: float, breakdown: list) -> str:
    """تنسيق نص الرسالة بشكل احترافي ومنظم"""
    direction_emoji = "🟢 LONG" if direction.upper() in ["LONG", "BUY", "شراء"] else "🔴 SHORT"
    
    # تحويل قائمة الإشارات إلى أسطر مرتبة
    reasons_list = []
    for item in breakdown:
        reasons_list.append(f"• {item['reason']} (`+{item['points']} p`)")
    
    reasons_text = "\n".join(reasons_list)

    msg = (
        f"🔥 **تراكم إشارات قوي: {symbol.upper()}**\n"
        f"🎯 **الاتجاه:** {direction_emoji}\n"
        f"📊 **مجموع النقاط:** `{score:.1f} / {SCORE_THRESHOLD}`\n\n"
        f"📋 **الإشارات المساهمة خلال 24 ساعة:**\n"
        f"{reasons_text}\n\n"
        f"💡 *يُنصح بمراجعة الشارت وتأكيد النماذج قبل الدخول.*"
    )
    return msg


def process_signal_and_alert(symbol: str, direction: str, signal_type: str, reason: str = ""):
    """
    الدالة الرئيسية التي تستدعيها عند اكتشاف أي إشارة جديدة.
    تقوم بـ: إضافة النقاط -> الفحص -> تنسيق الرسالة -> الإرسال لتيليغرام -> الحفظ.
    """
    state = load_state()
    
    # 1. التنظيف الدعمي للسجلات القديمة
    clean_old_events(state)
    
    # 2. إضافة الإشارة والنقاط الجديدة
    add_points(state, symbol, direction, signal_type, reason)
    
    # 3. التحقق هل تجاوزت العملة الحد المطلوب ويجب التنبيه؟
    if should_alert(state, symbol, direction):
        score = current_score(state, symbol, direction)
        breakdown = get_score_breakdown(state, symbol, direction)
        
        # 4. بناء وإرسال الرسالة
        message_text = format_alert_message(symbol, direction, score, breakdown)
        sent_success = send_telegram_message(message_text)
        
        # 5. إذا تم الإرسال بنجاح، يتم تحديث حالة التنبيه
        if sent_success:
            mark_alert_sent(state, symbol, direction)
    
    # 6. حفظ التغييرات على القرص
    save_state(state)

import requests  # تأكد من تثبيت المكتبة: pip install requests

# ============ إعدادات بوت تيليغرام ============
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ضع توكن البوت الخاص بك هنا
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"      # ضع Chat ID لقناتك أو حسابك هنا


def send_telegram_message(text: str) -> bool:
    """دالة مساعدة لإرسال الرسائل عبر API تيليغرام المباشر"""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not TELEGRAM_CHAT_ID:
        print("⚠️ لم يتم ضبط توكن البوت أو Chat ID الخاص بتيليغرام.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"  # لدعم التنسيق الغامق والرموز
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ خطأ أثناء إرسال رسالة تيليغرام: {e}")
        return False


def format_alert_message(symbol: str, direction: str, score: float, breakdown: list) -> str:
    """تنسيق نص الرسالة بشكل احترافي ومنظم"""
    direction_emoji = "🟢 LONG" if direction.upper() in ["LONG", "BUY", "شراء"] else "🔴 SHORT"
    
    # تحويل قائمة الإشارات إلى أسطر مرتبة
    reasons_list = []
    for item in breakdown:
        reasons_list.append(f"• {item['reason']} (`+{item['points']} p`)")
    
    reasons_text = "\n".join(reasons_list)

    msg = (
        f"🔥 **تراكم إشارات قوي: {symbol.upper()}**\n"
        f"🎯 **الاتجاه:** {direction_emoji}\n"
        f"📊 **مجموع النقاط:** `{score:.1f} / {SCORE_THRESHOLD}`\n\n"
        f"📋 **الإشارات المساهمة خلال 24 ساعة:**\n"
        f"{reasons_text}\n\n"
        f"💡 *يُنصح بمراجعة الشارت وتأكيد النماذج قبل الدخول.*"
    )
    return msg


def process_signal_and_alert(symbol: str, direction: str, signal_type: str, reason: str = ""):
    """
    الدالة الرئيسية التي تستدعيها عند اكتشاف أي إشارة جديدة.
    تقوم بـ: إضافة النقاط -> الفحص -> تنسيق الرسالة -> الإرسال لتيليغرام -> الحفظ.
    """
    state = load_state()
    
    # 1. التنظيف الدعمي للسجلات القديمة
    clean_old_events(state)
    
    # 2. إضافة الإشارة والنقاط الجديدة
    add_points(state, symbol, direction, signal_type, reason)
    
    # 3. التحقق هل تجاوزت العملة الحد المطلوب ويجب التنبيه؟
    if should_alert(state, symbol, direction):
        score = current_score(state, symbol, direction)
        breakdown = get_score_breakdown(state, symbol, direction)
        
        # 4. بناء وإرسال الرسالة
        message_text = format_alert_message(symbol, direction, score, breakdown)
        sent_success = send_telegram_message(message_text)
        
        # 5. إذا تم الإرسال بنجاح، يتم تحديث حالة التنبيه
        if sent_success:
            mark_alert_sent(state, symbol, direction)
    
    # 6. حفظ التغييرات على القرص
    save_state(state)

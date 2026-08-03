import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
import os

class AlertManager:
    def __init__(self, status_file="market_status.json", log_file="alerts.log", max_active_alerts=10):
        self.status_file = status_file
        self.max_active_alerts = max_active_alerts
        
        # 1. إعداد السجلات المتدورة (Rotating Log Handler)
        # يحفظ الملف حتى 5 ميجابايت، ويستبدله بـ 3 أراشيف كحد أقصى
        self.logger = logging.getLogger("AlertLogger")
        self.logger.setLevel(logging.INFO)
        
        handler = RotatingFileHandler(
            log_file, 
            maxBytes=5 * 1024 * 1024, # 5 MB
            backupCount=3, 
            encoding="utf-8"
        )
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def process_alert(self, alert_type: str, symbol: str, timeframe: str, message: str, extra_data: dict = None):
        """
        دالة استقبال التنبيهات وفصلها عن ملف الحالة الرئيسي
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        alert_payload = {
            "timestamp": timestamp,
            "type": alert_type,
            "symbol": symbol,
            "timeframe": timeframe,
            "message": message,
            "details": extra_data or {}
        }

        # أ) تسجيل التنبيه في ملف الأرشيف الجانبي (alerts.log)
        self.logger.info(f"[{symbol}] [{timeframe}] {alert_type}: {message}")

        # ب) إرسال إشعار خارجية (تليجرام / ديسكورد) - يمكن إضافة الكود هنا
        self._send_external_notification(alert_payload)

        # ج) تحديث ملف الحالة (market_status.json) مع حصر التنبيهات
        self._update_market_status(alert_payload)

    def _send_external_notification(self, alert: dict):
        """إرسال التنبيه إلى تليجرام أو أي منصة دون تعطيل الكود الأساسي"""
        # مثال: TelegramBot.send(alert['message'])
        pass

    def _update_market_status(self, new_alert: dict):
        """تحديث ملف market_status مع تطبيق الحجم المحدد (Buffer)"""
        status_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "dominance_status": "NEUTRAL",
            "active_alerts_count": 0,
            "recent_alerts": []
        }

        # قراءة الملف الحالي إن وجد
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception:
                pass # في حال وجود خطأ في القراءة يتم استخدام الهيكل الافتراضي

        # إضافة التنبيه الجديد في بداية القائمة
        recent_alerts = status_data.get("recent_alerts", [])
        recent_alerts.insert(0, new_alert)

        # حصر التنبيهات النشطة (Ring Buffer) لضمان بقاء الملف خفيفاً
        status_data["recent_alerts"] = recent_alerts[:self.max_active_alerts]
        status_data["active_alerts_count"] = len(status_data["recent_alerts"])
        status_data["last_updated"] = new_alert["timestamp"]

        # إعادة كتابة الملف ببيانات نظيفة ومحدودة
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)


import json
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
import os


class AlertManager:
    """
    مُحرك التنبيهات وإدارة الحالة اللحظية (Alert & Market Status Manager)
    يدعم معالجة مرحلية لآلة الحالات (State Machine) ومزامنة الصفقات والخطط الـ 8 مع الويب.
    """
    def __init__(self, status_file="docs/market_status.json", log_file="alerts.log", max_active_alerts=20, alert_cooldown_minutes=15):
        self.file_path = status_file
        self.status_file = status_file
        self.log_file = log_file
        self.max_active_alerts = max_active_alerts
        self.alert_cooldown_minutes = alert_cooldown_minutes
        self.last_alerts_time = {}

        # تهيئة الـ Logger لتسجيل الأحداث
        self.logger = logging.getLogger("AlertManager")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            handler = RotatingFileHandler(self.log_file, maxBytes=2*1024*1024, backupCount=2, encoding="utf-8")
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _default_converter(self, o):
        """تحويل أنواع NumPy لتفادي خطأ JSON Serialization"""
        if isinstance(o, (np.bool_, bool)):
            return bool(o)
        if isinstance(o, (np.integer, np.int64, np.int32)):
            return int(o)
        if isinstance(o, (np.floating, np.float64, np.float32)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    def _write_status_file(self, status_data):
        """كتابة حالة السوق إلى الملف بأمان مع إنشاء المجلد تلقائياً"""
        dir_name = os.path.dirname(self.file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4, default=self._default_converter)

    def is_alert_allowed(self, alert_type: str, symbol: str, timeframe: str) -> bool:
        """فحص فترة التهدئة للتنبيهات العادية"""
        alert_key = f"{symbol}_{alert_type}_{timeframe}"
        now = datetime.now(timezone.utc)
        
        if alert_key in self.last_alerts_time:
            last_sent = self.last_alerts_time[alert_key]
            if now - last_sent < timedelta(minutes=self.alert_cooldown_minutes):
                return False
        
        self.last_alerts_time[alert_key] = now
        return True

    def send_alert(self, alert_type: str, symbol: str, timeframe: str, message: str, extra_data: dict = None, ignore_cooldown=False):
        """
        إرسال التنبيه وتدوينه وتحديث ملف market_status.json
        """
        # الأحداث الحرجة وتغيرات آلة الحالات تتجاوز فترة التهدئة تلقائياً
        critical_alerts = [
            "NEW_SIGNAL", "FIRST_ENTRY", "RETEST_ENTRY", "ACTIVE", 
            "TRADE_T1", "TRADE_TP2", "TRADE_TP3", "TRADE_TP4", 
            "TRADE_SL", "TRADE_CLOSED_TRAILING"
        ]
        if alert_type in critical_alerts:
            ignore_cooldown = True

        if not ignore_cooldown and not self.is_alert_allowed(alert_type, symbol, timeframe):
            self.logger.info(f"[SKIP ALERT] تم تجاهل تنبيه مكرر لـ {symbol} ({alert_type}).")
            return False

        timestamp = datetime.now(timezone.utc).isoformat()
        
        # استخراج مرحلة الصفقة الخالية ورقم الخطة
        stage = extra_data.get("current_stage", alert_type) if extra_data else alert_type
        plan_id = extra_data.get("plan_id", "PLAN_1") if extra_data else "PLAN_1"
        
        alert_payload = {
            "timestamp": timestamp,
            "type": alert_type,
            "stage": stage,
            "plan_id": plan_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "message": message,
            "details": extra_data or {}
        }

        self.logger.info(f"[{plan_id}] [{symbol}] [{timeframe}] ({stage}): {message}")
        self._update_market_status(new_alert=alert_payload)
        return True

    def update_trades_in_status(self, open_trades: list, closed_trades_history: list = None):
        """
        مزامنة الصفقات المفتوحة والمغلقة وتوليد ملخص الخطط الـ 8 للويب
        """
        status_data = self._read_status_file()
        status_data["open_trades"] = open_trades
        status_data["open_trades_count"] = len(open_trades)
        
        if closed_trades_history is not None:
            status_data["recent_closed_trades"] = closed_trades_history[-10:]
        
        # توليد ملخص مجمع يتيح للوحة الويب قراءة أداء كل خطة من الخطط الـ 8 بالتوازي
        status_data["active_plans_summary"] = self._generate_plans_summary(open_trades)
        status_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write_status_file(status_data)

    def _generate_plans_summary(self, open_trades: list) -> dict:
        """تصنيف الصفقات المفتوحة بحسب الخطط الـ 8 لسهولة استهلاكها في واجهة الويب"""
        summary = {}
        for trade in open_trades:
            p_id = trade.get("plan_id", "PLAN_1")
            if p_id not in summary:
                summary[p_id] = {"count": 0, "trades": []}
            
            summary[p_id]["count"] += 1
            summary[p_id]["trades"].append({
                "id": trade.get("id"),
                "symbol": trade.get("symbol"),
                "stage": trade.get("current_stage"),
                "avg_entry": trade.get("average_entry", trade.get("entry_price")),
                "best_entry": trade.get("best_entry"),
                "retest_count": trade.get("retest_count", 0),
                "stop_loss": trade.get("current_stop_loss", trade.get("stop_loss"))
            })
        return summary

    def _read_status_file(self) -> dict:
        """قراءة الملف الحالي أو تقديم الهيكل الافتراضي"""
        default_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "active_alerts_count": 0,
            "recent_alerts": [],
            "open_trades_count": 0,
            "open_trades": [],
            "recent_closed_trades": [],
            "active_plans_summary": {}
        }
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default_data

    def _update_market_status(self, new_alert: dict):
        """إضافة التنبيه الجديد في مقدمة القائمة وتدويره"""
        status_data = self._read_status_file()
        recent_alerts = status_data.get("recent_alerts", [])
        recent_alerts.insert(0, new_alert)

        status_data["recent_alerts"] = recent_alerts[:self.max_active_alerts]
        status_data["active_alerts_count"] = len(status_data["recent_alerts"])
        status_data["last_updated"] = new_alert["timestamp"]

        self._write_status_file(status_data)

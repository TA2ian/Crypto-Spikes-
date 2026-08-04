import json
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
import os


class AlertManager:
    def __init__(self, status_file="market_status.json", log_file="alerts.log", max_active_alerts=10, alert_cooldown_minutes=15):
        self.status_file = status_file
        self.max_active_alerts = max_active_alerts
        self.alert_cooldown_minutes = alert_cooldown_minutes
        self.last_alerts_time = {}
        
        # إعداد السجلات log file
        self.logger = logging.getLogger("AlertLogger")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                log_file, 
                maxBytes=5 * 1024 * 1024, # 5MB
                backupCount=3, 
                encoding="utf-8"
            )
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def is_alert_allowed(self, alert_type: str, symbol: str, timeframe: str) -> bool:
        alert_key = f"{symbol}_{alert_type}_{timeframe}"
        now = datetime.now(timezone.utc)
        
        if alert_key in self.last_alerts_time:
            last_sent = self.last_alerts_time[alert_key]
            if now - last_sent < timedelta(minutes=self.alert_cooldown_minutes):
                return False
        
        self.last_alerts_time[alert_key] = now
        return True

    def send_alert(self, alert_type: str, symbol: str, timeframe: str, message: str, extra_data: dict = None, ignore_cooldown=False):
        if not ignore_cooldown and not self.is_alert_allowed(alert_type, symbol, timeframe):
            self.logger.info(f"[SKIP ALERT] تم تجاهل تنبيه مكرر لـ {symbol} ({alert_type}).")
            return False

        timestamp = datetime.now(timezone.utc).isoformat()
        
        alert_payload = {
            "timestamp": timestamp,
            "type": alert_type,
            "symbol": symbol,
            "timeframe": timeframe,
            "message": message,
            "details": extra_data or {}
        }

        self.logger.info(f"[{symbol}] [{timeframe}] {alert_type}: {message}")
        self._update_market_status(new_alert=alert_payload)
        return True

    def update_trades_in_status(self, open_trades: list, closed_trades_history: list = None):
        status_data = self._read_status_file()
        status_data["open_trades"] = open_trades
        status_data["open_trades_count"] = len(open_trades)
        if closed_trades_history is not None:
            status_data["recent_closed_trades"] = closed_trades_history[-5:]
        
        status_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write_status_file(status_data)

    def _read_status_file(self) -> dict:
        default_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "active_alerts_count": 0,
            "recent_alerts": [],
            "open_trades_count": 0,
            "open_trades": [],
            "recent_closed_trades": []
        }
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default_data

        # دالة تحويل أنواع البيانات الخاصة بـ NumPy إلى أنواع Python قياسية
    def _default_converter(self, o):
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
        with open(self.file_path, "w", encoding="utf-8") as f:
            # تم إضافة default=self._default_converter لمنع خطأ TypeError
            json.dump(status_data, f, ensure_ascii=False, indent=4, default=self._default_converter)


    def _update_market_status(self, new_alert: dict):
        status_data = self._read_status_file()
        recent_alerts = status_data.get("recent_alerts", [])
        recent_alerts.insert(0, new_alert)

        status_data["recent_alerts"] = recent_alerts[:self.max_active_alerts]
        status_data["active_alerts_count"] = len(status_data["recent_alerts"])
        status_data["last_updated"] = new_alert["timestamp"]

        self._write_status_file(status_data)

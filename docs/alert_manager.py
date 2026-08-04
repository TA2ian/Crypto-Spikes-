import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
import os


# ==========================================
# 1. كلاس إدارة التنبيهات مع منع التكرار
# ==========================================
class AlertManager:
    """
    مسؤول عن حفظ والتنبيه مع إضافة نظام التبريد (Cooldown) لعدم تكرار الإشعارات.
    """
    def __init__(self, status_file="market_status.json", log_file="alerts.log", max_active_alerts=10, alert_cooldown_minutes=15):
        self.status_file = status_file
        self.max_active_alerts = max_active_alerts
        self.alert_cooldown_minutes = alert_cooldown_minutes
        
        # ذاكرة مؤقتة لتسجيل توقيت آخر تنبيه لكل نوع وعملة
        # { "ATOM-USDT_OVERBOUGHT_WARNING_1h": datetime_object }
        self.last_alerts_time = {}
        
        # إعداد ملف الأرشيف الجانبي (Log Rotation)
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
        """فحص ما إذا كان التنبيه مسموحاً به أم أنه مكرر ضمن فترة التبريد"""
        alert_key = f"{symbol}_{alert_type}_{timeframe}"
        now = datetime.now(timezone.utc)
        
        if alert_key in self.last_alerts_time:
            last_sent = self.last_alerts_time[alert_key]
            # إذا لم تنقض فترة التبريد، يُرفض التنبيه
            if now - last_sent < timedelta(minutes=self.alert_cooldown_minutes):
                return False
        
        # التحديث وتخزين الوقت الحالي للتنبيه المسموح
        self.last_alerts_time[alert_key] = now
        return True

    def send_alert(self, alert_type: str, symbol: str, timeframe: str, message: str, extra_data: dict = None, ignore_cooldown=False):
        """دالة إرسال وتسجيل التنبيهات مع فلترة التكرار"""
        
        # التحقق من منع التكرار (إلا إذا طلب الكود التجاوز عبر ignore_cooldown)
        if not ignore_cooldown and not self.is_alert_allowed(alert_type, symbol, timeframe):
            self.logger.info(f"[SKIP ALERT] تم تجاهل تنبيه مكرر لـ {symbol} ({alert_type}) لتجنب التكرار.")
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

        # أ) أرشفة في ملف alerts.log
        self.logger.info(f"[{symbol}] [{timeframe}] {alert_type}: {message}")

        # ب) تحديث ملف market_status.json
        self._update_market_status(new_alert=alert_payload)
        return True

    def update_trades_in_status(self, open_trades: list, closed_trades_history: list = None):
        """تحديث قسم الصفقات داخل market_status.json"""
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

    def _write_status_file(self, status_data: dict):
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(status_data, f, ensure_ascii=False, indent=4)

    def _update_market_status(self, new_alert: dict):
        status_data = self._read_status_file()
        recent_alerts = status_data.get("recent_alerts", [])
        recent_alerts.insert(0, new_alert)

        status_data["recent_alerts"] = recent_alerts[:self.max_active_alerts]
        status_data["active_alerts_count"] = len(status_data["recent_alerts"])
        status_data["last_updated"] = new_alert["timestamp"]

        self._write_status_file(status_data)


# ==========================================
# 2. كلاس إدارة الصفقات مع منع تكرار الصفقات
# ==========================================
class TradeManager:
    """
    مسؤول عن إدارة دورة حياة الصفقة مع منع فتح صفقات مكررة للعملة ذاتها.
    """
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.open_trades = []
        self.closed_trades = []

    def has_open_trade(self, symbol: str, side: str = None) -> bool:
        """فحص ما إذا كانت هناك صفقة مفتوحة بالفعل لهذه العملة"""
        for trade in self.open_trades:
            if trade["symbol"] == symbol:
                if side is None or trade["side"] == side:
                    return True
        return False

    def open_trade(self, symbol: str, side: str, entry_price: float, tp_price: float, sl_price: float, amount: float):
        """فتح صفقة جديدة بشرط عدم وجود صفقة نشطة لنفس العملة"""
        
        # 1. منع تكرار فتح الصفقة
        if self.has_open_trade(symbol, side):
            print(f"⚠️ [BLOCKED] توجد صفقة مفتوحة بالفعل لـ {symbol} ({side}). تم إلغاء الأمر التلقائي.")
            return None

        trade_id = f"{symbol}_{side}_{int(datetime.now().timestamp())}"
        
        trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "take_profit": tp_price,
            "stop_loss": sl_price,
            "amount": amount,
            "status": "OPEN",
            "opened_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.open_trades.append(trade)
        
        msg = f"🚀 فتح صفقة جديدة [{side}]: {symbol} بسعر {entry_price}$ | TP: {tp_price}$ | SL: {sl_price}$"
        self.alert_manager.send_alert("TRADE_OPENED", symbol, "EXECUTION", msg, trade, ignore_cooldown=True)
        self.alert_manager.update_trades_in_status(self.open_trades, self.closed_trades)
        return trade

    def update_and_check_trades(self, current_prices: dict):
        """فحص الأسعار الحالية وإغلاق الصفقات عند TP/SL"""
        for trade in self.open_trades[:]:
            symbol = trade["symbol"]
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            side = trade["side"]

            hit_tp = (side == "BUY" and current_price >= trade["take_profit"]) or \
                     (side == "SELL" and current_price <= trade["take_profit"])

            hit_sl = (side == "BUY" and current_price <= trade["stop_loss"]) or \
                     (side == "SELL" and current_price >= trade["stop_loss"])

            if hit_tp:
                self._close_trade(trade, current_price, reason="TAKE_PROFIT")
            elif hit_sl:
                self._close_trade(trade, current_price, reason="STOP_LOSS")

    def _close_trade(self, trade: dict, exit_price: float, reason: str):
        """إغلاق الصفقة وحساب PnL"""
        trade["exit_price"] = exit_price
        trade["closed_at"] = datetime.now(timezone.utc).isoformat()
        trade["status"] = f"CLOSED_{reason}"

        if trade["side"] == "BUY":
            pnl_pct = ((exit_price - trade["entry_price"]) / trade["entry_price"]) * 100
        else:
            pnl_pct = ((trade["entry_price"] - exit_price) / trade["entry_price"]) * 100

        trade["pnl_pct"] = round(pnl_pct, 2)

        self.open_trades.remove(trade)
        self.closed_trades.append(trade)

        icon = "🎯" if reason == "TAKE_PROFIT" else "🛑"
        msg = f"{icon} إغلاق صفقة {trade['symbol']} السبب: {reason} | سعر الخروج: {exit_price}$ | النتيجة: {trade['pnl_pct']}%"
        
        self.alert_manager.send_alert("TRADE_CLOSED", trade['symbol'], "EXECUTION", msg, trade, ignore_cooldown=True)
        self.alert_manager.update_trades_in_status(self.open_trades, self.closed_trades)


# ==========================================
# 3. محاكاة اختبار منع التكرار
# ==========================================
class TradingBot:
    def __init__(self):
        # تبريد التنبيهات محدد بـ 15 دقيقة افتراضياً
        self.alert_manager = AlertManager(max_active_alerts=10, alert_cooldown_minutes=15)
        self.trade_manager = TradeManager(self.alert_manager)

    def run_simulation(self):
        print("--- 1. تجربة إرسال تنبيهين متتاليين لنفس العملة ---")
        # التنبيه الأول: ينجح
        res1 = self.alert_manager.send_alert("RSI_HIGH", "ATOM-USDT", "1h", "تنبيه تشبع شرائي أول")
        print(f"التنبيه الأول: {'تم الإرسال ✅' if res1 else 'مُنع ❌'}")

        # التنبيه الثاني فوراً: يتم حظره بسبب Cooldown
        res2 = self.alert_manager.send_alert("RSI_HIGH", "ATOM-USDT", "1h", "تنبيه تشبع شرائي ثاني (تكرار)")
        print(f"التنبيه الثاني: {'تم الإرسال ✅' if res2 else 'مُنع ❌'}")

        print("\n--- 2. تجربة فتح صفقتين متتاليتين لنفس العملة ---")
        # الصفقة الأولى: تنجح
        t1 = self.trade_manager.open_trade("ATOM-USDT", "BUY", 1.35, 1.45, 1.30, 100)
        
        # الصفقة الثانية: تُمحى وتُرفض تلقائياً لأن الأولى ما تزال مفتوحة
        t2 = self.trade_manager.open_trade("ATOM-USDT", "BUY", 1.36, 1.46, 1.31, 100)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run_simulation()

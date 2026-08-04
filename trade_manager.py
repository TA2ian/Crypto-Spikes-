import os
import json
import numpy as np
from datetime import datetime, timezone

class TradeManager:
    def __init__(self, alert_manager=None, status_file="docs/market_status.json", account_balance=1000.0, risk_per_trade_pct=1.0):
        self.alert_manager = alert_manager
        self.status_file = status_file
        self.account_balance = account_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.open_trades = []
        self.closed_trades_history = []
        self.load_state()

    # دالة تحويل أنواع NumPy لتفادي خطأ JSON Serialization
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

    def load_state(self):
        """تحميل الصفقات المفتوحة والسابقة من ملف الحالة"""
        if os.path.exists(self.status_file):
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.open_trades = data.get("open_trades", [])
                    self.closed_trades_history = data.get("recent_closed_trades", [])
            except Exception:
                self.open_trades = []
                self.closed_trades_history = []

    def save_state(self):
        """تحديث الصفقات داخل AlertManager أو حفظها في ملف market_status.json مباشرة"""
        if self.alert_manager:
            self.alert_manager.update_trades_in_status(self.open_trades, self.closed_trades_history)
        else:
            dir_name = os.path.dirname(self.status_file)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            
            data = {}
            if os.path.exists(self.status_file):
                try:
                    with open(self.status_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            data["open_trades"] = self.open_trades
            data["open_trades_count"] = len(self.open_trades)
            data["recent_closed_trades"] = self.closed_trades_history[-5:]
            data["last_updated"] = datetime.now(timezone.utc).isoformat()

            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4, default=self._default_converter)

    def open_trade(
        self,
        symbol: str = "UNKNOWN",
        timeframe: str = "1h",
        strategy_name: str = "Automated Signal",
        entry_price: float = 0.0,
        stop_loss: float = 0.0,
        target_1: float = 0.0,
        target_2: float = 0.0,
        side: str = "BUY",
        **kwargs
    ):
        """
        فتح صفقة تلقائية مطابقة تماماً للمستدعيات الواردة من scanner.py
        """
        # استخراج القيم التي يرسلها scanner.py بمرونة عالية
        symbol = kwargs.get("symbol", symbol)
        side = kwargs.get("side", side)
        entry_price = float(kwargs.get("entry_price", entry_price))
        
        # استخراج الستوب لوس سواء كان sl_price أو stop_loss
        sl_val = kwargs.get("sl_price", kwargs.get("stop_loss", stop_loss))
        stop_loss = float(sl_val) if sl_val else 0.0
        
        # استخراج أهداف أرباح الصفقة (tp_price أو target_2 / target_1)
        tp1_val = kwargs.get("tp_price", kwargs.get("target_1", target_1))
        tp2_val = kwargs.get("tp_2", kwargs.get("target_2", target_2))
        
        target_1 = float(tp1_val) if tp1_val else (entry_price * 1.02 if entry_price else 0.0)
        target_2 = float(tp2_val) if tp2_val else (entry_price * 1.05 if entry_price else 0.0)

        timeframe = kwargs.get("timeframe", timeframe)
        strategy_name = kwargs.get("strategy_name", strategy_name)

        # تخصيص إعدادات الستوب المتحرك إن وجدت
        use_trailing = kwargs.get("use_trailing", False)
        trailing_act = kwargs.get("trailing_activation_pct", 1.5)
        trailing_cb = kwargs.get("trailing_callback_pct", 1.0)

        # تجنب فتح صفقة مكررة لنفس العملة على نفس الفريم
        for trade in self.open_trades:
            if trade.get('symbol') == symbol and trade.get('timeframe') == timeframe and trade.get('status') == "OPEN":
                return False

        # حساب إدارة المخاطر وحجم الصفقة
        risk_amount = self.account_balance * (self.risk_per_trade_pct / 100.0)
        price_risk = abs(entry_price - stop_loss) if entry_price and stop_loss else 0.0
        position_size = (risk_amount / price_risk) if price_risk > 0 else 0.0

        trade_payload = {
            "id": f"{symbol}_{timeframe}_{int(datetime.now(timezone.utc).timestamp())}",
            "symbol": symbol,
            "side": side,
            "timeframe": timeframe,
            "strategy": strategy_name,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "initial_stop_loss": stop_loss,
            "target_1": target_1,
            "target_2": target_2,
            "position_size": position_size,
            "use_trailing": use_trailing,
            "trailing_activation_pct": trailing_act,
            "trailing_callback_pct": trailing_cb,
            "status": "OPEN",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "t1_hit": False
        }

        self.open_trades.append(trade_payload)
        self.save_state()

        if self.alert_manager:
            msg = f"🚀 فتح صفقة تلقائية جديدة ({side}) | السعر: ${entry_price:.4f} | الستوب: ${stop_loss:.4f} | الهدف: ${target_1:.4f}"
            self.alert_manager.send_alert("TRADE_OPEN", symbol, timeframe, msg, extra_data=trade_payload, ignore_cooldown=True)

        return True

    def update_and_check_trades(self, current_prices: dict):
        """متابعة الصفقات المفتوحة وتحديث الستوب المتحرك أو إغلاقها عند الأهداف"""
        updated = False
        remaining_trades = []

        for trade in self.open_trades:
            symbol = trade['symbol']
            if symbol not in current_prices:
                remaining_trades.append(trade)
                continue

            current_price = current_prices[symbol]
            timeframe = trade['timeframe']

            # 1. التحقق من ضرب وقف الخسارة (Stop Loss)
            if current_price <= trade['stop_loss']:
                trade['status'] = "CLOSED_SL"
                trade['closed_at'] = datetime.now(timezone.utc).isoformat()
                trade['exit_price'] = float(current_price)
                self.closed_trades_history.append(trade)
                updated = True

                if self.alert_manager:
                    msg = f"❌ تم ضرب وقف الخسارة عند ${current_price:.4f}"
                    self.alert_manager.send_alert("TRADE_SL", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)
                continue

            # 2. التحقق من الهدف الأول (T1) تحريك الستوب إلى سعر الدخول (Break Even)
            if not trade['t1_hit'] and current_price >= trade['target_1']:
                trade['t1_hit'] = True
                trade['stop_loss'] = trade['entry_price']  # تحريك الستوب للدخول
                updated = True

                if self.alert_manager:
                    msg = f"🎯 تم تحقيق الهدف الأول (T1) عند ${current_price:.4f} | رفع الستوب ونقل نقطة التعادل"
                    self.alert_manager.send_alert("TRADE_T1", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)

            # 3. التحقق من الهدف الثاني (T2) وإغلاق الصفقة بنجاح
            if current_price >= trade['target_2']:
                trade['status'] = "CLOSED_TP2"
                trade['closed_at'] = datetime.now(timezone.utc).isoformat()
                trade['exit_price'] = float(current_price)
                self.closed_trades_history.append(trade)
                updated = True

                if self.alert_manager:
                    msg = f"🏆 تم تحقيق الهدف الثاني بالكامل (T2) عند ${current_price:.4f}!"
                    self.alert_manager.send_alert("TRADE_TP2", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)
                continue

            remaining_trades.append(trade)

        if updated:
            self.open_trades = remaining_trades
            self.save_state()

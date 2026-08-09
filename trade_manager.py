import os
import json
import numpy as np
from datetime import datetime, timezone

class TradeManager:
    """
    مُحرك إدارة الصفقات المتقدم (Trade Manager)
    يدعم آلة الحالات (State Machine) لجميع المراحل من NEW_SIGNAL إلى CLOSED
    ويدعم تتبع المتوسط المرجح للدخول (Weighted Average Entry) وتعدد الأهداف والخطط الـ 8.
    """
    def __init__(self, alert_manager=None, status_file="docs/market_status.json", account_balance=1000.0, risk_per_trade_pct=1.0):
        self.alert_manager = alert_manager
        self.status_file = status_file
        self.account_balance = account_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.open_trades = []
        self.closed_trades_history = []
        self.load_state()

    def _default_converter(self, o):
        """دالة تحويل أنواع NumPy لتفادي خطأ JSON Serialization"""
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
            data["recent_closed_trades"] = self.closed_trades_history[-10:]
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
        target_3: float = 0.0,
        target_4: float = 0.0,
        side: str = "BUY",
        plan_id: str = "PLAN_1",
        **kwargs
    ):
        """
        فتح صفقة تلقائية متوافقة مع هيكل البيانات وآلة الحالات الجديدة
        """
        now_str = datetime.now(timezone.utc).isoformat()

        # استخراج وتدقيق البيانات المرنة
        symbol = kwargs.get("symbol", symbol)
        side = kwargs.get("side", side)
        entry_price = float(kwargs.get("entry_price", entry_price))
        plan_id = kwargs.get("plan_id", plan_id)
        
        sl_val = kwargs.get("sl_price", kwargs.get("stop_loss", stop_loss))
        stop_loss = float(sl_val) if sl_val else 0.0

        # استخراج الأهداف الأربعة
        tp1 = float(kwargs.get("tp_1", kwargs.get("target_1", target_1))) or (entry_price * 1.02 if entry_price else 0.0)
        tp2 = float(kwargs.get("tp_2", kwargs.get("target_2", target_2))) or (entry_price * 1.04 if entry_price else 0.0)
        tp3 = float(kwargs.get("tp_3", kwargs.get("target_3", target_3))) or (entry_price * 1.06 if entry_price else 0.0)
        tp4 = float(kwargs.get("tp_4", kwargs.get("target_4", target_4))) or (entry_price * 1.08 if entry_price else 0.0)

        timeframe = kwargs.get("timeframe", timeframe)
        strategy_name = kwargs.get("strategy_name", strategy_name)

        use_trailing = kwargs.get("use_trailing", False)
        trailing_act = float(kwargs.get("trailing_activation_pct", 1.5))
        trailing_cb = float(kwargs.get("trailing_callback_pct", 1.0))

        # تفادي فتح صفقة مكررة لنفس العملة على نفس الفريم ونفس الخطة
        for trade in self.open_trades:
            if trade.get('symbol') == symbol and trade.get('timeframe') == timeframe and trade.get('plan_id') == plan_id and trade.get('status') == "OPEN":
                return False

        # حساب إدارة المخاطر وحجم الصفقة الأولية
        risk_amount = self.account_balance * (self.risk_per_trade_pct / 100.0)
        price_risk = abs(entry_price - stop_loss) if entry_price and stop_loss else 0.0
        position_size = (risk_amount / price_risk) if price_risk > 0 else 0.0

        trade_id = f"{plan_id}_{symbol}_{timeframe}_{int(datetime.now(timezone.utc).timestamp())}"

        # كائن الصفقة الجديد المطور (Data Schema)
        trade_payload = {
            "id": trade_id,
            "trade_id": trade_id,
            "plan_id": plan_id,
            "symbol": symbol,
            "side": side,
            "timeframe": timeframe,
            "strategy": strategy_name,
            
            # --- آلة الحالات والزمن ---
            "current_stage": "WAITING_ENTRY",
            "status": "OPEN",
            "first_detection_time": now_str,
            "opened_at": now_str,
            "last_update_time": now_str,

            # --- أسعار ومتوسطات الدخول ---
            "original_entry": entry_price,
            "first_entry_price": entry_price,
            "best_entry": entry_price,
            "average_entry": entry_price,
            "entry_price": entry_price,  # للتوافقية العكسية
            "retest_count": 0,
            "position_size": position_size,
            "position_size_coin": position_size,
            "total_invested_usdt": round(entry_price * position_size, 2),

            # --- سجل عمليات الدخول ---
            "entry_fills": [
                {
                    "timestamp": now_str,
                    "price": entry_price,
                    "amount": position_size,
                    "type": "FIRST_ENTRY"
                }
            ],

            # --- إدارة المخاطر والأهداف ---
            "initial_stop_loss": stop_loss,
            "stop_loss": stop_loss,
            "current_stop_loss": stop_loss,
            
            "targets": {
                "TP1": {"price": tp1, "hit": False, "hit_time": None, "close_pct": 25},
                "TP2": {"price": tp2, "hit": False, "hit_time": None, "close_pct": 25},
                "TP3": {"price": tp3, "hit": False, "hit_time": None, "close_pct": 25},
                "TP4": {"price": tp4, "hit": False, "hit_time": None, "close_pct": 25}
            },

            # للتوافقية مع الأنظمة القديمة
            "target_1": tp1,
            "target_2": tp2,
            "target_3": tp3,
            "target_4": tp4,
            "t1_hit": False,

            # --- التتبع المتحرك (Trailing Config) ---
            "use_trailing": use_trailing,
            "trailing_config": {
                "is_active": False,
                "activation_pct": trailing_act,
                "callback_pct": trailing_cb,
                "highest_price_seen": entry_price,
                "current_trailing_sl": None
            }
        }

        self.open_trades.append(trade_payload)
        self.save_state()

        if self.alert_manager:
            msg = f"🆕 إشارة جديدة [{plan_id}] ({side}) | العملة: {symbol} | منطقة الدخول: ${entry_price:.4f} | الستوب: ${stop_loss:.4f}"
            self.alert_manager.send_alert("NEW_SIGNAL", symbol, timeframe, msg, extra_data=trade_payload, ignore_cooldown=True)

        return True

    def register_retest_entry(self, trade_id: str, fill_price: float, fill_amount: float):
        """
        تسجيل دخول جديد/إعادة اختبار (RETEST_ENTRY) وإعادة حساب المتوسط المرجح للدخول
        """
        now_str = datetime.now(timezone.utc).isoformat()
        updated_trade = None

        for trade in self.open_trades:
            if trade.get("id") == trade_id or trade.get("trade_id") == trade_id:
                # 1. إضافة التنفيذ الجديد
                trade["entry_fills"].append({
                    "timestamp": now_str,
                    "price": fill_price,
                    "amount": fill_amount,
                    "type": "RETEST_ENTRY"
                })

                # 2. تحديث العداد وأفضل سعر دخول
                trade["retest_count"] = trade.get("retest_count", 0) + 1
                if fill_price < trade.get("best_entry", fill_price):
                    trade["best_entry"] = fill_price

                # 3. إعادة حساب المتوسط المرجح (Weighted Average Entry)
                total_cost = sum(f["price"] * f["amount"] for f in trade["entry_fills"])
                total_volume = sum(f["amount"] for f in trade["entry_fills"])

                new_avg = round(total_cost / total_volume, 4) if total_volume > 0 else fill_price
                trade["average_entry"] = new_avg
                trade["entry_price"] = new_avg  # للتوافقية
                trade["position_size"] = total_volume
                trade["position_size_coin"] = total_volume
                trade["total_invested_usdt"] = round(total_cost, 2)
                trade["current_stage"] = "RETEST_ENTRY"
                trade["last_update_time"] = now_str

                updated_trade = trade
                break

        if updated_trade:
            self.save_state()
            if self.alert_manager:
                msg = f"🔄 إعادة اختبار وتنعيم الدخول (Retest #{updated_trade['retest_count']}) | السعر: ${fill_price:.4f} | المتوسط الجديد: ${updated_trade['average_entry']:.4f}"
                self.alert_manager.send_alert("RETEST_ENTRY", updated_trade["symbol"], updated_trade["timeframe"], msg, extra_data=updated_trade, ignore_cooldown=True)

        return updated_trade

    def update_and_check_trades(self, current_prices: dict):
        """
        متابعة الصفقات المفتوحة طبقاً لآلة الحالات (State Machine) وتحديث الأهداف والستوب المتحرك
        """
        updated = False
        remaining_trades = []
        now_str = datetime.now(timezone.utc).isoformat()

        for trade in self.open_trades:
            symbol = trade['symbol']
            if symbol not in current_prices:
                remaining_trades.append(trade)
                continue

            current_price = float(current_prices[symbol])
            timeframe = trade['timeframe']
            stage = trade.get("current_stage", "WAITING_ENTRY")
            avg_entry = trade.get("average_entry", trade.get("entry_price", 0.0))
            current_sl = trade.get("current_stop_loss", trade.get("stop_loss", 0.0))

            # تحديث أقصى سعر تم الوصول إليه لنسب التتبع
            trailing_cfg = trade.get("trailing_config", {})
            if current_price > trailing_cfg.get("highest_price_seen", avg_entry):
                trailing_cfg["highest_price_seen"] = current_price
                trade["trailing_config"] = trailing_cfg

            # --- (أ) الانتقال من WAITING_ENTRY إلى FIRST_ENTRY / ACTIVE ---
            if stage == "WAITING_ENTRY":
                original_entry = trade.get(
                    "original_entry",
                    trade.get(
                        "entry_price",
                        trade.get("entry"),
                    ),
                )

                if original_entry is None:
                    continue

                original_entry = float(original_entry)
                trade["original_entry"] = original_entry

                if current_price <= original_entry * 1.002:
                    trade["current_stage"] = "FIRST_ENTRY"
                    trade["last_update_time"] = now_str
                    updated = True

                    if self.alert_manager:
                        msg = (
                            f"⚡ تفعيل الدخول الأول "
                            f"(FIRST_ENTRY) عند ${current_price:.4f}"
                        )
                        self.alert_manager.send_alert(
                            "FIRST_ENTRY",
                            symbol,
                            timeframe,
                            msg,
                            extra_data=trade,
                            ignore_cooldown=True,
                        )

                    remaining_trades.append(trade)
                    continue

            # --- (ب) التحقق من ضرب وقف الخسارة (Stop Loss) ---
            if current_price <= current_sl:
                trade['status'] = "CLOSED"
                trade['current_stage'] = "CLOSED_SL"
                trade['closed_at'] = now_str
                trade['last_update_time'] = now_str
                trade['exit_price'] = current_price
                self.closed_trades_history.append(trade)
                updated = True

                if self.alert_manager:
                    msg = f"❌ تم إغلاق الصفقة على ضرب الستوب لوس عند ${current_price:.4f}"
                    self.alert_manager.send_alert("TRADE_SL", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)
                continue

            # --- (ج) الانتقال لـ ACTIVE إذا ابتعد السعر صعوداً عن الدخول ---
            if stage in ["FIRST_ENTRY", "RETEST_ENTRY"] and current_price >= avg_entry * 1.005:
                trade["current_stage"] = "ACTIVE"
                trade["last_update_time"] = now_str
                updated = True

            # --- (د) فحص وتتبع الأهداف الأربعة (TP1 -> TP4) ---
            targets = trade.get("targets", {})

            # 1. الهدف الأول TP1
            tp1_data = targets.get("TP1", {})
            if not tp1_data.get("hit") and current_price >= tp1_data.get("price", trade.get("target_1", 0.0)):
                tp1_data["hit"] = True
                tp1_data["hit_time"] = now_str
                trade["current_stage"] = "TP1_REACHED"
                trade["t1_hit"] = True
                
                # رفع الستوب إلى سعر الدخول Breakeven
                trade["current_stop_loss"] = avg_entry
                trade["stop_loss"] = avg_entry
                trade["last_update_time"] = now_str
                updated = True

                if self.alert_manager:
                    msg = f"🎯 تحقيق Target 1 عند ${current_price:.4f} | رفع الستوب لـ Breakeven (${avg_entry:.4f})"
                    self.alert_manager.send_alert("TRADE_T1", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)

            # 2. الهدف الثاني TP2
            tp2_data = targets.get("TP2", {})
            if tp1_data.get("hit") and not tp2_data.get("hit") and current_price >= tp2_data.get("price", trade.get("target_2", 0.0)):
                tp2_data["hit"] = True
                tp2_data["hit_time"] = now_str
                trade["current_stage"] = "TP2_REACHED"
                
                # رفع الستوب لـ TP1
                trade["current_stop_loss"] = tp1_data.get("price", avg_entry)
                trade["stop_loss"] = trade["current_stop_loss"]
                trade["last_update_time"] = now_str
                updated = True

                if self.alert_manager:
                    msg = f"🏆 تحقيق Target 2 عند ${current_price:.4f} | رفع الستوب لحماية أرباح TP1"
                    self.alert_manager.send_alert("TRADE_TP2", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)

            # 3. الهدف الثالث TP3
            tp3_data = targets.get("TP3", {})
            if tp2_data.get("hit") and not tp3_data.get("hit") and current_price >= tp3_data.get("price", trade.get("target_3", 0.0)):
                tp3_data["hit"] = True
                tp3_data["hit_time"] = now_str
                trade["current_stage"] = "TP3_REACHED"
                
                # رفع الستوب لـ TP2
                trade["current_stop_loss"] = tp2_data.get("price", avg_entry)
                trade["stop_loss"] = trade["current_stop_loss"]
                trade["last_update_time"] = now_str
                updated = True

                if self.alert_manager:
                    msg = f"🚀 تحقيق Target 3 عند ${current_price:.4f} | رفع الستوب لحماية أرباح TP2"
                    self.alert_manager.send_alert("TRADE_TP3", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)

            # 4. الهدف الرابع TP4 وتفعيل الـ Trailing Stop
            tp4_data = targets.get("TP4", {})
            if tp3_data.get("hit") and not tp4_data.get("hit") and current_price >= tp4_data.get("price", trade.get("target_4", 0.0)):
                tp4_data["hit"] = True
                tp4_data["hit_time"] = now_str
                trade["current_stage"] = "TP4_REACHED"
                
                if trade.get("use_trailing"):
                    trade["current_stage"] = "TRAILING_ACTIVE"
                    trailing_cfg["is_active"] = True
                    trailing_cfg["current_trailing_sl"] = current_price * (1 - trailing_cfg.get("callback_pct", 1.0) / 100.0)
                
                trade["last_update_time"] = now_str
                updated = True

                if self.alert_manager:
                    msg = f"🔥 تحقيق Target 4 بالكامل عند ${current_price:.4f}! تفعيل التتبع المتحرك Trailing Stop"
                    self.alert_manager.send_alert("TRADE_TP4", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)

            # --- (هـ) تتبع Trailing Stop إذا كان مفعّلاً ---
            if trailing_cfg.get("is_active"):
                high_p = trailing_cfg.get("highest_price_seen", current_price)
                cb_pct = trailing_cfg.get("callback_pct", 1.0) / 100.0
                new_trailing_sl = high_p * (1 - cb_pct)
                
                if trailing_cfg.get("current_trailing_sl") is None or new_trailing_sl > trailing_cfg["current_trailing_sl"]:
                    trailing_cfg["current_trailing_sl"] = new_trailing_sl

                # فحص الخروج بالتتبع المتحرك
                if current_price <= trailing_cfg["current_trailing_sl"]:
                    trade['status'] = "CLOSED"
                    trade['current_stage'] = "CLOSED_TP"
                    trade['closed_at'] = now_str
                    trade['last_update_time'] = now_str
                    trade['exit_price'] = current_price
                    self.closed_trades_history.append(trade)
                    updated = True

                    if self.alert_manager:
                        msg = f"💰 إغلاق ممتاز بالتتبع المتحرك (Trailing Stop) عند ${current_price:.4f}"
                        self.alert_manager.send_alert("TRADE_CLOSED_TRAILING", symbol, timeframe, msg, extra_data=trade, ignore_cooldown=True)
                    continue

            remaining_trades.append(trade)

        if updated:
            self.open_trades = remaining_trades
            self.save_state()

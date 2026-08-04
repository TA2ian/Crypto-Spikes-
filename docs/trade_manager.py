from datetime import datetime, timezone
from alert_manager import AlertManager


class TradeManager:
    def __init__(self, alert_manager: AlertManager, account_balance: float = 1000.0, risk_per_trade_pct: float = 1.0):
        self.alert_manager = alert_manager
        self.account_balance = account_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.open_trades = []
        self.closed_trades = []

    def calculate_position_size(self, entry_price: float, sl_price: float) -> dict:
        if entry_price <= 0 or sl_price <= 0 or entry_price == sl_price:
            return {"position_size_usd": 0, "token_amount": 0, "risk_amount_usd": 0}

        risk_amount_usd = self.account_balance * (self.risk_per_trade_pct / 100.0)
        sl_distance_pct = abs(entry_price - sl_price) / entry_price
        position_size_usd = risk_amount_usd / sl_distance_pct
        token_amount = position_size_usd / entry_price

        return {
            "position_size_usd": round(position_size_usd, 2),
            "token_amount": round(token_amount, 4),
            "risk_amount_usd": round(risk_amount_usd, 2),
            "sl_distance_pct": round(sl_distance_pct * 100, 2)
        }

    def has_open_trade(self, symbol: str, side: str = None) -> bool:
        for trade in self.open_trades:
            if trade["symbol"] == symbol:
                if side is None or trade["side"] == side:
                    return True
        return False

    def open_trade(self, symbol: str, side: str, entry_price: float, tp_price: float, sl_price: float, 
                   use_trailing: bool = True, trailing_activation_pct: float = 1.5, trailing_callback_pct: float = 1.0):
        if self.has_open_trade(symbol, side):
            print(f"⚠️ [BLOCKED] توجد صفقة مفتوحة بالفعل لـ {symbol} ({side}).")
            return None

        risk_calc = self.calculate_position_size(entry_price, sl_price)
        position_usd = risk_calc["position_size_usd"]
        token_qty = position_usd / entry_price

        trade_id = f"{symbol}_{side}_{int(datetime.now().timestamp())}"
        
        trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "take_profit": tp_price,
            "stop_loss": sl_price,
            "position_size_usd": position_usd,
            "token_amount": round(token_qty, 4),
            "risk_usd": risk_calc["risk_amount_usd"],
            "use_trailing": use_trailing,
            "trailing_active": False,
            "trailing_activation_pct": trailing_activation_pct,
            "trailing_callback_pct": trailing_callback_pct,
            "peak_price": entry_price,
            "status": "OPEN",
            "opened_at": datetime.now(timezone.utc).isoformat()
        }
        
        self.open_trades.append(trade)
        
        msg = (f"🚀 فتح صفقة [{side}]: {symbol} | الدخول: {entry_price}$ | "
               f"حجم: ${position_usd} | SL الأصلي: {sl_price}$ | Trailing: {'مفعل' if use_trailing else 'غير مفعل'}")
        
        self.alert_manager.send_alert("TRADE_OPENED", symbol, "EXECUTION", msg, trade, ignore_cooldown=True)
        self.alert_manager.update_trades_in_status(self.open_trades, self.closed_trades)
        return trade

    def update_and_check_trades(self, current_prices: dict):
        for trade in self.open_trades[:]:
            symbol = trade["symbol"]
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            side = trade["side"]

            # 1. تحديث منطق الستوب المتحرك Trailing Stop
            if trade.get("use_trailing", False):
                self._update_trailing_stop(trade, current_price)

            # 2. فحص الأهداف والتصفيات
            hit_tp = (side == "BUY" and current_price >= trade["take_profit"]) or \
                     (side == "SELL" and current_price <= trade["take_profit"])

            hit_sl = (side == "BUY" and current_price <= trade["stop_loss"]) or \
                     (side == "SELL" and current_price >= trade["stop_loss"])

            if hit_tp:
                self._close_trade(trade, current_price, reason="TAKE_PROFIT")
            elif hit_sl:
                reason = "TRAILING_STOP" if trade.get("trailing_active") else "STOP_LOSS"
                self._close_trade(trade, current_price, reason=reason)

    def _update_trailing_stop(self, trade: dict, current_price: float):
        side = trade["side"]
        entry = trade["entry_price"]
        activation_pct = trade["trailing_activation_pct"]
        callback_pct = trade["trailing_callback_pct"]

        if side == "BUY":
            pnl_pct = ((current_price - entry) / entry) * 100
            
            # تفعيل Trailing Stop لأول مرة عند تحقق الشرط
            if not trade["trailing_active"] and pnl_pct >= activation_pct:
                trade["trailing_active"] = True
                trade["peak_price"] = current_price
                new_sl = round(current_price * (1 - (callback_pct / 100.0)), 4)
                if new_sl > trade["stop_loss"]:
                    trade["stop_loss"] = new_sl
                    msg = f"⚡ تفعيل Trailing Stop لـ {trade['symbol']}! رفع SL إلى: {new_sl}$ (حجز أرباح)"
                    self.alert_manager.send_alert("TRAILING_ACTIVATED", trade['symbol'], "EXECUTION", msg, trade, ignore_cooldown=True)

            # رفع الستوب عند صعود السعر لأرقام قياسية جديدة
            elif trade["trailing_active"]:
                if current_price > trade["peak_price"]:
                    trade["peak_price"] = current_price
                    new_sl = round(current_price * (1 - (callback_pct / 100.0)), 4)
                    if new_sl > trade["stop_loss"]:
                        trade["stop_loss"] = new_sl
                        msg = f"📈 تحديث الستوب المتحرك لـ {trade['symbol']}: رفع SL إلى {new_sl}$"
                        self.alert_manager.send_alert("TRAILING_UPDATED", trade['symbol'], "EXECUTION", msg, trade, ignore_cooldown=True)

        elif side == "SELL":
            pnl_pct = ((entry - current_price) / entry) * 100
            
            if not trade["trailing_active"] and pnl_pct >= activation_pct:
                trade["trailing_active"] = True
                trade["peak_price"] = current_price
                new_sl = round(current_price * (1 + (callback_pct / 100.0)), 4)
                if new_sl < trade["stop_loss"]:
                    trade["stop_loss"] = new_sl
                    msg = f"⚡ تفعيل Trailing Stop لـ {trade['symbol']}! تعديل SL إلى: {new_sl}$"
                    self.alert_manager.send_alert("TRAILING_ACTIVATED", trade['symbol'], "EXECUTION", msg, trade, ignore_cooldown=True)

            elif trade["trailing_active"]:
                if current_price < trade["peak_price"]:
                    trade["peak_price"] = current_price
                    new_sl = round(current_price * (1 + (callback_pct / 100.0)), 4)
                    if new_sl < trade["stop_loss"]:
                        trade["stop_loss"] = new_sl
                        msg = f"📉 تحديث الستوب المتحرك لـ {trade['symbol']}: تعديل SL إلى {new_sl}$"
                        self.alert_manager.send_alert("TRAILING_UPDATED", trade['symbol'], "EXECUTION", msg, trade, ignore_cooldown=True)

    def _close_trade(self, trade: dict, exit_price: float, reason: str):
        trade["exit_price"] = exit_price
        trade["closed_at"] = datetime.now(timezone.utc).isoformat()
        trade["status"] = f"CLOSED_{reason}"

        if trade["side"] == "BUY":
            pnl_pct = ((exit_price - trade["entry_price"]) / trade["entry_price"]) * 100
        else:
            pnl_pct = ((trade["entry_price"] - exit_price) / trade["entry_price"]) * 100

        pnl_usd = trade["position_size_usd"] * (pnl_pct / 100.0)

        trade["pnl_pct"] = round(pnl_pct, 2)
        trade["pnl_usd"] = round(pnl_usd, 2)

        self.open_trades.remove(trade)
        self.closed_trades.append(trade)

        icon = "🎯" if reason == "TAKE_PROFIT" else ("🛡️" if reason == "TRAILING_STOP" else "🛑")
        msg = f"{icon} إغلاق صفقة {trade['symbol']} | السبب: {reason} | النتيجة: {trade['pnl_pct']}% (${trade['pnl_usd']})"
        
        self.alert_manager.send_alert("TRADE_CLOSED", trade['symbol'], "EXECUTION", msg, trade, ignore_cooldown=True)
        self.alert_manager.update_trades_in_status(self.open_trades, self.closed_trades)

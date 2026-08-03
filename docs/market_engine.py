from alert_manager import AlertManager

class MarketEngine:
    def __init__(self):
        # استدعاء وحدة إدارة التنبيهات
        self.alert_manager = AlertManager(max_active_alerts=10)

    def analyze_market(self):
        # --- محاكاة لجزء تحليل الأسعار والشروط ---
        symbol = "ATOM-USDT"
        rsi = 83.0
        price = 1.356
        level = 1.349
        
        # شرط التنبيه (مثال: تشبع شرائي)
        if rsi > 70:
            msg = f"⚠️ تحذير تشبع شرائي وقرب انعكاس: العملة {symbol} وصلت لمنطقة تشبع مفرط (RSI: {rsi}) بالقرب من Resistance {level}$"
            
            # إرسال التنبيه دون الانشغال بكتابة الملفات
            self.alert_manager.process_alert(
                alert_type="OVERBOUGHT_WARNING",
                symbol=symbol,
                timeframe="1h",
                message=msg,
                extra_data={"rsi": rsi, "price": price, "level": level}
            )

        # --- تنفيذ الأوامر والتداول يحدث هنا دون إعاقة ---
        self.execute_orders()

    def execute_orders(self):
        # منطق فتح وإغلاق الصفقات ينفذ بحرية
        pass

if __name__ == "__main__":
    bot = MarketEngine()
    bot.analyze_market()


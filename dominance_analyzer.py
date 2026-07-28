import pandas as pd

def analyze_market_dominance(btc_d_df: pd.DataFrame, usdt_d_df: pd.DataFrame) -> dict:
    """
    محلل مستقل لهيمنة البيتكوين (BTC.D) والعملات المستقرة (USDT.D)
    لتحديد حالة السوق، موسم العملات، أو المخاطر الكلية.
    """
    analysis = {
        "status": "NEUTRAL",
        "altseason_signal": False,
        "market_crash_warning": False,
        "message": ""
    }

    if btc_d_df is None or usdt_d_df is None or len(btc_d_df) < 15 or len(usdt_d_df) < 15:
        return analysis

    # قراءة آخر إغلاق
    btc_d_last = float(btc_d_df.iloc[-1]["close"])
    btc_d_prev = float(btc_d_df.iloc[-2]["close"])
    
    usdt_d_last = float(usdt_d_df.iloc[-1]["close"])
    usdt_d_prev = float(usdt_d_df.iloc[-2]["close"])

    # 1. سيناريو موسم العملات البديلة (Altseason): هبوط BTC.D مع استقرار أو هبوط USDT.D
    is_btc_d_falling = btc_d_last < btc_d_prev and btc_d_last < btc_d_df.iloc[-10]["close"]
    is_usdt_d_stable_or_falling = usdt_d_last <= usdt_d_prev

    # 2. سيناريو انهيار السوق أو الخروج للكاش: صعود حاد في USDT.D (هروب السيولة)
    is_usdt_d_surging = usdt_d_last > usdt_d_prev * 1.015 and usdt_d_last > usdt_d_df.iloc[-5]["close"]

    # 3. سيناريو استحواذ البيتكوين العنيف (طرد السيولة من البدائل): صعود BTC.D مع صعود USDT.D
    is_btc_d_dominating = btc_d_last > btc_d_prev * 1.01 and usdt_d_last > usdt_d_prev

    if is_btc_d_falling and is_usdt_d_stable_or_falling:
        analysis["altseason_signal"] = True
        analysis["status"] = "ALTSEASON_MODE"
        analysis["message"] = (
            f"🚀 **مؤشر سيولة إيجابي (موسم البدائل):**\n"
            f"• هيمنة البيتكوين `BTC.D` تتراجع (`{btc_d_last:.2f}%`).\n"
            f"• هيمنة المستقرة `USDT.D` مستقرة أو تتراجع (`{usdt_d_last:.2f}%`).\n"
            f"💡 *التفسير:* السيولة تتدفق بسلاسة من البيتكوين نحو العملات البديلة (فرص شراء قوية للبدائل)."
        )
    elif is_usdt_d_surging:
        analysis["market_crash_warning"] = True
        analysis["status"] = "RISK_OFF_CRASH"
        analysis["message"] = (
            f"🚨 **تحذير هيكلي عام (هروب إلى الكاش):**\n"
            f"• هيمنة المستقرة `USDT.D` تقفز بقوة لتصل إلى `{usdt_d_last:.2f}%`.\n"
            f"💡 *التفسير:* المستثمرون يبيعون الأصول ويحولونها إلى كاش (مخاطر هبوط عامة في السوق، تجنب صفقات الشراء الجديدة)."
        )
    elif is_btc_d_dominating:
        analysis["status"] = "BTC_SQUEEZE"
        analysis["message"] = (
            f"⚠️ **تحذير سيطرة البيتكوين:**\n"
            f"• `BTC.D` ترتفع بقوة (`{btc_d_last:.2f}%`) بالتزامن مع صعود `USDT.D` (`{usdt_d_last:.2f}%`).\n"
            f"💡 *التفسير:* سحب السيولة من العملات البديلة ووضعها في البيتكوين أو الكاش (اضغط على صفقة البدائل بحذر)."
        )

    return analysis


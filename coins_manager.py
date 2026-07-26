import json
import os
import threading

WATCHLIST_FILE = "user_watchlists.json"
file_lock = threading.Lock()  # قفل لحماية البيانات أثناء المعالجة المتوازية

# القائمة الافتراضية لأي مستخدم جديد يفتح البوت لأول مرة
DEFAULT_WATCHLIST = [
    "BTC-USDT",
    "ETH-USDT",
    "BNB-USDT",
    "XRP-USDT",
    "SOL-USDT",
    "TRX-USDT",
    "ZEC-USDT",
    "XLM-USDT",
    "XMR-USDT",
    "ADA-USDT",
    "LINK-USDT",
    "BCH-USDT",
    "GRAM-USDT",
    "LTC-USDT",
    "SUI-USDT",
    "AVAX-USDT",
    "NEAR-USDT",
    "TAO-USDT",
    "DOT-USDT",
    "WLD-USDT",
    "ICP-USDT",
    "ETC-USDT",
    "POL-USDT",
    "ATOM-USDT",
    "QNT-USDT",
    "UB-USDT",
    "AIO-USDT",
    "H-USDT",
    "XLM-USDT",
    "HBAR-USDT",
    "AKE-USDT",
    "ZAMA-USDT",
    "GWEI-USDT",
    "PYTH-USDT",
    "DGB-USDT",
    "XAUT-USDT",
    "KITE-USDT",
    "ORDI-USDT",
    "RENDER-USDT",
    "FET-USDT",
    "XTZ-USDT",
    "ARB-USDT",
    "ATOM-USDT",
    "AVAX-USDT",
    "DCR-USDT",
    "ZEN-USDT",
]

def load_all_watchlists() -> dict:
    """تحميل قوائم كل المستخدمين من الملف مع حماية التزامن"""
    with file_lock:
        if os.path.exists(WATCHLIST_FILE):
            try:
                with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

def save_all_watchlists(data: dict):
    """حفظ قوائم كل المستخدمين في الملف"""
    with file_lock:
        try:
            with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[خطأ] فشل حفظ القوائم: {e}")

def get_user_watchlist(user_id) -> list:
    """جلب قائمة العملات الخاصة بمستخدم معين"""
    user_id_str = str(user_id)
    all_data = load_all_watchlists()
    if user_id_str in all_data:
        return all_data[user_id_str]
    return DEFAULT_WATCHLIST.copy()

def add_coin_for_user(user_id, symbol: str) -> str:
    """إضافة عملة لقائمة المستخدم الخاصة"""
    user_id_str = str(user_id)
    symbol = symbol.upper().strip()
    if "/" not in symbol:
        symbol = f"{symbol}/USDT"
    
    all_data = load_all_watchlists()
    user_list = all_data.get(user_id_str, DEFAULT_WATCHLIST.copy())
    
    if symbol in user_list:
        return f"⚠️ العملة <code>{symbol}</code> موجودة مسبقاً في قائمتك الخاصة."
    
    user_list.append(symbol)
    all_data[user_id_str] = user_list
    save_all_watchlists(all_data)
    return f"✅ تم إضافة العملة <code>{symbol}</code> إلى قائمتك الخاصة بنجاح."

def remove_coin_from_user(user_id, symbol: str) -> str:
    """حذف عملة من قائمة المستخدم الخاصة"""
    user_id_str = str(user_id)
    symbol = symbol.upper().strip()
    if "/" not in symbol and not symbol.endswith("-USDT"):
        symbol = f"{symbol}/USDT"
    
    all_data = load_all_watchlists()
    user_list = all_data.get(user_id_str, DEFAULT_WATCHLIST.copy())
    
    if symbol in user_list:
        user_list.remove(symbol)
        all_data[user_id_str] = user_list
        save_all_watchlists(all_data)
        return f"🗑 تمت إزالة العملة <code>{symbol}</code> من قائمتك الخاصة بنجاح."
    
    # مطابقة جزئية في حال كتب الرمز بدون شرطة
    for item in user_list:
        if symbol.replace("/", "") in item.replace("/", ""):
            user_list.remove(item)
            all_data[user_id_str] = user_list
            save_all_watchlists(all_data)
            return f"🗑 تمت إزالة العملة <code>{item}</code> من قائمتك الخاصة بنجاح."

    return f"❌ العملة <code>{symbol}</code> غير موجودة في قائمتك الخاصة."

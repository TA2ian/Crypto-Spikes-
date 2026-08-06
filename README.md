🚀 Crypto Spikes - Engine & Live Dashboard
نظام آلي متكامل לרصد إشارات التداول على العملات الرقمية عبر الأطر الزمنية المختلفة، إدارة الصفقات وفق آلة الحالات (State Machine)، تتبع الأهداف الهيكلية الخمسة والستوب المتحرك، ومزامنة النتائج لحظياً مع لوحة تحكم تفاعلية مستضافة على Netlify.
🌟 المميزات الرئيسية
 * رصد متعدد الأطر الزمنية (scanner.py): مسح الأسواق وتحليل السيولة وانحرافات مؤشر القوة النسبية (Divergences) وارتفاعات الأحجام (Volume Spikes) بناءً على الخطط الفنية الثمانية.
 * إدارة الصفقات والمخاطر (trade_manager.py):
   * حساب حجم العقود (Position Sizing): تحديد حجم الصفقة والقيمة بالدولار تلقائياً استناداً إلى نسبة المخاطرة المحددة ورصيد المحفظة.
   * آلة الحالات (State Machine): تتبع مراحل الصفقة من الدخول الأول (FIRST_ENTRY) إلى إعادة الاختبار (RETEST) وحتى تحقق الأهداف.
   * الستوب المتحرك الذكي (Dynamic Trailing Stop): حجز الأرباح تلقائياً عند تجاوز السعر لنسبة الربح المحددة وتحديث وقف الخسارة صعوداً.
   * منع التكرار (Deduplication): تصفية الإشارات لمنع فتح صفقات مكررة لنفس العملة والخطة الفنية.
   * دعم المعاملات المرنة (**kwargs): مرونة كاملة لمنع أخطاء التوافقية (TypeError) عند استلام معاملات الأهداف من السكربت الرئيسي.
 * إشعارات وتنبيهات فورية (alert_manager.py): إرسال تنبيهات لحظية عبر Telegram عند فتح الصفقة، تحقق الأهداف (TP1 إلى Macro Target)، أو الإغلاق.
 * تحديث لوحة الويب بدون كاش (Netlify Dashboard Sync): جلب البيانات مباشرة من GitHub Raw مع خاصية منع التخزين المؤقت (Cache Busting) لتفادي توقف تحديثات الواجهة ودون استهلاك دقائق بناء Netlify.
📁 هيكلية المشروع
├── main.py                 # السكربت الرئيسي لتشغيل المحرك وتنسيق دورة الفحص
├── scanner.py              # وحدة فحص الأسواق واستخراج الإشارات والأنماط
├── trade_manager.py        # وحدة إدارة دورة حياة الصفقات والمخاطر والستوب المتحرك
├── alert_manager.py        # وحدة إرسال التنبيهات عبر تلغرام والمنصات
├── market_status.json      # ملف البيانات المحدث لحظياً لنتائج الفحص والصفقات
├── docs/
│   └── market_status.json  # النسخة المستهدفة للعرض المباشر على لوحة Netlify
├── index.html              # لوحة التحكم التفاعلية للواجهة (Netlify Frontend)
└── .github/
    └── workflows/
        └── scanner.yml     # أتمتة التشغيل والرفع التلقائي عبر GitHub Actions

⚙️ التثبيت والتشغيل المحلي
1. استنساخ المستودع وتثبيت المكتبات
git clone https://github.com/TA2ian/Crypto-Spikes.git
cd Crypto-Spikes
pip install -r requirements.txt

2. إعداد متغيرات البيئة (.env)
قم بإنشاء ملف .env في المجلد الرئيسي واضبط الإعدادات التالية:
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ACCOUNT_BALANCE=1000.0
RISK_PER_TRADE_PCT=1.0

3. تشغيل المحرك
python main.py

🌐 إعداد لوحة الويب Netlify
لضمان تحديث لوحة الويب فورياً ودون الحاجة لإعادة بناء (Rebuild) الموقع على Netlify:
 * يقوم السكربت الرئيسي main.py برفع docs/market_status.json تلقائياً إلى GitHub بعد كل دورة فحص.
 * تقرأ صفحة الويب (index.html / app.js) الملف مباشرة من رابط Raw الخاص بـ GitHub باستخدام طابع زمني لمنع التخزين المؤقت (Cache Busting):
const githubUsername = "TA2ian";
const repoName = "اسم_المستودع";
const branch = "main";

const url = `https://raw.githubusercontent.com/${githubUsername}/${repoName}/${branch}/docs/market_status.json?t=${Date.now()}`;

fetch(url)
  .then(res => res.json())
  .then(data => updateUI(data));

📊 دورة حياة الصفقة (Trade Lifecycle)
[إشارة جديدة] ──> [حساب حجم الصفقة وفتحها] ──> [تفعيل الستوب المتحرك]
                               │
                               ├──> 🎯 TP1 / TP2 / TP3 / TP4 ──> [تنبيهات Telegram]
                               └──> 👑 Macro Target / Trailing SL ──> [إغلاق وتحديث الحساب]

📄 الترخيص
هذا المشروع مخصص للاستخدام الشخصي والتطوير المستمر للنظم البرمجية الخاصة بالتداول الالي.

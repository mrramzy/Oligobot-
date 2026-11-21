# گزارش جلسه — ۲۰۲۶-۰۶-۱۸

**هدف جلسه:** ساخت سیستم اشتراک ماهانه و پنل مدیریت ادمین برای OLIGOBOT V10

محیط مجازیِ پروژه: `D:\Programing\projects\Telegram RAG bot\RAGBot\Scripts\python.exe`

---

## ۱. سیستم اشتراک (Subscription Manager) ✅

**فایل:** `subscription_manager.py` (260 خط)

### تی‌رهای اشتراک

| تی‌ر | سقف روزانه | قیمت ماهانه | ویژگی‌ها |
|------|:---------:|:----------:|---------|
| Free | ۱۰ سوال | رایگان | سوالات متنی، RAG پایه |
| Basic | ۵۰ سوال | ۱۵۰,۰۰۰ تومان | تصویر، سند، RAG کامل، رفرنس |
| Pro | ۲۰۰ سوال | ۳۵۰,۰۰۰ تومان | + اولویت پشتیبانی، پنل متخصص |
| Enterprise | نامحدود | ۸۰۰,۰۰۰ تومان | + API، KB سفارشی |

### قابلیت‌های ادمین (Override System)

- **Test Mode** - دسترسی نامحدود برای تست (مثلاً ۷ روز)
- **Free Access** - دسترسی کامل رایگان (هدیه/تست)
- **Bonus Credits** - اضافه کردن سوال روزانه
- **Tier Override** - تنظیم هر تی‌ر برای هر کاربر

### اولویت کنترل دسترسی
```
ادمین → Override (test/free) → وضعیت اشتراک → سقف روزانه
```

---

## ۲. پنل مدیریت ادمین (Admin Dashboard API) ✅

**فایل:** `admin_api.py` (FastAPI backend, 19 مسیر API)

### مسیرهای API

| مسیر | نوع | توضیح |
|------|:---:|-------|
| `/api/stats` | GET | آمار کلی پلتفرم |
| `/api/users` | GET | لیست تمام کاربران |
| `/api/users/{id}` | GET | جزئیات کاربر |
| `/api/subscription/set` | POST | تنظیم تی‌ر اشتراک |
| `/api/subscription/cancel` | POST | لغو اشتراک |
| `/api/override/set` | POST | تنظیم override ادمین |
| `/api/override/remove` | POST | حذف override |
| `/api/bonus` | POST | اعطای سوالات اضافی |
| `/api/user/notes` | POST | یادداشت ادمین |
| `/api/tiers` | GET | لیست تی‌رها |
| `/api/payment-history` | GET | تاریخچه عملیات |
| `/api/quick/grant-test` | POST | تست رایگان سریع |
| `/api/quick/grant-free` | POST | دسترسی رایگان سریع |
| `/api/quick/give-pro` | POST | اشتراک PRO سریع |

### احراز هویت
- ادمین باید `admin_id` و `secret` را ارسال کند
- secret پیش‌فرض: `oligobot_admin_2026` (قابل تغییر در `.env`)
- فرمت: `ADMIN_SECRET=your_secret_here`

---

## ۳. رابط کاربری داشبورد (Admin Dashboard Frontend) ✅

**فایل:** `admin_dashboard.html` (RTL Farsi UI)

### امکانات
- ورود با Admin ID + Secret Key
- نمایش آمار کلی (کاربران, سوالات امروز, overrides)
- عملیات سریع (تست رایگان, دسترسی رایگان, PRO)
- جدول مدیریت کاربران با جستجو و فیلتر
- مودال جزئیات کاربر (تغییر تی‌ر, یادداشت, لغو)
- تاریخچه عملیات

### نحوه اجرا
```bash
cd "OLIGOBOT V10 beta"
uvicorn admin_api:app --host 0.0.0.0 --port 8080
# باز کردن http://localhost:8080
```

---

## ۴. یکپارچه‌سازی با کد موجود ✅

### تغییرات غیرمخرب

| فایل | تغییر |
|------|-------|
| `handlers.py` | import subscription_manager, `can_user_use()` با تی‌رآگاه, دکمه و دستور `/subscription` |
| `app.py` | import subscription_manager, اضافه کردن `increment_usage()` هماهنگ |
| `config.py` | BTN_SUBSCRIPTION, ADMIN_SECRET, ADMIN_DASHBOARD_PORT |
| `requirements.txt` | fastapi, uvicorn, python-multipart |

### تست‌های انجام شده
- ✅ import subscription_manager
- ✅ import admin_api
- ✅ import handlers
- ✅ تمام تی‌رها با موفقیت بارگذاری شدند
- ✅ دسترسی ادمین تایید شد
- ✅ کاربر جدید با FREE شناسایی شد
- ✅ ۱۹ مسیر API ثبت شد

---

## ۵. فایل‌های جدید و تغییریافته

### فایل‌های جدید
| فایل | سایز | توضیح |
|------|------|-------|
| `subscription_manager.py` | ~260 خط | سیستم اشتراک و کنترل دسترسی |
| `admin_api.py` | ~300 خط | API پنل ادمین (FastAPI) |
| `admin_dashboard.html` | ~400 خط | رابط کاربری داشبورد |

### فایل‌های تغییریافته
| فایل | خطوط تغییر |
|------|------------|
| `handlers.py` | +import, +can_user_use(), +handle_subscription(), +handle_subscription_command() |
| `app.py` | +import, +subscription_manager.increment_usage() در ۲ مکان |
| `config.py` | +BTN_SUBSCRIPTION, +ADMIN_SECRET, +ADMIN_DASHBOARD_PORT |
| `requirements.txt` | +fastapi, +uvicorn, +python-multipart |

---

## ۶. نحوه استفاده

### اجرای ربات (بدون تغییر)
```bash
python app.py
```

### اجرای پنل ادمین (جدید)
```bash
cd "OLIGOBOT V10 beta"
uvicorn admin_api:app --host 0.0.0.0 --port 8080
```

### دستورات تلگرام جدید
- `/subscription` - نمایش وضعیت اشتراک کاربر
- دکمه `💳 اشتراک من` به منوی اصلی اضافه شد

---

## ۷. کارهای بعدی (پیشنهادی)

1. **اضافه کردن درگاه پرداخت** - اتصال به زرین‌پال/آی‌دی‌پی برای پرداخت خودکار
2. **داشبورد مدیریت KB** - مدیریت منابع دانش از پنل
3. **API برای اپلیکیشن موبایل** - دسترسی REST API برای کلاینت‌های خارجی
4. **گزارش‌گیری پیشرفته** - نمودار استفاده, درآمد, رشد کاربران
5. **سیستم دعوت** - کد دعوت برای جذب کاربر جدید

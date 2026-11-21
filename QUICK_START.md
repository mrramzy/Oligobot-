# 🚀 OLIGOBOT V10 - Quick Start Guide

## خلاصه اجرایی (Executive Summary)

```
📊 Project Status: ✅ 72/100 (B Grade)
📦 Dependencies: ✅ All Installed
🐛 Issues Found: 5 Major + 10 Minor
✅ Critical Issues: Handler Functions Missing
⏱️  Time to Fix: ~2-3 hours
```

---

## 🚀 فوری! اولین قدم‌ها

### 1. تأیید نصب (Verify Installation)
```bash
# Activate venv
& "D:/Programing/projects/Telegram RAG bot/RAGBot/Scripts/Activate.ps1"

# Check Python
python --version
# Expected: Python 3.9+

# Check imports
python -c "import langchain; import sentence_transformers; print('✅ All imports OK')"
```

### 2. تغییر API Keys
```bash
# Edit .env file
nano .env

# Required:
TELEGRAM_TOKEN=your_bot_token
OPENAI_API_KEY=your_api_key
# OR GEMINI_API_KEY, DEEPSEEK_API_KEY
```

### 3. دیباگ برای شروع
```bash
python app.py
# Expected output:
# 🚀 OligoSoft Bot Server Starting...
# ✅ Bot is polling for updates...
```

---

## ⚠️ اگر خطا دید (Troubleshooting)

### ❌ "No module named 'sentence_transformers'"
```bash
pip install sentence-transformers
```

### ❌ "handlers has no attribute 'start'"
**مشکل شناسایی شده:** Handler functions ناقص هستند
```python
# حل موقتی در app.py:
# بعد از بخش handlers definition، اضافه کنید:
handlers.start = lambda u, c: None  # Temporary stub
```

### ❌ TELEGRAM_TOKEN خطا
```bash
# بررسی کنید:
cat .env | grep TELEGRAM_TOKEN
# باید value داشته باشد
```

---

## 📋 بررسی سریع (Quick Checklist)

- [ ] Virtual Environment فعال
- [ ] Python 3.9+ (چک: `python --version`)
- [ ] تمام Packages نصب (`pip list | findstr langchain`)
- [ ] .env file تکمیل شده
- [ ] TELEGRAM_TOKEN معتبر
- [ ] API Keys صحیح

---

## 🔧 تنظیم سریع مدل AI

### OpenAI (پیشنهادی)
```env
AI_MODEL=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...
```

### Google Gemini
```env
AI_MODEL=gemini
MODEL_NAME=gemini-pro
GEMINI_API_KEY=...
```

### DeepSeek
```env
AI_MODEL=deepseek
DEEPSEEK_API_KEY=...
```

---

## 📊 درجه‌بندی فوری

| مورد | نمره | وضعیت |
|-----|------|--------|
| معماری | 8.5/10 | ✅ عالی |
| کد | 7/10 | ✅ خوب |
| Dependencies | 9/10 | ✅ عالی |
| Handlers | 2/10 | ⚠️ ناقص |
| Tests | 4/10 | ⚠️ کم |
| Security | 7/10 | ✅ خوب |

**نمره کل: 7.2/10 (B)**

---

## 🎯 نقدهای اصلی

### 🔴 بحرانی (Blocking)
```python
# handlers.py میں یہ functions نیز موجود نہیں:
start()
handle_new_command()
handle_setname_command()
handle_feedback_command()
handle_callback()
```
**حل:** Complete these implementations

### 🟠 مهم (Important)
- Type hints incomplete
- Test coverage minimal
- Hardcoded paths

### 🟡 کم‌اهمیت (Nice-to-have)
- Better documentation
- More error handling
- Additional features

---

## 💻 دستورات مفید

```bash
# Run bot
python app.py

# Run tests
pytest tests/ -v

# Check types
python -m mypy app.py

# Check imports
python -c "import app; print('OK')"

# List packages
pip list | findstr langchain

# Update requirements
pip freeze > requirements_updated.txt
```

---

## 📚 دوکومنت‌های مهم

| فایل | مورد |
|-----|------|
| [CODE_AUDIT_REPORT.md](CODE_AUDIT_REPORT.md) | تحلیل کامل |
| [README_UPDATED.md](README_UPDATED.md) | راهنمای کامل |
| [SUMMARY_FARSI.md](SUMMARY_FARSI.md) | خلاصه فارسی |

---

## 🎓 یادگیری سریع

```python
# مثال ساده - RAG استفاده
from rag_engine import RAGSystem
import asyncio

async def test():
    rag = RAGSystem()
    result = await rag.process_query(
        user_id=1,
        user_query="What is anemia?",
        chat_history=[],
        strategy={"use_rag": True}
    )
    print(result)

asyncio.run(test())
```

---

## ✅ چکلیست قبل از Production

- [ ] تمام handlers تکمیل شده
- [ ] ۸۰% test coverage
- [ ] .env صحیح‌تر
- [ ] Type hints بهتر
- [ ] Monitoring setup
- [ ] Backup system

---

## 🆘 اگر مشکل داشتید

1. **Check logs:** `cat logs/bot.log`
2. **Debug mode:** استفاده کنید `logging.DEBUG`
3. **Test imports:** تک‌تک import کنید
4. **Check env:** `python -c "import os; print(os.getenv('TELEGRAM_TOKEN'))"`
5. **Virtual env:** آیا فعال است؟

---

## 📞 اطلاعات بیشتر

- 📖 [README_UPDATED.md](README_UPDATED.md) - راهنمای مکمل
- 📊 [CODE_AUDIT_REPORT.md](CODE_AUDIT_REPORT.md) - تحلیل تفصیلی
- 🔍 [SUMMARY_FARSI.md](SUMMARY_FARSI.md) - خلاصه فارسی

---

**آخرین بهروزرسانی:** 27 دسامبر 2025  
**وضعیت:** ✅ تقریباً آماده


# نقشه: ایندکس‌کردن اطلس هماتولوژی (Vision-to-Text)

## هدف
دانشِ تصویریِ «Clinical Hematology Atlas» (۲۴MB) را به ایندکس بیاوریم تا قدرت تشخیصِ تصویرِ ربات
چند برابر شود — بدون CLIP/GPU، با همان زیرساخت bge-m3 موجود.

## 📊 یافته‌های probe واقعی (کالیبراسیون)
- اطلس **۲۹۰ صفحه، ۲۷۹ تصویر**، و **۲۰۰ صفحهٔ محتوایی** (تصویر + کلمهٔ FIGURE).
- **هر صفحه دقیقاً ۱ تصویرِ مرکّب** دارد (پنل‌های A/B/C/D) → **واحد کار = صفحه** (نه تصویرِ منفرد).
- متن صفحات بسیار غنی است (FIGURE id + DESCRIPTION + ASSOCIATED WITH) → **لنگرِ ضدتوهمِ عالی**.
- آرتیفکت لیگاتور در متن (fi/fl→`?`, ×→`�`) → پاک‌سازی سبک؛ ولی محتوای ایندکس = کپشنِ تمیزِ LLM.
- **هزینه:** ~۲۰۰ تماس ویژن آروان ≈ ۸–۱۵ هزار تومان یک‌بار، دیسک ~۲۰–۳۰MB، زمان ~۱۵–۳۰ دقیقه.

## تصمیم‌های تأییدشده (کاربر)
- **روش:** Vision-to-Text (هر **صفحه** اطلس → توصیف مورفولوژیک غنی → ایندکس متنی bge-m3).
- **زبان کپشن:** انگلیسی (LLM در فضای انگلیسی مقایسه می‌کند و توصیفات کتاب‌ها هم انگلیسی‌اند؛
  پاسخ نهایی به کاربر فارسی می‌ماند).
- **مدل کپشن‌گذار:** آروان پولی (پروفایل ۲، Gemini-2.5-Flash-lite) — **ماژولار** تا بعداً به MedGemma س��ییچ شود.
- **معماری ایندکس:** توصیف‌های متنیِ اطلس **در همان فضای bge-m3** → ساب‌ایندکس جدا ساخته و با
  `merger_of_indexes.merge_and_save()` در `brain_index` merge می‌شود (دقیقاً الگوی فعلیِ هر کتاب).
  (تصویربه‌تصویرِ آینده با MedSigLIP/BioCLIP = استورِ جدا، خارج از این فاز.)
- **نمایش تصویر به کاربر:** `image_path` در متادیتا ذخیره می‌شود (ماژولار)، ولی **ارسال به کاربر
  فعلاً خاموش** (یک فلگ config برای بعد).

## تکنیک کلیدیِ ضدتوهم
کپشن‌گذار **هم تصویر و هم کپشنِ اصلیِ خودِ اطلس** را می‌گیرد و کپشن را به کلیدواژه‌های مورفولوژیک
بسط می‌دهد (نه تشخیص از صفر) → توهم به‌شدت کم می‌شود.

---

## بخش ۱ — کپشن‌گذارِ ماژولار (`ai_models.py`)
تابع جدید `caption_atlas_image(image, caption_hint: str) -> str`:
- مسیر آروان (`_profile_uses_openai_compat()` + `_openai_compat_client()` + `prof["vision_model"]`) را
  مثل `analyze_image_for_rag` بازاستفاده کن.
- پرامپت (انگلیسی): «تو دانشمند علوم آزمایشگاهی هستی. این تصویرِ اطلس + کپشنِ اصلی‌اش را ببین و یک
  توصیف مورفولوژیکِ غنی و جستجوپذیر (نوع سلول، اندازه، هسته، سیتوپلاسم، رنگ‌آمیزی، inclusions،
  زمینه) به انگلیسی بنویس. فقط آنچه دیده می‌شود؛ کپشن را گسترش بده، تشخیص اختراع نکن.»
- خروجی: یک پاراگراف متنیِ انگلیسی. خطا → رشته‌ی خالی (skip امن).
- **ماژولار بودن:** کل تماسِ مدل در همین یک تابع است؛ سوییچ به MedGemma = تغییر همین تابع.

## بخش ۲ — اسکریپت استخراج+ساخت (`clinical_rag/atlas_ingest.py`)
آینه‌ی `faiss_ingest.py` ولی تصویرمحور. تابع اصلی `ingest_atlas(pdf_path, output_dir="knowledge_base")`:

1. **استخراج تصاویر** با PyMuPDF (`page.get_images(full=True)` + `doc.extract_image`):
   - فیلتر: ت��اویرِ کوچک‌تر از ~۱۵۰×۱۵۰px (لوگو/تزئین) رد شوند.
   - شماره‌ی صفحه با همان `PageNumberTracker` (روی متنِ fitz) — یکدست با کتاب‌ها.
   - کپشن: متنِ صفحه را بخوان، الگوهای `Figure/Fig N-M ...` را به‌عنوان `caption_hint` و `figure_id`
     استخراج کن (نزدیک‌ترین به تصویر؛ اگر نبود، خالی).
2. **ذخیره‌ی تصویر** در `knowledge_base/atlas_images/<safe_figid_or_idx>.png` → `image_path`.
3. **کپشن‌گذاری** با `caption_atlas_image(img, caption_hint)`.
4. **ساخت Document** (هم‌فرمت با schema موجود + `image_path`):
   - `page_content`: `**TYPE: IMAGE**\nPage: {page}\nContext: {section}\n**Contains: {figure_id}**\n**VISUAL_DESC:** {desc}\nCaption: {caption_hint}`
   - `metadata`: `{source:"Clinical Hematology Atlas", chapter, category:"Hematology", page, type:"image", visuals:figure_id, engine:"vision_caption", image_path}`
5. **ذخیره‌ی ساب‌ایندکس** در `knowledge_base/Clinical_Hematology_Atlas/` (نام ASCII):
   `chunks.jsonl` + `index.faiss`+`index.pkl` (با `get_rag_embeddings()`، batch=100) + `bm25_retriever.pkl`
   — عیناً بلوک SAVE در `faiss_ingest.py:558-596`.
6. **Resume‌پذیری:** اگر `chunks.jsonl` از اجرای قبلی هست، تصاویرِ کپشن‌خورده را skip کن (در برابر کرشِ
   وسط batchِ صدها تصویر). پیشرفت لاگ شود.
7. `update_book_aliases` معادل برای اطلس (یا تأیید alias موجود در `book_aliases.json`).

## بخش ۳ — config (فلگ‌های ماژولار)
```python
ATLAS_SEND_IMAGE_TO_USER = os.getenv("ATLAS_SEND_IMAGE_TO_USER", "0") == "1"  # فعلاً خاموش
ATLAS_IMAGES_DIR = os.path.join(BASE_DIR, "knowledge_base", "atlas_images")
```

## بخش ۴ — merge و query
- merge: `merge_and_save()` خودکار پوشه‌ی اطلس را (چون `index.faiss` دارد و بُعدش ۱۰۲۴ است) برمی‌دارد.
  **هیچ تغییری در merger لازم نیست.** کاربر merge را با پنل خودش می‌زند.
- query: مسیر Vision-to-Text (`rag_engine.py:349-374`) از قبل کار می‌کند — عکس کاربر → کلیدواژه →
  جستجو → حالا توصیف‌های اطلس هم در نتایج می‌آیند. **بدون تغییر کد query.**
- citation: `book_aliases.json` باید alias + `citation_format` برای اطلس داشته باشد (طبق گزارش قبلی
  alias اضافه شده؛ تأیید/تکمیل می‌شود).

## بخش ۵ — نمایش تصویر (فقط آماده‌سازی، ارسال خاموش)
`image_path` در متادیتا از merge عبور می‌کند و در `retrieved_docs` در دسترس است. ارسالِ واقعی به
کاربر (یک reply_photo در `handlers.py` پشت فلگ `ATLAS_SEND_IMAGE_TO_USER`) **در این فاز پیاده نمی‌شود**؛
فقط مسیرش باز می‌ماند.

---

## یکپارچگی با پنل (آینده‌نگری)
پنلِ واقعیِ فعلی = `Clinical RAG Manager - v3.0.py` (ریشه). (نسخهٔ `clinical_rag/manager.py` v2.1
منسوخ است و دست‌نخورده ماند — تصمیم کاربر: فقط v3.0 وصل شود.)
- موتور جدید `"ATLAS"` در `decide_index_engine` (نام شامل atlas/rodak → ATLAS).
- `add_source` و `tui_auto_ingest` به `ingest_atlas` روت می‌کنند، سپس `merge_faiss_indexes`.
- نتیجه: **هر اطلسِ آینده خودکار Vision-to-Text می‌شود**؛ کتاب‌ها → `ingest_book`، گایدلاین‌ها → Chroma.

## فایل‌های تغییر/جدید (انجام‌شده)
- `ai_models.py` — تابع `caption_atlas_image` (جدید، ماژولار) ✅
- `clinical_rag/atlas_ingest.py` — استخراج+کپشن+ساخت ساب‌ایندکس، واحد=صفحه، resume، limit ✅
- `config.py` — فلگ‌های `ATLAS_IMAGES_DIR`, `ATLAS_SEND_IMAGE_TO_USER` ✅
- `Clinical RAG Manager - v3.0.py` — موتور ATLAS + روت ✅
- `book_aliases.json` — تأیید/تکمیل alias اطلس (در حین تست بررسی می‌شود)
- (بدون تغییر: `merger_of_indexes.py`, `rag_engine.py` query path)

## Verification
1. **probe**: تعداد دقیق تصاویر + برآورد هزینه و دیسک.
2. **تستِ نمونه‌ی کوچک:** `ingest_atlas` را روی ۳–۵ تصویرِ اول اجرا کن (limit پارامتر) → تأیید کن
   استخراج، کپشن آروان، و ساب‌ایندکس درست ساخته می‌شوند؛ یک query نمونه نتیجه‌ی اطلس بدهد.
3. **اجرای کامل:** کاربر کل اطلس را با پنل/اسکریپت کپشن‌گذاری می‌کند (یک‌باره، resumable).
4. **merge + تست end-to-end:** بعد از merge، یک عکس لام واقعی بفرست → باید توصیف اطلس در
   `retrieved_docs` و رفرنسِ «Clinical Hematology Atlas, page X» در پاسخ بیاید.
5. ربات ری‌استارت تا brain_index جدید لود شود.

## برآورد هزینه (تقریبی، با probe دقیق می‌شود)
- اطلس ~۳۰۰–۵۰۰ تصویر فرض. هر کپشن ~۳۰۰ توکن خروجی. آروان Gemini-2.5-lite خروجی ۸۴هزار/۱M
  → کل ~۱۲۰k–۱۵۰k توکن ≈ **چند هزار تومان، یک‌بار**. دیسک تصاویر ~۲۰–۴۰MB.

## فاز بعد (ثبت، پیاده نمی‌شود)
- تصویربه‌تصویر با MedSigLIP (خون/پاتو) + BioCLIP (انگل) در استورِ جدا.
- فعال‌کردن `ATLAS_SEND_IMAGE_TO_USER` (ارسال شکل مرجع به کاربر).
- کپشن‌گذار MedGemma اگر روی API/GPU در دسترس شد.

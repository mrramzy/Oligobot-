# گزارش جلسه — ۲۰۲۶-۰۶-۱۷ (شب)

**هدف جلسه:** بستنِ کاملِ اطلسِ روداک، آماده‌سازی پایپ‌لاین برای بقیه‌ی اطلس‌ها، رفع باگ حذفِ رفرنس، و فارسی‌سازیِ ارجاعِ جدول/تصویر.

محیط مجازیِ پروژه: `D:\Programing\projects\Telegram RAG bot\RAGBot\Scripts\python.exe`

---

## ۱. اطلسِ روداک (Clinical Hematology Atlas) — کامل شد ✅

- **۲۱۶ صفحه** کپشن‌گذاری شد (Vision-to-Text با آروان) و **۲۱۶ تصویر** در `knowledge_base/atlas_images/` ذخیره شد.
- ساب‌ایندکس در `knowledge_base/Clinical Hematology Atlas/` (index.faiss + index.pkl + bm25_retriever.pkl + chunks.jsonl).
- در `brain_index` ادغام شد → **مجموع ۲۴۰۹۴ چانک** (۲۳۸۷۸ متن + ۲۱۶ تصویرِ اطلس).
- تیتز هنگام merge به‌خاطر بُعدِ ۷۶۸ (مدل قدیمی) خودکار رد می‌شود — انتظارمان همین است (نیاز به reembed دارد اگر بخواهیم برگردد).

**تأییدِ کارکرد (جستجوی واقعی روی brain_index):**
| کوئری | بهترین نتیجه | فاصله |
|---|---|---|
| spherocyte morphology | اطلس، ص ۹۷، تصویر 11.4 | 0.559 |
| teardrop / dacrocyte | اطلس، ص ۱۰۳، تصویر 11.10 | 0.548 |
| wedge film preparation | اطلس، ص ۳ و ۲، تصویر 1.1/1.2 | 0.482 |

چانک‌های تصویریِ اطلس در صدر نتایجِ مورفولوژیک می‌آیند → سیستم درست کار می‌کند.

---

## ۲. پایپ‌لاینِ اطلس جنریک شد (آماده برای اطلس‌های بعدی) ✅

فایل: `clinical_rag/atlas_ingest.py`
- **نام منبع از روی نام فایل** گرفته می‌شود (دیگر هاردکد نیست). تابع `_source_name_from_path`. روداک هنوز دقیقاً «Clinical Hematology Atlas» می‌شود.
- **گیتِ فیگور گسترده:** `FIGURE_KEYWORDS = ("FIGURE", "FIG.", "FIG ", "PLATE")`.
- **پارامترِ `page_label_mode`:** `"printed"` (پیش‌فرض، مخصوص روداک — شماره از خط اولِ صفحه) یا `"physical"` (شماره از برچسب/شماره‌ی فیزیکیِ PDF؛ برای اطلسی که چیدمانِ شماره‌گذاریِ متفاوت دارد).
- پارامترِ اختیاریِ `source_name` برای override دستی.
- روتر در `Clinical RAG Manager - v3.0.py` (`decide_index_engine`) هر فایلی با «atlas» یا «rodak» در نام را خودکار به موتور `ATLAS` می‌فرستد.

### 👉 روشِ افزودنِ اطلسِ بعدی (برای خودت)
1. فایلِ PDF اطلس را در `knowledge_base/atlases/` بگذار (نامِ فایل = نامِ نمایشیِ منبع؛ مثلاً `Koneman's Color Atlas.pdf`).
2. (اختیاری ولی توصیه‌شده) در `book_aliases.json` یک alias برایش اضافه کن (اسم کوتاه فارسی) تا citation تمیز شود.
3. اجرا — یکی از دو راه:
   - از پنل: `Clinical RAG Manager - v3.0.py` → افزودنِ منبع (روتر خودش ATLAS را انتخاب می‌کند).
   - یا مستقیم (پایتونِ venv):
     ```python
     from clinical_rag.atlas_ingest import ingest_atlas
     ingest_atlas("knowledge_base/atlases/<FILE>.pdf", resume=True)
     # اگر شماره‌ی صفحه‌ها درست تشخیص داده نشد:
     # ingest_atlas("...", resume=True, page_label_mode="physical")
     ```
4. **تستِ نمونه اول:** با `limit=3` بزن و `chunks.jsonl` را نگاه کن (شماره‌ی صفحه، figure_ids و کیفیتِ کپشن). اگر شماره‌ها پرت بود → `page_label_mode="physical"`.
5. بعد از ingestِ کامل: merge را اجرا کن تا وارد مغز شود:
   ```python
   from clinical_rag.merger_of_indexes import merge_and_save
   merge_and_save(output_dir="brain_index")
   ```
6. ربات را restart کن (در زمان اجرا از `brain_index/` می‌خواند).

> نکته: کپشن‌گذاری تماسِ ویژنِ آروان دارد (پولی). `resume=True` صفحاتِ انجام‌شده را رد می‌کند، پس اگر وسطش قطع شد دوباره بزن.

---

## ۳. حذفِ رفرنس — دو باگ پیدا و رفع شد ✅

**باگ A — `remove_book_index()` در `Clinical RAG Manager - v3.0.py`:**
کدِ قبلی همه‌ی فایل‌های `index.faiss` را skip می‌کرد؛ چون هر ساب‌ایندکس داخلِ پوشه‌ی خودش `index.faiss` نام دارد، عملاً **هیچ مرجعی پیدا نمی‌شد**. بازنویسی شد: حالا پوشه‌های مرجع (که `index.faiss` دارند) را با **نامِ پوشه** فهرست می‌کند، کلِ پوشه را حذف می‌کند (`shutil.rmtree`)، و سپس re-merge می‌کند. هر ۴ مرجع درست لیست شدند.

**باگ B — `merge_and_save()` در `clinical_rag/merger_of_indexes.py`:**
هنگام re-merge فایل‌های `bm25_retriever_*.pkl` قدیمیِ `brain_index` پاک نمی‌شدند؛ بات در زمان اجرا هر `*bm25_retriever*.pkl` را از `brain_index` می‌خواند → مرجعِ حذف‌شده در **جستجوی کلمه‌کلیدی** باقی می‌ماند. حالا ابتدای merge، BM25های قدیمی پاک و از نو ساخته می‌شوند (در همین merge تأیید شد).

> نتیجه: حالا «Remove a Reference» در پنل واقعاً مرجع را هم از FAISS و هم از BM25 حذف می‌کند.

---

## ۴. فرمتِ ارجاعِ جدول/تصویر — فارسی شد ✅

خواسته: مثلِ «صفحه‌ی فلان»، «جدول فلان» و «تصویر فلان» نوشته شود؛ کلماتِ انگلیسیِ table/figure/image در متن نماند.

- **`book_aliases.json` → `citation_format`:** قانونِ `rule_table_fa` و `example_table_fa` فارسی شد (Table→جدول، Figure/Image→تصویر؛ مثال: «(هافبراند، صفحه 176، جدول 11.3)»). منبعِ واحدِ حقیقت؛ به prompt تزریق می‌شود (`rag_engine.py:527`).
- **شبکه‌ی ایمنی در `citation_manager.py`:** متد `_normalize_visual_terms` در `format_answer_with_citations` اجرا می‌شود — هر «Table 11.3 / Tab. / Figure 1.1 / Fig. / Image / Photo» باقی‌مانده را به «جدول/تصویر» تبدیل می‌کند. فقط وقتی یک شناسه (عدد/رومی) بلافاصله بعدش بیاید عمل می‌کند، پس متنِ عادیِ بدون عدد دست‌نخورده می‌ماند. (تست شد.)

---

## فایل‌های تغییریافته
- `clinical_rag/atlas_ingest.py` — جنریک‌سازی (نام منبع، گیتِ فیگور، page_label_mode).
- `clinical_rag/merger_of_indexes.py` — پاک‌سازیِ BM25 قبل از re-merge.
- `Clinical RAG Manager - v3.0.py` — بازنویسیِ `remove_book_index` (پوشه‌محور).
- `book_aliases.json` — فارسی‌سازیِ قانون/مثالِ جدول/تصویر.
- `citation_manager.py` — نرمالایزرِ ارجاعِ دیداری + هماهنگیِ defaultها.

## وضعیتِ فعلیِ ایندکس
- `brain_index`: ۲۴۰۹۴ چانک (اطلس + هنری + هافبراند). BM25 برای هر سه تازه ساخته شد.
- `knowledge_base/`: اطلسِ روداک کامل؛ تیتز هنوز ۷۶۸بعدی (نیاز به reembed برای بازگشت به مغز).

## کارهای بعدی (پیشنهادی)
1. (تو) افزودنِ بقیه‌ی اطلس‌ها طبق دستورالعملِ بخش ۲.
2. تستِ واقعیِ بات: یک سوالِ مورفولوژیک بپرس و چک کن رفرنس به‌صورت «(اطلس هماتولوژی، صفحه X، تصویر Y)» بیاید.
3. تستِ پنل: «Remove a Reference» روی یک مرجعِ آزمایشی.
4. تصمیم درباره‌ی تیتز (reembed با bge-m3 یا کنار گذاشتن).

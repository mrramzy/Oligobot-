# OLIGOBOT V10 - Specialized Architecture Documentation

## 🏗️ معماری سیستم (System Architecture)

### دو بخش اصلی:

```
┌────────────────────────────────────────────────────────────────┐
│                    OLIGOBOT V10                                │
│              (Medical RAG System)                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────┐          ┌──────────────────┐           │
│  │ TEXT/DOCUMENT    │          │  IMAGE/SLIDE     │           │
│  │  INPUT PIPELINE  │          │  INPUT PIPELINE  │           │
│  └────────┬─────────┘          └────────┬─────────┘           │
│           │                             │                    │
│           ▼                             ▼                    │
│  ┌──────────────────────────┐  ┌─────────────────────────┐  │
│  │  4 CORE PROMPTS          │  │  DOMAIN-SPECIFIC PROMPT │  │
│  │  (General Purpose)       │  │  (Specialized)          │  │
│  │                          │  │                         │  │
│  │ 1. system_core.md        │  │ 5 Medical Domains:      │  │
│  │ 2. human_interaction.md  │  │ • hematology.md         │  │
│  │ 3. diagnostic_protocol.md│  │ • pathology.md          │  │
│  │ 4. prompt_injection...md │  │ • cytopathology.md      │  │
│  │                          │<-│ • parasitology.md       │  │
│  │ Purpose:                 │  │ • urinalysis.md         │  │
│  │ • Language & tone        │  │                         │  │
│  │ • Output format          │  │ Purpose:                │  │
│  │ • Safety rules           │  │ • Expert analysis       │  │
│  │ • Scope definition       │  │ • Domain knowledge      │  │
│  └──────────┬───────────────┘  │ • Diagnostic protocols  │  │
│             │                  │ • Test recommendations  │  │
│             │                  └──────────-──────────────┘  │
│             └──────────────┬                 
│                            │                                │
│                            ▼                                │
│                  ┌─────────────────────┐                   │
│                  │  RAG INTEGRATION    │                   │
│                  │  Knowledge Base     │                   │
│                  │  + Citations        │                   │
│                  └──────────┬──────────┘                   │
│                             │                              │
│                             ▼                              │
│                  ┌─────────────────────┐                   │
│                  │  LLM RESPONSE       │                   │
│                  │  Generation         │                   │
│                  └──────────┬──────────┘                   │
│                             │                              │
│                             ▼                              │
│                  ┌─────────────────────┐                   │
│                  │  FINAL OUTPUT       │                   │
│                  │  (Specialized)      │                   │
│                  └─────────────────────┘                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 🖼️ IMAGE/SLIDE ANALYSIS WORKFLOW (نوآورانه)

```
┌─────────────────────────────────────────────────────────────────┐
│                    عکس/لام تشخیصی                            │
│              (Diagnostic Slide/Image)                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         مدل Vision توصیف عکس                                  │
│    (Image Captioning Model)                                    │
│    Output: "خون با بلاست‌های زیاد، Auer rods مشاهده شدند"   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│        استخراج کلیدواژه‌های پزشکی                           │
│    (Medical Keyword Extraction)                                │
│    Keywords: ["blast", "Auer rods", "leukemia", ...]        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          تشخیص Domain خودکار                                  │
│      (Domain Detection - Keyword Based)                        │
│      Result: HEMATOLOGY ✓                                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│    بارگذاری Specialized Prompt                               │
│       (Load hematology.md)                                     │
│                                                                │
│    استاد کارکشته هماتولوژی:                                 │
│    ✓ تحلیل مورفولوژی                                        │
│    ✓ دیفرانسیال دیاگنوز                                     │
│    ✓ توصیه آزمایش‌های تأیید کننده                          │
│    ✓ نتیجه‌گیری نهایی                                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│    یکپارچه شدن با RAG Knowledge Base                          │
│        (RAG Integration)                                       │
│    - استناد به مطالعات معتبر                                 │
│    - اضافه کردن context از knowledge base                    │
│    - تقویت دقت پاسخ                                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          تولید پاسخ نهایی با LLM                              │
│       (Final Response Generation)                              │
│                                                                │
│    نتیجه: تحلیل دقیق + توصیات + استنادها                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 TEXT/DOCUMENT WORKFLOW (استاندارد)

```
┌─────────────────────────────────────────────────────────────────┐
│              پرسش متنی یا سند                                 │
│          (Text Question or Document)                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         استفاده از 4 CORE PROMPTS                             │
│                                                                │
│    1. system_core.md → شخصیت و هویت                         │
│    2. human_interaction.md → تن و رفتار                    │
│    3. diagnostic_protocol.md → پروتکل تشخیصی               │
│    4. prompt_injection_shield.md → امنیت                  │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          جستجو در RAG Knowledge Base                           │
│           (Vector Search + Retrieval)                          │
│    - استخراج نتایج مرتبط                                     │
│    - رتبه‌بندی با عنایت به مربوط‌بودن                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         ترکیب Context + Documents                              │
│        (Hybrid RAG Integration)                                │
│    - معلومات بازیافت شده                                     │
│    - منابع معتبر                                             │
│    - Context محافظت‌شده                                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         تولید پاسخ توسط LLM                                   │
│       (Response Generation)                                    │
│    - دقیق و علمی                                             │
│    - با استناد                                               │
│    - بر اساس 4 core prompts                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Domain Detection فایل‌های Specialized

### نگاشت Keywords → Domain → Prompt File

```
┌──────────────────────────────────────────────────────────┐
│  Keywords Detected                                       │
├──────────────────────────────────────────────────────────┤
│  "خون", "گلبول", "RBC", "hemoglobin"                   │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│  Domain Classification                                   │
├──────────────────────────────────────────────────────────┤
│  Match: HEMATOLOGY                                       │
└─────────────────────┬──────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│  Load Specialized Prompt File                            │
├──────────────────────────────────────────────────────────┤
│  File: /PSL/hematology.md                               │
│                                                          │
│  Content:                                               │
│  ✓ خبرگی هماتولوژی                                     │
│  ✓ پروتکل تحلیل                                        │
│  ✓ معاییر تشخیصی                                       │
│  ✓ توصیه‌های آزمایش                                    │
└──────────────────────────────────────────────────────────┘
```

### تمام Domain‌ها

| Keywords | Domain | Specialized Prompt | Purpose |
|----------|--------|-------------------|---------|
| خون، RBC، WBC، hemoglobin | **Hematology** | hematology.md | Blood cell analysis |
| بافت، tissue، biopsy | **Pathology** | pathology.md | Tissue analysis |
| سلول، microscopy، nucleus | **Cytopathology** | cytopathology.md | Cell analysis |
| انگل، parasite، protozoan | **Parasitology** | parasitology.md | Parasite ID |
| ادرار، urine، crystal، sediment | **Urinalysis** | urinalysis.md | Urine analysis |
| سوال کلی، متن | **General** | 4 core prompts | Text-based Q&A |

---

## 💡 نقطه نوآوری (Innovation)

### چرا این معماری خاص است:

1. **Dual-Mode Processing**
   - تصویر: Domain-specific specialized prompts
   - متن: Core generic prompts + RAG

2. **On-Demand Specialization**
   - Specialized prompts فقط هنگام نیاز بارگذاری می‌شوند
   - حافظه‌کارآمد
   - سرعت بالا

3. **Expert-Level Analysis**
   - هر domain یک "استاد کارکشته" است
   - Protocols تشخیصی دقیق
   - توصیه‌های آزمایش‌های تأیید کننده

4. **RAG Integration**
   - تمام پاسخ‌ها بر اساس knowledge base
   - استناد خودکار
   - دقت و اعتماد‌پذیری

---

## 🔄 کد Implementation

### در `rag_engine.py`:

```python
# Step 2: Domain Detection & Specialized Prompt Loading
domain = detect_clinical_domain(user_query)  # e.g., "hematology"

if strategy.get("mode") == "image":
    # برای عکس: بارگذاری specialized prompt
    specialized_prompt = self._load_specialized_prompt(domain)
    if specialized_prompt:
        llm_chat_history.append({
            "role": "system", 
            "content": specialized_prompt
        })
else:
    # برای متن: استفاده از 4 core prompts
    core_prompts = self.prompt_cache.get_all_core()
    combined_core = "\n\n".join(core_prompts)
    llm_chat_history.append({
        "role": "system", 
        "content": combined_core
    })
```

---

## ✅ فایل‌های Specialized موجود

- ✅ **hematology.md** - تحلیل خون
- ✅ **pathology.md** - تحلیل بافت
- ✅ **cytopathology.md** - تحلیل سلول‌ها
- ✅ **parasitology.md** - شناسایی انگل‌ها
- ✅ **urinalysis.md** - تحلیل ادرار

## ✅ فایل‌های Core Prompts موجود

- ✅ **system_core.md** - هویت و شخصیت
- ✅ **human_interaction.md** - تن و رفتار
- ✅ **diagnostic_protocol.md** - پروتکل تشخیصی
- ✅ **prompt_injection_shield.md** - حفاظت امنیتی

---

## 🚀 نتیجه

این معماری:
- **برای عکس/اسلاید**: متخصص هستند (specialized)
- **برای متن**: عمومی و انعطاف‌پذیر (generic)
- **هر دو با RAG**: یکپارچه و معتبر

**نوآورانه، دقیق، و حرفه‌ای!** 🎯


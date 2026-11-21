# -*- coding: utf-8 -*-
"""
🖼️ Atlas Ingest — Vision-to-Text indexing برای اطلس‌های تصویرمحور.

برخلاف faiss_ingest (متن‌محور)، اینجا واحدِ کار «صفحه» است: هر صفحه‌ی محتوایی یک تصویرِ
مرکّب (پنل‌های A/B/C/D) + متنِ غنی (FIGURE/DESCRIPTION/ASSOCIATED WITH) دارد. برای هر صفحه:
تصویر استخراج و ذخیره می‌شود، متنِ صفحه به‌عنوان «حقیقتِ زمینه» به کپشن‌گذارِ ویژن (آروان) داده
می‌شود تا یک توصیفِ مورفولوژیکِ انگلیسیِ جستجوپذیر تولید شود، و نتیجه به‌صورت یک چانکِ متنی در
همان فضای bge-m3 ایندکس می‌شود. خروجی یک ساب‌ایندکس FAISS+BM25 هم‌فرمت با کتاب‌هاست؛ سپس
merger_of_indexes آن را در brain_index ادغام می‌کند.

اجرا: از پنل (Clinical RAG Manager v3.0 → موتور ATLAS) یا مستقیم:
    python -m clinical_rag.atlas_ingest  (یا ingest_atlas(path, limit=3) برای تست)
"""
import os
import sys
import io
import json
import pickle
import asyncio

import fitz  # PyMuPDF
from PIL import Image
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

# مسیر ریشه‌ی پروژه برای importهای هم‌سطح
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import re
from embeddings import get_rag_embeddings
from ai_models import caption_atlas_image
from clinical_rag.faiss_ingest import (
    sanitize_ascii_name, extract_visual_ids, BM25_FILENAME,
)

# نام نمایشیِ منبعِ پیش‌فرض (وقتی از روی نام فایل گرفته نشود). باید با book_aliases.json بخواند.
ATLAS_SOURCE_NAME = "Clinical Hematology Atlas"
# حداقل ابعاد تصویر تا لوگو/تزئین رد شود
MIN_IMG_DIM = 150
# هم‌زمانیِ تماس‌های ویژن (محترمانه با rate-limit آروان)
CAPTION_CONCURRENCY = 3
# کلیدواژه‌هایی که «صفحه‌ی فیگوردار» را مشخص می‌کنند (اطلس‌های مختلف اصطلاح متفاوت دارند)
FIGURE_KEYWORDS = ("FIGURE", "FIG.", "FIG ", "PLATE")


def _source_name_from_path(pdf_path: str) -> str:
    """نام نمایشیِ منبع را از نام فایلِ اطلس می‌سازد (بدون پسوند، تمیزشده)."""
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    return re.sub(r"\s+", " ", base).strip() or ATLAS_SOURCE_NAME


def _has_figure(text_upper: str) -> bool:
    return any(k in text_upper for k in FIGURE_KEYWORDS)

# پاک‌سازیِ سبکِ آرتیفکت‌های لیگاتور/سمبل که fitz تولید می‌کند
_LIG_FIX = {"�": "x", "": "", "": "", "": ""}


def _clean_text(t: str) -> str:
    if not t:
        return ""
    for k, v in _LIG_FIX.items():
        t = t.replace(k, v)
    return "\n".join(ln.strip() for ln in t.splitlines() if ln.strip())


def _largest_image_on_page(doc, page):
    """بزرگ‌ترین تصویرِ embed‌شده‌ی صفحه را به‌صورت (PIL.Image, ext) برمی‌گرداند یا None."""
    best = None
    best_area = 0
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            info = doc.extract_image(xref)
        except Exception:
            continue
        w, h = info.get("width", 0), info.get("height", 0)
        if w < MIN_IMG_DIM or h < MIN_IMG_DIM:
            continue
        area = w * h
        if area > best_area:
            best_area = area
            best = info
    if not best:
        return None
    try:
        pil = Image.open(io.BytesIO(best["image"])).convert("RGB")
        return pil, best.get("ext", "png")
    except Exception:
        return None


def _atlas_page_number(raw_text: str, prev):
    """شماره‌ی صفحه‌ی اطلس را مستقیم از خط اول/آخر (عددِ عربیِ مستقل) می‌خواند.
    اطلس Rodak شماره را در خط اولِ هر صفحه‌ی بدنه دارد. front-matter (رومی/بدون‌عدد) → None (skip).
    drift-guard سبک تا اعدادِ پرت (مثل شماره‌ی فیگور) شماره‌ی صفحه تلقی نشوند.
    خروجی: int یا None."""
    lines = [l.strip() for l in (raw_text or "").splitlines() if l.strip()]
    if not lines:
        return None
    # در اطلس Rodak شماره‌ی صفحه «خط اول» است؛ خط آخر معمولاً متن/رفرنس است (مثبت کاذب).
    first = lines[0]
    if re.fullmatch(r"\d{1,3}", first):
        n = int(first)
        if prev is None:
            # شروعِ بدنه: فقط عددِ کوچک (1..6) را بپذیر تا اعدادِ پرتِ TOC/front-matter بدنه را زود شروع نکنند
            return n if n <= 6 else None
        if abs(n - (prev + 1)) <= 5 or abs(n - prev) <= 5:
            return n
        return None
    # fallback: اگر از قبل در بدنه‌ایم، خط آخر را با drift-guard امتحان کن (صفحاتی که شماره ته‌شان است)
    if prev is not None and re.fullmatch(r"\d{1,3}", lines[-1]):
        n = int(lines[-1])
        if abs(n - (prev + 1)) <= 5 or abs(n - prev) <= 5:
            return n
    return None


def _guess_section(text: str) -> str:
    """یک عنوانِ کوتاهِ بخش/سلول از متن صفحه حدس می‌زند (برای متادیتای chapter)."""
    for ln in text.splitlines():
        s = ln.strip()
        # خطوطِ کوتاهِ تمام‌بزرگ (مثل SPHEROCYTE) عنوانِ مورفولوژی‌اند
        if 3 <= len(s) <= 40 and s.isupper() and not any(ch.isdigit() for ch in s):
            return s.title()
    return "Atlas"


def _collect_pages(pdf_path, limit=None, page_label_mode="printed"):
    """صفحاتِ محتوایی (تصویر + کلمه‌ی فیگور) را استخراج می‌کند.
    page_label_mode:
      - "printed": شماره را از متنِ چاپ‌شده‌ی صفحه می‌خواند (پیش‌فرض، مخصوص اطلسِ Rodak/مشابه).
      - "physical": از شماره‌ی فیزیکیِ PDF (یا برچسبِ PDF) استفاده می‌کند؛ برای اطلس‌هایی که
        شماره‌ی چاپی قابل‌اتکا ندارند (front-matter با گیتِ فیگور+تصویر فیلتر می‌شود).
    خروجی: لیستی از dict شامل pdf_index, page_label, text, figure_ids, section, image(PIL), ext."""
    doc = fitz.open(pdf_path)
    out = []
    prev_num = None
    for i in range(doc.page_count):
        page = doc[i]
        raw = page.get_text("text")
        if page_label_mode == "printed":
            # شماره‌ی صفحه‌ی مستقیم؛ None یعنی front-matter/بدون‌شماره → کل صفحه skip (مثبت کاذب حذف می‌شود)
            num = _atlas_page_number(raw, prev_num)
            if num is None:
                continue
            prev_num = num  # حتی اگر این صفحه فیگور نداشته باشد، شماره را جلو ببر تا drift-guard درست بماند
            page_label = str(num)
        else:  # physical: برچسبِ PDF اگر عددی بود، وگرنه شماره‌ی فیزیکی
            lbl = (page.get_label() or "").strip()
            page_label = lbl if lbl.isdigit() else str(i + 1)
        text = _clean_text(raw)
        if not _has_figure(text.upper()):
            continue
        got = _largest_image_on_page(doc, page)
        if not got:
            continue
        pil, ext = got
        fig_ids = extract_visual_ids(text) or "None"
        fig_ids = re.sub(r"\s+", " ", fig_ids).strip()  # حذف newline داخلِ "Figure\n2-1"
        out.append({
            "pdf_index": i,
            "page_label": page_label,
            "text": text,
            "figure_ids": fig_ids,
            "section": _guess_section(text),
            "image": pil,
            "ext": ext,
        })
        if limit and len(out) >= limit:
            break
    doc.close()
    return out


async def _caption_all(pages):
    """کپشن‌گذاریِ هم‌زمانِ محدودِ صفحات. توصیف را در کلید 'caption' هر page می‌گذارد."""
    sem = asyncio.Semaphore(CAPTION_CONCURRENCY)

    async def one(pg):
        async with sem:
            pg["caption"] = await caption_atlas_image(pg["image"], pg["text"])

    await asyncio.gather(*[one(pg) for pg in pages])


def ingest_atlas(pdf_path: str, output_dir: str = "knowledge_base", limit=None, resume: bool = True,
                 source_name: str = None, page_label_mode: str = "printed"):
    """
    اطلس را Vision-to-Text ایندکس می‌کند → ساب‌ایندکس FAISS+BM25 در knowledge_base/<ascii name>/.
    limit: فقط N صفحه‌ی اول (برای تستِ نمونه). resume: صفحاتِ کپشن‌خورده‌ی قبلی را skip کن.
    source_name: نام نمایشیِ منبع برای citation؛ None یعنی از نام فایل گرفته شود (جنریک برای هر اطلس).
    page_label_mode: "printed" (پیش‌فرض، Rodak) یا "physical" (اطلسِ با چیدمانِ متفاوت).
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Atlas not found: {pdf_path}")
        return

    from config import ATLAS_IMAGES_DIR
    os.makedirs(ATLAS_IMAGES_DIR, exist_ok=True)

    source_name = source_name or _source_name_from_path(pdf_path)
    print(f"📚 منبع: {source_name}  |  حالتِ شماره‌ی صفحه: {page_label_mode}")

    index_save_path = os.path.join(output_dir, sanitize_ascii_name(source_name))
    os.makedirs(index_save_path, exist_ok=True)
    chunks_path = os.path.join(index_save_path, "chunks.jsonl")

    # --- Resume: چانک‌های قبلی + مجموعه‌ی صفحاتِ انجام‌شده ---
    existing_docs = []
    done_indices = set()
    if resume and os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                existing_docs.append(Document(page_content=rec["page_content"], metadata=rec["metadata"]))
                pi = rec.get("metadata", {}).get("pdf_index")
                if pi is not None:
                    done_indices.add(pi)
        print(f"🔄 Resume: {len(existing_docs)} چانکِ قبلی، {len(done_indices)} صفحه از قبل انجام شده.")

    print(f"📖 استخراج صفحاتِ محتوایی از اطلس...")
    pages = _collect_pages(pdf_path, limit=limit, page_label_mode=page_label_mode)
    pages = [p for p in pages if p["pdf_index"] not in done_indices]
    print(f"   {len(pages)} صفحه‌ی جدید برای کپشن‌گذاری.")

    if not pages and not existing_docs:
        print("❌ هیچ صفحه‌ی محتوایی پیدا نشد.")
        return

    # --- کپشن‌گذاری (ویژن آروان) ---
    if pages:
        print(f"🔬 کپشن‌گذاری {len(pages)} صفحه (هم‌زمانی {CAPTION_CONCURRENCY})...")
        asyncio.run(_caption_all(pages))

    # --- ساخت Document + ذخیره‌ی تصویر ---
    new_docs = []
    for pg in pages:
        caption = (pg.get("caption") or "").strip()
        if not caption:
            print(f"   ⚠️ صفحه {pg['page_label']}: کپشن خالی، رد شد.")
            continue
        # ذخیره‌ی تصویر
        img_name = f"atlas_p{pg['page_label']}_{pg['pdf_index']}.{('png' if pg['ext'] not in ('png','jpg','jpeg') else pg['ext'])}"
        img_path = os.path.join(ATLAS_IMAGES_DIR, img_name)
        try:
            pg["image"].save(img_path)
        except Exception as e:
            print(f"   ⚠️ ذخیره‌ی تصویر صفحه {pg['page_label']} ناموفق: {e}")
            img_path = ""

        page_content = (
            f"**TYPE: IMAGE**\nPage: {pg['page_label']}\nContext: {pg['section']}\n"
            f"**Contains: {pg['figure_ids']}**\n**VISUAL_DESC:** {caption}"
        )
        metadata = {
            "source": source_name,
            "chapter": pg["section"],
            "category": "Hematology",
            "page": pg["page_label"],
            "type": "image",
            "visuals": pg["figure_ids"],
            "engine": "vision_caption",
            "image_path": os.path.relpath(img_path, os.path.dirname(index_save_path)) if img_path else "",
            "pdf_index": pg["pdf_index"],
        }
        new_docs.append(Document(page_content=page_content, metadata=metadata))

    all_docs = existing_docs + new_docs
    if not all_docs:
        print("❌ هیچ چانکی برای ذخیره نیست.")
        return

    print(f"\n💾 ذخیره‌ی {len(all_docs)} چانک ({len(new_docs)} جدید) در {index_save_path}...")

    # 1) chunks.jsonl (کاملِ به‌روز)
    with open(chunks_path, "w", encoding="utf-8") as f:
        for d in all_docs:
            f.write(json.dumps({"page_content": d.page_content, "metadata": d.metadata}, ensure_ascii=False) + "\n")
    print(f"🧬 {len(all_docs)} چانک در chunks.jsonl ذخیره شد.")

    # 2) FAISS (bge-m3، batch)
    embeddings = get_rag_embeddings()
    vector_store = None
    BATCH = 100
    for i in range(0, len(all_docs), BATCH):
        batch = all_docs[i:i + BATCH]
        if vector_store is None:
            vector_store = FAISS.from_documents(batch, embedding=embeddings)
        else:
            vector_store.add_documents(batch)
        print(f"   Batch {i // BATCH + 1} embedded.")
    vector_store.save_local(index_save_path)

    # 3) BM25
    try:
        bm25 = BM25Retriever.from_documents(all_docs)
        bm25.k = 5
        with open(os.path.join(index_save_path, BM25_FILENAME), "wb") as f:
            pickle.dump(bm25, f)
        print("✅ BM25 ساخته شد.")
    except Exception as e:
        print(f"⚠️ BM25 ساخته نشد: {e}")

    print(f"✅ Atlas ingest کامل شد. حالا merge را اجرا کن تا در brain_index بیاید.")


if __name__ == "__main__":
    # اجرای مستقیم برای تست: پیش‌فرض اطلس هماتولوژی، ۳ صفحه‌ی نمونه
    default = os.path.join("knowledge_base", "atlases", "Clinical Hematology Atlas.pdf")
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    ingest_atlas(default, limit=lim)

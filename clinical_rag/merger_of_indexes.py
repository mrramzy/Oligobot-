# Merger of Indexes with BM25 and FAISS
import os
import sys
import pickle
import shutil
from langchain_community.vectorstores import FAISS

# 🧬 EMBEDDING (single source of truth): همان مدلی که faiss_ingest و کوئری ربات استفاده می‌کنند.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from embeddings import get_rag_embeddings

# ==========================================
# ⚙️ تنظیمات
# ==========================================
KNOWLEDGE_BASE_DIR = "knowledge_base"
BRAIN_INDEX_DIR = "brain_index"
BM25_FILENAME = "bm25_retriever.pkl"
OUTPUT_INDEX_NAME = "index"

# 🔒 Security: Validate paths are within expected directories
def _validate_path(path: str, allowed_parent: str) -> bool:
    """Ensure path is within the allowed parent directory (prevents path traversal)."""
    try:
        real_path = os.path.realpath(path)
        real_parent = os.path.realpath(allowed_parent)
        return real_path.startswith(real_parent + os.sep) or real_path == real_parent
    except Exception:
        return False

# متغیرهای گلوبال (مخفی) برای نگهداری ایندکس‌ها در حافظه
_GLOBAL_FAISS = None
_GLOBAL_BM25_RETRIEVERS = []

def load_knowledge_base():
    """
    🚀 تابع راه‌اندازی (Startup):
    این تابع باید فقط یکبار در زمان استارت ربات صدا زده شود.
    وظیفه: خواندن تمام کتاب‌ها از دیسک و ادغام آن‌ها در حافظه.
    """
    global _GLOBAL_FAISS, _GLOBAL_BM25_RETRIEVERS

    # مدل امبدینگ برای لود کردن FAISS ضروری است (هماهنگ با مدل ساخت)
    embeddings = get_rag_embeddings()
    
    if not os.path.exists(KNOWLEDGE_BASE_DIR):
        print(f"⚠️ مسیر دیتابیس {KNOWLEDGE_BASE_DIR} یافت نشد.")
        return

    # 1. پیدا کردن پوشه‌های تمام کتاب‌ها
    book_folders = [
        os.path.join(KNOWLEDGE_BASE_DIR, d) 
        for d in os.listdir(KNOWLEDGE_BASE_DIR) 
        if os.path.isdir(os.path.join(KNOWLEDGE_BASE_DIR, d))
    ]

    if not book_folders:
        print("⚠️ هیچ کتابی در سیستم ایندکس نشده است.")
        return

    print(f"📚 در حال بارگذاری و ادغام {len(book_folders)} کتاب مرجع...")

    # --- 2. بارگذاری و ادغام FAISS (مغز معنایی) ---
    try:
        # کتاب اول را به عنوان "پایه" لود می‌کنیم
        print(f"   🔹 بارگذاری پایه: {os.path.basename(book_folders[0])}")
        _GLOBAL_FAISS = FAISS.load_local(book_folders[0], embeddings, allow_dangerous_deserialization=True)
        
        # بقیه کتاب‌ها را روی اولی Merge می‌کنیم
        for folder in book_folders[1:]:
            try:
                sub_index = FAISS.load_local(folder, embeddings, allow_dangerous_deserialization=True)
                _GLOBAL_FAISS.merge_from(sub_index)
                print(f"   🔹 ادغام شد: {os.path.basename(folder)}")
            except Exception as e:
                print(f"   ❌ خطا در ادغام {folder}: {e}")
                
    except Exception as e:
        print(f"❌ خطای حیاتی در لود FAISS: {e}")
        _GLOBAL_FAISS = None

    # --- 3. بارگذاری BM25 (مغز کلمات کلیدی) ---
    _GLOBAL_BM25_RETRIEVERS = []
    for folder in book_folders:
        bm25_path = os.path.join(folder, BM25_FILENAME)
        if os.path.exists(bm25_path):
            try:
                with open(bm25_path, "rb") as f:
                    retriever = pickle.load(f)
                    _GLOBAL_BM25_RETRIEVERS.append(retriever)
                print(f"   🔸 BM25 لود شد: {os.path.basename(folder)}")
            except Exception as e:
                print(f"   ⚠️ خطای لود BM25 در {folder}: {e}")

    # گزارش نهایی
    faiss_size = _GLOBAL_FAISS.index.ntotal if _GLOBAL_FAISS else 0
    print(f"✅ سیستم آماده است! (تعداد کل قطعات دانش: {faiss_size})")

def merge_and_save(output_dir=BRAIN_INDEX_DIR):
    """
    Loads all sub-indexes from knowledge_base and saves a single merged index to output_dir.
    This is used by the Manager to prepare the index for the main bot.
    """
    print(f"🔄 Merging all indexes into {output_dir}...")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 🧹 پاک‌سازیِ BM25های قدیمی تا re-merge یک بازسازیِ تمیز باشد (کتابِ حذف‌شده نماند).
    # بات در زمان اجرا هر فایلِ *bm25_retriever*.pkl را از brain_index می‌خواند؛ پس قبل از کپیِ
    # دوباره باید قبلی‌ها حذف شوند، وگرنه مرجعِ حذف‌شده در جستجوی کلمه‌کلیدی باقی می‌ماند.
    for fn in os.listdir(output_dir):
        if "bm25_retriever" in fn and fn.endswith(".pkl"):
            try:
                os.remove(os.path.join(output_dir, fn))
            except Exception as e:
                print(f"   ⚠️ حذف BM25 قدیمی ناموفق ({fn}): {e}")

    embeddings = get_rag_embeddings()

    # بُعد مدلِ فعلی (برای رد کردن ایندکس‌های ناسازگار از مدل قدیمی)
    try:
        model_dim = len(embeddings.embed_query("dimension probe"))
    except Exception as e:
        print(f"⚠️ نتوانست بُعد مدل را تشخیص دهد: {e}")
        model_dim = None

    # فقط پوشه‌هایی که واقعاً index.faiss دارند (نه atlases/books/guidelines خام)
    candidate_folders = [
        os.path.join(KNOWLEDGE_BASE_DIR, d)
        for d in os.listdir(KNOWLEDGE_BASE_DIR)
        if os.path.isdir(os.path.join(KNOWLEDGE_BASE_DIR, d))
        and os.path.exists(os.path.join(KNOWLEDGE_BASE_DIR, d, "index.faiss"))
    ]

    if not candidate_folders:
        print("⚠️ هیچ پوشه‌ای با index.faiss برای ادغام پیدا نشد.")
        return

    merged_index = None
    merged_names = []
    for folder in candidate_folders:
        name = os.path.basename(folder)
        try:
            sub = FAISS.load_local(folder, embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"   ⏭️  رد شد (لود نشد): {name} | {e}")
            continue
        # رد کردن ایندکسِ ناسازگار (بُعد متفاوت = مدل قدیمی، مثلا Tietz 768)
        if model_dim is not None and sub.index.d != model_dim:
            print(f"   ⏭️  رد شد (بُعد {sub.index.d} ≠ مدل {model_dim}، با مدل قدیمی ساخته شده): {name}")
            continue

        if merged_index is None:
            merged_index = sub
        else:
            merged_index.merge_from(sub)
        merged_names.append(name)
        print(f"   🔹 ادغام شد: {name}")

        # کپی BM25 این کتاب
        bm25_src = os.path.join(folder, BM25_FILENAME)
        if os.path.exists(bm25_src):
            bm25_base = os.path.splitext(BM25_FILENAME)[0]
            bm25_dst = os.path.join(output_dir, f"{bm25_base}_{name}.pkl")
            try:
                shutil.copy(bm25_src, bm25_dst)
                print(f"   📄 BM25 کپی شد: {name}")
            except Exception as e:
                print(f"   ⚠️ کپی BM25 ناموفق ({name}): {e}")

    if merged_index is None:
        print("❌ هیچ ایندکس سازگاری برای ادغام نبود (همه با بُعد ناسازگار یا خراب).")
        return

    merged_index.save_local(output_dir, OUTPUT_INDEX_NAME)  # index.faiss + index.pkl
    print(f"✅ {len(merged_names)} کتاب ادغام شد ({merged_index.index.ntotal} چانک) → {output_dir}/{OUTPUT_INDEX_NAME}.faiss")

# ==========================================
# 🔌 توابع دسترسی (Getters)
# ==========================================
def get_faiss_index():
    """فایل جستجو از این تابع برای گرفتن FAISS استفاده می‌کند"""
    return _GLOBAL_FAISS

def get_bm25_retrievers():
    """فایل جستجو از این تابع برای گرفتن لیست BM25ها استفاده می‌کند"""
    return _GLOBAL_BM25_RETRIEVERS
import os
import sys
import re
import time
import shutil
import pickle
import json
import nest_asyncio
from dotenv import load_dotenv
from PyPDF2 import PdfWriter, PdfReader

# Add parent directory to path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import LLAMA_CLOUD_API_KEY

try:
    import fitz  # PyMuPDF for high-quality local extraction
except ImportError:
    fitz = None

# 🔧 PATCH: Fix for LangChain Core 0.3+ & Pydantic v2 compatibility
try:
    from langchain_core import pydantic_v1
except ImportError:
    import langchain_core
    try:
        from pydantic import v1 as pydantic_v1
    except ImportError:
        import pydantic as pydantic_v1
    import sys
    sys.modules["langchain_core.pydantic_v1"] = pydantic_v1
    langchain_core.pydantic_v1 = pydantic_v1

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

# 🧬 EMBEDDING (single source of truth): مدل امبدینگ از config/.env می‌آید (پیش‌فرض bge-m3 روی آروان).
# get_rag_embeddings تضمین می‌کند ساخت ایندکس و کوئری ربات همیشه با یک مدل باشند + batch واقعی برای سرعت.
from embeddings import get_rag_embeddings

from langchain_core.documents import Document
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- LlamaParse Import ---
from llama_parse import LlamaParse

# --- Marker Import ---
MARKER_AVAILABLE = False
try:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models
    print("⚙️ Loading Marker models...")
    model_lst = load_all_models()
    MARKER_AVAILABLE = True
except ImportError:
    pass

nest_asyncio.apply()
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

#===========================================
BOOK_INDEX_NAME = "Tietz_Textbook_Final"
PDF_PATH = "books/Tietz_Textbook.pdf"
KNOWLEDGE_BASE_DIR = "knowledge_base"
BM25_FILENAME = "bm25_retriever.pkl"
INITIAL_OFFSET = 41 
# ==========================================
# ⚙️ CONFIGURATION & MODES
# ==========================================
# "AUTO": Scans full book, decides mode per page (Table/Fig -> Premium, Text -> Fast/Marker)
# "SURGICAL": Only scans ranges defined in SURGICAL_PLAN
INGESTION_MODE = "AUTO" 

DEFAULT_MODE = "marker" if MARKER_AVAILABLE else "fast"

# Plan Configuration
SURGICAL_PLAN = {
    "Analytes_Reference": {"start": 1500, "end": 2000, "mode": "premium", "cat": "Clinical Chemistry"},
    "Clinical_Vignettes": {"start": 3800, "end": 3900, "mode": "fast", "cat": "Case Studies"},
    "Appendix_Tables":    {"start": 4200, "end": 4400, "mode": "premium", "cat": "Reference Data"},
    "Basics":             {"start": 100,  "end": 300,  "mode": "marker",  "cat": "Basics"}
}

# ==========================================
# 🧠 HELPER FUNCTIONS
# ==========================================
def sanitize_ascii_name(name):
    """
    نام پوشه‌ی ASCII-امن برای ایندکس.
    چرا: کتابخانه‌ی native faiss روی ویندوز مسیرهای غیر-ASCII را نه می‌نویسد نه می‌خواند
    (مثلاً آپوستروف فرفری ’ در "Henry’s"). نام نمایشیِ منبع (citation) دست‌نخورده می‌ماند؛
    فقط نام *پوشه* ASCII می‌شود.
    """
    repl = {'’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-'}
    for k, v in repl.items():
        name = name.replace(k, v)
    name = name.encode('ascii', 'ignore').decode('ascii').strip()
    name = re.sub(r'\s+', ' ', name)
    return name or "book"


# ------------------------------------------------------------------
# 📖 شماره‌گذاری صفحات (تست‌شده روی Henry/Hoffbrand واقعی)
# ------------------------------------------------------------------
# چالش: شروع شماره‌گذاری از ۱ افست دارد (front matter)، صفحاتِ بدون‌شماره،
# front-matter رومی، و e-pageهای انتهای فصل (مثل 21.e1) که افستِ ثابت را
# مدام جابه‌جا می‌کنند. راه‌حل: عددِ *چاپیِ* هر صفحه به‌عنوان «لنگر» خوانده
# می‌شود (با drift-guard برای رد اعداد پرت مثل سال)، رومی‌ها front matter،
# و صفحاتِ بدون‌شماره از آخرین لنگر شمرده می‌شوند.

_ROMAN_VALS = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}


def roman_to_int(s):
    """رشته‌ی رومی → عدد (یا None اگر رومی معتبر نباشد)."""
    s = s.strip().lower()
    if not s or not re.fullmatch(r'[ivxlcdm]+', s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALS[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def parse_page_token(text):
    """
    شماره‌ی چاپیِ صفحه را از خطوط ابتدا/انتها استخراج می‌کند.
    خروجی: ('epage', base, suf) | ('arabic', n) | ('roman', n, raw) | None
    اولویت: e-page > عدد عربی > رومی.
    """
    if not text:
        return None
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return None
    cands = lines[:3] + lines[-3:]

    # 1) e-page مثل 21.e1 / 707.e2
    for l in cands:
        m = re.search(r'\b(\d{1,5})[.\s  ]?e(\d{1,3})\b', l, re.IGNORECASE)
        if m:
            return ('epage', int(m.group(1)), int(m.group(2)))
    # 2) عدد عربی خالص (کل خط فقط یک عدد ۱ تا ۴ رقمی)
    for l in cands:
        if re.fullmatch(r'\d{1,4}', l):
            return ('arabic', int(l))
    # 3) رومی خالص
    for l in cands:
        n = roman_to_int(l)
        if n is not None:
            return ('roman', n, l)
    return None


class PageNumberTracker:
    """
    شماره‌گذاری ترتیبیِ تمیز برای حالت AUTO (صفحات به‌ترتیب پردازش می‌شوند).
    .next(page_text) برچسب صفحه را برمی‌گرداند: 'xii' (front matter) | '260' | '21.e1'.
    """
    DRIFT = 10  # حداکثر فاصله‌ی مجاز عدد تشخیص‌داده‌شده تا انتظار (رد اعداد پرت)

    def __init__(self):
        self.body = False     # وارد بدنه‌ی عددی شده‌ایم؟
        self.base = 0
        self.suffix = 0       # >0 یعنی e-page
        self.last_roman = 0

    def next(self, page_text):
        tok = parse_page_token(page_text)

        if tok and tok[0] == 'epage':
            self.body = True
            self.base, self.suffix = tok[1], tok[2]
            return f"{self.base}.e{self.suffix}"

        if tok and tok[0] == 'arabic':
            n = tok[1]
            # اولین عددِ بدنه بی‌قیدوشرط؛ بعد از آن drift-guard
            if not self.body or abs(n - self.base) <= self.DRIFT:
                self.body, self.base, self.suffix = True, n, 0
                return str(self.base)
            return self._increment()  # عددِ پرت → مثل صفحه‌ی بدون‌شماره

        if tok and tok[0] == 'roman' and not self.body:
            self.last_roman = tok[1]
            return tok[2]

        # شماره‌ای پیدا نشد
        if not self.body:
            return f"fm{self.last_roman}" if self.last_roman else "fm"
        return self._increment()

    def _increment(self):
        if self.suffix > 0:
            self.suffix += 1
            return f"{self.base}.e{self.suffix}"
        self.base += 1
        return str(self.base)

def extract_visual_ids(text):
    """Extracts Table/Figure IDs for metadata."""
    if not text: return None
    patterns = [r"(Table\s+\d+[-.]\d+)", r"(Figure\s+\d+[-.]\d+)", r"(Box\s+\d+[-.]\d+)"]
    found = []
    for pat in patterns:
        found.extend(re.findall(pat, text, re.IGNORECASE))
    return ", ".join(sorted(list(set(found)))) if found else None

def detect_page_mode(raw_text):
    """
    🤖 AI Decision: Decides ingestion mode based on page content complexity.
    """
    if not raw_text: return DEFAULT_MODE
    
    # Heuristic: If page contains explicit Table/Figure references, use Premium
    # Matches: "Table 12-1", "Figure 3.4", "Box 5-2"
    if re.search(r'(Table|Figure|Box)\s+\d+[-.]\d+', raw_text):
        return "premium"
    
    # Heuristic: Dense tabular data (lots of pipes or tabs)
    if raw_text.count('|') > 5: 
        return "premium"
        
    return "text"

# ==========================================
# 🚦 PROCESSORS (Robust)
# ==========================================
def extract_text_local(pdf_path):
    """Fallback text extraction using PyPDF2 (No API required)."""
    try:
        reader = PdfReader(pdf_path)
        text = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text.append(extracted)
        return "\n".join(text)
    except Exception as e:
        print(f"⚠️ Local Extraction Error: {e}")
        return ""

def extract_text_fitz(pdf_path):
    """High-quality local text extraction using PyMuPDF (Fitz)."""
    if not fitz:
        print("⚠️ PyMuPDF (fitz) not found. Falling back to PyPDF2.")
        return extract_text_local(pdf_path)
    
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
        return text
    except Exception as e:
        print(f"⚠️ Fitz Extraction Error: {e}")
        return extract_text_local(pdf_path)

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=2, min=4, max=20),
    retry=retry_if_exception_type(Exception)
)
def process_with_llama_robust(pdf_path, mode="premium"):
    """Sends request to LlamaCloud with retry mechanism."""
    
    # 🛡️ Fallback if API Key is missing
    if not LLAMA_CLOUD_API_KEY or LLAMA_CLOUD_API_KEY.strip() == "":
        print("⚠️ LlamaCloud API Key not found. Switching to Local Extraction.")
        return extract_text_local(pdf_path)
    
    # Custom instructions based on mode
    if mode == "premium":
        instruction = """
        Medical Textbook.
        1. Extract TABLES as distinct Markdown tables.
        2. IMAGES: If a clinical image exists, describe it starting with '**VISUAL_DESC:**'.
        """
    else:
        instruction = "Medical text. Preserve tables in Markdown."

    parser = LlamaParse(
        api_key=LLAMA_CLOUD_API_KEY,
        result_type="markdown",
        verbose=False,
        premium_mode=(mode == "premium"),
        system_prompt=instruction
    )
    docs = parser.load_data(pdf_path)
    return docs[0].text if docs else ""

def process_with_marker(pdf_path):
    if not MARKER_AVAILABLE: 
        return process_with_llama_robust(pdf_path, mode="fast")
    try:
        full_text, _, _ = convert_single_pdf(pdf_path, model_lst)
        return full_text
    except Exception as e:
        print(f"⚠️ Marker Error: {e}")
        return ""

# ==========================================
# ⚛️ ATOMIC SPLITTER
# ==========================================
def split_content_atomically(markdown_text, page_label, section, category, visuals, engine, source_name):
    """
    Separates Markdown tables from text to prevent chunking issues.
    Returns a list of Document objects.
    """
    documents = []
    
    # Regex to identify markdown tables
    table_pattern = r"(?:\|.*\|\n)+"
    
    # 1. Extract Tables
    tables = re.findall(table_pattern, markdown_text)
    
    # 2. Remove tables from main text
    text_without_tables = re.sub(table_pattern, "\n[TABLE_EXTRACTED]\n", markdown_text)
    
    # --- Process Tables (Atomic Chunks) ---
    for i, table in enumerate(tables):
        doc = Document(
            page_content=f"**TYPE: TABLE**\nPage: {page_label}\nContext: {section}\n**Contains: {visuals}**\n\n{table}",
            metadata={
                "source": source_name,
                "chapter": section,
                "category": category,
                "page": page_label,
                "type": "table",
                "visuals": visuals or "None",
                "engine": engine
            }
        )
        documents.append(doc)

    # --- Process Remaining Text ---
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    text_chunks = text_splitter.split_text(text_without_tables)
    
    for chunk in text_chunks:
        if "[TABLE_EXTRACTED]" in chunk and len(chunk) < 50: continue 

        doc = Document(
            page_content=f"**TYPE: TEXT**\nPage: {page_label}\nContext: {section}\n**Contains: {visuals}**\n{chunk}",
            metadata={
                "source": source_name,
                "chapter": section,
                "category": category,
                "page": page_label,
                "type": "text",
                "visuals": visuals or "None",
                "engine": engine
            }
        )
        documents.append(doc)
        
    return documents

def update_book_aliases(book_name):
    """Automatically adds the new book to book_aliases.json if missing."""
    try:
        alias_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "book_aliases.json"))
        
        if not os.path.exists(alias_path):
            return

        with open(alias_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        aliases = data.get("aliases", {})

        # 🛡️ اگر آلیاسِ منتخبی از قبل این کتاب را پوشش می‌دهد (کلید یا full_title زیررشته‌ی نام باشد)،
        # ورودیِ زشتِ خودکار اضافه نکن — اسم کوتاهِ تمیز همان آلیاس استفاده می‌شود.
        low = book_name.lower()
        for k, info in aliases.items():
            ft = (info.get("full_title") or "").lower()
            if k in low or (ft and ft in low):
                return

        # Create a key from the filename (lowercase, underscores)
        key = book_name.lower().replace(" ", "_").replace("-", "_")

        if key not in aliases:
            print(f"📝 Registering new book in aliases: {key}")
            new_entry = {
                "display": {"fa": book_name, "en": book_name},
                "full_title": book_name,
                "type": "book"
            }
            if "aliases" not in data:
                data["aliases"] = {}
            data["aliases"][key] = new_entry
            
            with open(alias_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("✅ book_aliases.json updated.")
            
    except Exception as e:
        print(f"⚠️ Warning: Could not update book_aliases.json: {e}")

# ==========================================
# 🚀 MAIN INGESTION LOOP
# ==========================================
def ingest_book(file_path: str, output_dir: str = "knowledge_base", extraction_mode: str = "auto"):
    """
    Ingests a book with support for both SURGICAL (Manual) and AUTO (Smart) modes.
    """
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    book_name = os.path.splitext(os.path.basename(file_path))[0]

    update_book_aliases(book_name)

    # نام پوشه ASCII-امن (faiss native روی ویندوز مسیر یونیکد را پشتیبانی نمی‌کند).
    # نام نمایشیِ منبع برای citation همان book_name اصلی می‌ماند.
    index_save_path = os.path.join(output_dir, sanitize_ascii_name(book_name))
    
    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    all_documents = []
    
    temp_dir = "temp_ingest"
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)

    print(f"🚀 Starting Ingestion: {BOOK_INDEX_NAME}")
    print(f"🚀 Starting Ingestion: {book_name}")
    print(f"   Strategy: {extraction_mode.upper()} | Plan: {INGESTION_MODE}")

    # --- 1. Build Processing Queue ---
    pages_to_process = [] # List of (page_index, mode, category, section)

    if INGESTION_MODE == "SURGICAL":
        # Manual Plan
        for section_name, plan in SURGICAL_PLAN.items():
            for i in range(plan["start"], plan["end"]):
                if i < total_pages:
                    pages_to_process.append((i, plan["mode"], plan["cat"], section_name))
    elif extraction_mode in ("local_fast", "local_marker"):
        # موتور ثابتِ محلی → نیازی به پاسِ کندِ تحلیل صفحه‌به‌صفحه نیست (مدل بعداً override می‌شود)
        for i in range(total_pages):
            pages_to_process.append((i, "text", "General", "Full_Book"))
    else:
        # Auto Pilot — تحلیل محتوای هر صفحه برای انتخاب موتور (premium برای جدول/شکل)
        print("   🤖 Analyzing pages to assign engines...")
        for i in range(total_pages):
            try: raw = reader.pages[i].extract_text()
            except: raw = ""
            mode = detect_page_mode(raw)
            pages_to_process.append((i, mode, "General", "Full_Book"))

    # --- 2. Execute Queue ---
    # شماره‌گذاری از روی متنِ fitz (یکدست و قابل‌اعتماد) خوانده می‌شود، مستقل از موتورِ استخراجِ محتوا.
    page_tracker = PageNumberTracker()
    pn_doc = None
    if fitz is not None:
        try:
            pn_doc = fitz.open(file_path)
        except Exception as e:
            print(f"⚠️ fitz نتوانست برای شماره‌گذاری باز کند: {e}")

    for page_idx, mode, cat, section_name in pages_to_process:
        i = page_idx
        
        # 🧠 DECISION LOGIC: Override mode based on user preference
        effective_mode = mode
        if extraction_mode == "online":
            # Force online (premium/fast via Llama)
            pass 
        
        # 1. Resolve abstract "text" mode based on strategy
        if mode == "text":
            if extraction_mode == "online":
                effective_mode = "fast"  # ☁️ Full Online: Use API for text too
            elif extraction_mode == "auto":
                effective_mode = "fitz"  # 🚀 Hybrid: Use Local for text (Best Speed/Cost)
            elif extraction_mode == "local_marker":
                effective_mode = "marker"
            elif extraction_mode == "local_fast":
                effective_mode = "fitz"
            else:
                effective_mode = "fitz"

        # 2. Force Local Override (Downgrade Premium if user wants FULL local)
        if extraction_mode == "local_fast":
            effective_mode = "fitz"
        elif extraction_mode == "local_marker":
            effective_mode = "marker"
            

        print(f"\n💉 Processing: {section_name} (Page {i+1}) | Engine: {effective_mode}")
        
        if i >= len(reader.pages): continue
        
        # --- Page Number Logic (PageNumberTracker روی متنِ fitz، یکدست و تست‌شده) ---
        if pn_doc is not None and i < len(pn_doc):
            pn_text = pn_doc[i].get_text()
        else:
            try: pn_text = reader.pages[i].extract_text()  # fallback اگر fitz نبود
            except: pn_text = ""

        final_page_label = page_tracker.next(pn_text)
        print(f"   PAGE: {final_page_label} (PDF: {i+1})", end="\r")

        # --- Extraction ---
        temp_pdf = os.path.join(temp_dir, f"p_{i}.pdf")
        writer = PdfWriter()
        writer.add_page(reader.pages[i])
        with open(temp_pdf, "wb") as f: writer.write(f)
        
        try:
            if effective_mode == "premium": md = process_with_llama_robust(temp_pdf, "premium")
            elif effective_mode == "fast": md = process_with_llama_robust(temp_pdf, "fast")
            elif effective_mode == "marker": md = process_with_marker(temp_pdf)
            elif effective_mode == "fitz": md = extract_text_fitz(temp_pdf)
            else: md = ""
            
            os.remove(temp_pdf)
            if not md.strip(): continue

            visuals = extract_visual_ids(md)
            
            page_docs = split_content_atomically(
                markdown_text=md,
                page_label=final_page_label,
                section=section_name,
                category=cat,
                visuals=visuals,
                engine=effective_mode,
                source_name=book_name
            )
                
            all_documents.extend(page_docs)
                
        except Exception as e:
            print(f"\n   ❌ Error on page {final_page_label}: {e}")
            if os.path.exists(temp_pdf): os.remove(temp_pdf)

    # Cleanup
    if pn_doc is not None: pn_doc.close()
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

    # ==========================
    # 💾 SAVE TO DISK
    # ==========================
    if not all_documents:
        print("❌ No documents extracted.")
        return

    if not os.path.exists(index_save_path): os.makedirs(index_save_path, exist_ok=True)

    print(f"\n\n💾 Saving Index to {index_save_path}...")

    # 0. 🧬 ذخیره‌ی چانک‌های خام (لایه‌ی آینده‌نگری):
    #    اگر روزی مدل امبدینگ عوض شد، بازسازی از روی این فایل ~چند دقیقه طول می‌کشد،
    #    بدون نیاز به پارس مجدد PDF (مرحله‌ی گران/کند). reembed.py از این می‌خواند.
    chunks_path = os.path.join(index_save_path, "chunks.jsonl")
    try:
        with open(chunks_path, "w", encoding="utf-8") as f:
            for doc in all_documents:
                f.write(json.dumps(
                    {"page_content": doc.page_content, "metadata": doc.metadata},
                    ensure_ascii=False) + "\n")
        print(f"🧬 Saved {len(all_documents)} raw chunks to {chunks_path}")
    except Exception as e:
        print(f"⚠️ Warning: Could not save chunks.jsonl: {e}")

    # 1. امبدینگ از config (پیش‌فرض bge-m3 روی آروان) — هماهنگ با کوئری ربات + batch واقعی
    embeddings = get_rag_embeddings()

    # 2. Save FAISS
    vector_store = None
    BATCH_SIZE = 100
    for i in range(0, len(all_documents), BATCH_SIZE):
        batch = all_documents[i:i+BATCH_SIZE]
        if vector_store is None: vector_store = FAISS.from_documents(batch, embedding=embeddings)
        else: vector_store.add_documents(batch)
        print(f"   Batch {i//BATCH_SIZE + 1} processed.")
    
    vector_store.save_local(index_save_path)

    # 3. Save BM25
    try:
        retriever_bm25 = BM25Retriever.from_documents(all_documents)
        retriever_bm25.k = 5
        with open(os.path.join(index_save_path, BM25_FILENAME), "wb") as f:
            pickle.dump(retriever_bm25, f)
        print("✅ BM25 Index created successfully.")
    except Exception as e:
        print(f"⚠️ Warning: Could not create BM25 index (rank_bm25 missing?). Skipping. Error: {e}")

    print("✅ Indexing completed successfully.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        ingest_book(sys.argv[1])
    else:
        print("Usage: python faiss_ingest.py <pdf_path>")

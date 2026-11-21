# -*- coding: utf-8 -*-
"""پروتوتایپ و اعتبارسنجی PageNumberTracker روی PDFهای واقعی (قبل از وصل به faiss_ingest)."""
import re
import fitz

_ROMAN_VALS = {'i':1,'v':5,'x':10,'l':50,'c':100,'d':500,'m':1000}

def roman_to_int(s: str):
    s = s.strip().lower()
    if not s or not re.fullmatch(r'[ivxlcdm]+', s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALS[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def parse_token(text: str):
    """
    از خطوط ابتدا/انتهای صفحه، شماره‌ی چاپی را استخراج می‌کند.
    خروجی: ('epage', base, suf) | ('arabic', n) | ('roman', n, raw) | None
    اولویت: e-page > عدد عربی > رومی (رومی فقط در front-matter معنا دارد).
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None
    cands = lines[:3] + lines[-3:]

    # 1) e-page مثل 21.e1 یا 707.e2 (نقطه/فاصله بین عدد و e)
    for l in cands:
        m = re.search(r'\b(\d{1,4})[.\s  ]?e(\d{1,3})\b', l, re.I)
        if m:
            return ('epage', int(m.group(1)), int(m.group(2)))

    # 2) عدد عربی خالص (کل خط فقط یک عدد ۱ تا ۴ رقمی)
    for l in cands:
        if re.fullmatch(r'\d{1,4}', l):
            return ('arabic', int(l))

    # 3) رومی خالص (کل خط یک عدد رومی)
    for l in cands:
        n = roman_to_int(l)
        if n is not None:
            return ('roman', n, l)
    return None


class PageNumberTracker:
    """
    شماره‌گذاری تمیز: front-matter رومی، بدنه عربی با لنگرِ عددِ چاپی،
    e-page انتهای فصل، و شمارش صفحات بدون‌شماره از آخرین لنگر.
    """
    DRIFT = 10  # حداکثر فاصله‌ی مجاز بین عددِ تشخیص‌داده‌شده و انتظار (رد اعداد پرت)

    def __init__(self):
        self.body = False        # وارد بدنه‌ی عددی شده‌ایم؟
        self.base = 0            # آخرین شماره‌ی پایه‌ی چاپی
        self.suffix = 0          # شماره‌ی e-page (۰ یعنی صفحه‌ی عادی)
        self.last_roman = 0

    def next(self, page_text: str) -> str:
        tok = parse_token(page_text)

        if tok and tok[0] == 'epage':
            self.body = True
            self.base, self.suffix = tok[1], tok[2]
            return f"{self.base}.e{self.suffix}"

        if tok and tok[0] == 'arabic':
            n = tok[1]
            # اولین عددِ بدنه را بی‌قیدوشرط بپذیر؛ بعد از آن drift-guard
            if not self.body or abs(n - self.base) <= self.DRIFT:
                self.body, self.base, self.suffix = True, n, 0
                return str(self.base)
            # عددِ پرت → مثل صفحه‌ی بدون‌شماره ادامه بده
            return self._increment()

        if tok and tok[0] == 'roman' and not self.body:
            self.last_roman = tok[1]
            return tok[2]  # خود رشته‌ی رومی (مثلا xii)

        # شماره‌ای پیدا نشد
        if not self.body:
            return f"fm{self.last_roman}" if self.last_roman else "fm"
        return self._increment()

    def _increment(self) -> str:
        if self.suffix > 0:
            self.suffix += 1
            return f"{self.base}.e{self.suffix}"
        self.base += 1
        return str(self.base)


def validate(path, label, checks):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    doc = fitz.open(path)
    tracker = PageNumberTracker()
    labels = {}
    n = len(doc)
    for i in range(n):
        lbl = tracker.next(doc[i].get_text())
        labels[i] = lbl
    doc.close()
    # نمایش نمونه‌ها
    show = list(range(0, 27)) + sorted(checks.keys())
    for i in show:
        if i < n:
            print(f"  PDF#{i+1:<5} -> page label: {labels[i]}")
    # بررسی‌های انتظار
    print("  --- CHECKS ---")
    ok = True
    for i, expected in checks.items():
        got = labels.get(i)
        status = "OK" if got == expected else "FAIL"
        if got != expected: ok = False
        print(f"  PDF#{i+1}: expected {expected!r}, got {got!r}  [{status}]")
    print("  RESULT:", "ALL PASS ✅" if ok else "SOME FAIL ❌")


henry = "knowledge_base/books/Henry’s clinical diagnosis and management by laboratory 24th edition.pdf"
hoff  = "knowledge_base/books/Hoffbrand's Postgraduate Haematology 8th edition.pdf"

# انتظارات بر اساس probe قبلی (PDF index -> برچسب چاپی درست)
validate(henry, "HENRY", {19:"2", 20:"3", 21:"4", 22:"5", 40:"21.e1", 60:"40", 300:"260", 800:"707.e2", 1500:"1299"})
validate(hoff,  "HOFFBRAND", {17:"1", 18:"3", 19:"4", 20:"5", 40:"25", 60:"45", 300:"287", 800:"790"})

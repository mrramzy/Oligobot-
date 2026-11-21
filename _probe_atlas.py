# -*- coding: utf-8 -*-
"""بررسی ساختار اطلس هماتولوژی: تعداد صفحات، تصاویر، و وجود کپشن متنی."""
import fitz  # PyMuPDF
import os
import sys

def p(s):
    """چاپ امن در برابر کنسول cp1252 (کاراکترهای غیرقابل‌انکد را جایگزین می‌کند)."""
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.write(str(s).encode(enc, errors="replace").decode(enc) + "\n")

path = os.path.join("knowledge_base", "atlases", "Clinical Hematology Atlas.pdf")
doc = fitz.open(path)
p(f"pages: {doc.page_count}")

total_images = 0
pages_with_text = 0
multi_img_pages = 0
content_pages = 0   # صفحاتی که هم تصویر دارند هم کلمه‌ی FIGURE (صفحات واقعیِ مورفولوژی)
for i, page in enumerate(doc):
    imgs = page.get_images(full=True)
    total_images += len(imgs)
    if len(imgs) > 1:
        multi_img_pages += 1
    txt = page.get_text("text").strip()
    if len(txt) > 40:
        pages_with_text += 1
    if imgs and "FIGURE" in txt.upper():
        content_pages += 1

# نمونه از صفحات محتوایی واقعی (مورفولوژی اریتروسیت ~ صفحه‌ی 90-115 کتاب)
p("\n===== SAMPLE CONTENT PAGES (figure caption pattern) =====")
for idx in (105, 110, 125):
    if idx < doc.page_count:
        pg = doc[idx]
        imgs = pg.get_images(full=True)
        txt = pg.get_text("text").strip()
        p(f"\n--- PDF page {idx+1}: {len(imgs)} images, text len={len(txt)} ---")
        p(txt[:700])

p(f"\n=== SUMMARY ===")
p(f"total embedded images: {total_images}")
p(f"pages with meaningful text (captions?): {pages_with_text}/{doc.page_count}")
p(f"pages with >1 image: {multi_img_pages}")
p(f"CONTENT pages (image + 'FIGURE' caption): {content_pages}  <-- صفحاتِ واقعیِ کپشن‌گذاری")
doc.close()

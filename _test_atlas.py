# -*- coding: utf-8 -*-
"""رانرِ تستِ atlas_ingest روی نمونه‌ی کوچک — UTF-8 امن، بدون نیاز به متغیر محیطی."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
from clinical_rag.atlas_ingest import ingest_atlas

n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
pdf = os.path.join("knowledge_base", "atlases", "Clinical Hematology Atlas.pdf")

# ایندکس تستِ جدا تا ساب‌ایندکس واقعی آلوده نشود
ingest_atlas(pdf, output_dir="knowledge_base", limit=n, resume=False)

# نمایش یک نمونه از chunks ساخته‌شده برای بازبینی کیفیت کپشن
import json
sub = os.path.join("knowledge_base", "Clinical Hematology Atlas")
cj = os.path.join(sub, "chunks.jsonl")
if os.path.exists(cj):
    print("\n" + "=" * 60)
    print("نمونه‌ی چانک‌های ساخته‌شده:")
    with open(cj, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m = r["metadata"]
            print(f"\n--- page {m['page']} | figs={m['visuals']} | img={m['image_path']} ---")
            print(r["page_content"][:700])

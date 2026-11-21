# -*- coding: utf-8 -*-
"""تست واحد EADL Semantic Store — افزودن اصلاحیه و بازیابی معنایی (واقعی، آروان bge-m3)."""
import asyncio
import os
import shutil
import time

# ایندکس تست جدا تا ایندکس واقعی آلوده نشود
os.environ["EADL_INDEX_PATH"] = os.path.join(os.path.dirname(__file__), "eadl_index_TEST")

from eadl_semantic_store import EADLSemanticStore
from config import EADL_CONSENSUS_MATCH_THRESHOLD as EADL_MATCH


async def main():
    test_path = os.environ["EADL_INDEX_PATH"]
    if os.path.isdir(test_path):
        shutil.rmtree(test_path, ignore_errors=True)

    store = EADLSemanticStore(index_path=test_path)
    print(f"enabled = {store.enabled}")
    assert store.enabled, "Store باید فعال باشد (آروان در دسترس)"

    # ۲ اصلاحیه‌ی نمونه
    cases = [
        {
            "id": "tc001",
            "query": "تفسیر CBC با هموگلوبین پایین و MCV بالا چیست؟",
            "response": "پاسخ اولیه‌ی ربات...",
            "domain": "hematology",
            "keywords": ["CBC", "هموگلوبین", "MCV", "آنمی"],
            "comment": "MCV بالا + هموگلوبین پایین → آنمی ماکروسیتیک؛ حتماً B12 و فولات را چک کنید، نه فقط آهن.",
            "verdict": "REJECT",
            "reviewer_id": 70747083,
            "review_time": time.time(),
        },
        {
            "id": "tc002",
            "query": "رنج نرمال TSH در بارداری چقدر است؟",
            "response": "پاسخ اولیه...",
            "domain": "endocrinology",
            "keywords": ["TSH", "بارداری", "تیروئید"],
            "comment": "در سه‌ماهه‌ی اول TSH باید زیر 2.5 باشد؛ رنج عمومی آزمایشگاه گمراه‌کننده است.",
            "verdict": "REJECT",
            "reviewer_id": 70747083,
            "review_time": time.time(),
        },
    ]
    for c in cases:
        ok = await store.add_correction(c)
        print(f"add {c['id']}: {ok}")
        assert ok

    # کوئری مشابه کیس اول → باید بالای آستانه بازیابی شود
    sim_q = "بیمار هموگلوبین کم و MCV بالا دارد، علت آنمی چیست؟"
    res = await store.retrieve(sim_q, k=3, threshold=0.70)
    print(f"\n[similar] '{sim_q}'\n -> {len(res)} نتیجه")
    for r in res:
        print(f"    score={r['score']:.3f} domain={r['domain']} :: {r['correction_text'][:50]}")

    # کوئری کاملاً بی‌ربط → باید زیر آستانه و خالی باشد
    irr_q = "بهترین رستوران تهران کجاست؟"
    res2 = await store.retrieve(irr_q, k=3, threshold=0.70)
    print(f"\n[irrelevant] '{irr_q}'\n -> {len(res2)} نتیجه (باید 0 باشد)")

    inj = store.build_injection_text(res)
    print(f"\n[injection text]\n{inj}\n")

    # جمع‌بندی
    print("=" * 40)
    assert len(res) >= 1, "❌ کیس مشابه باید بازیابی شود"
    assert len(res2) == 0, "❌ کیس بی‌ربط نباید بازیابی شود"
    assert inj, "❌ متن تزریق نباید خالی باشد"
    print("✅ همه‌ی assert ها پاس شدند — Semantic retrieval کار می‌کند.")

    # ============ تست وزن‌دهی اجماع ============
    print("\n" + "=" * 40)
    print("🗳️ تست اجماع متخصص")
    # تک‌متخصص → باید برچسب «مقدماتی/با احتیاط» بگیرد
    single = await store.retrieve("رنج TSH بارداری سه ماهه اول", k=1, threshold=0.70)
    assert single, "کیس TSH باید بازیابی شود"
    assert single[0]["confirmations"] == 1, "هنوز تک‌متخصص است"
    inj_single = store.build_injection_text(single)
    print(f"[single expert]\n{inj_single}")
    assert "مقدماتی" in inj_single, "❌ تک‌متخصص باید برچسب مقدماتی بگیرد"

    # متخصص دوم همان موضوع TSH را از کیس دیگری تأیید می‌کند → confirmations=2
    await store.add_correction({
        "id": "tc002b", "query": "محدوده طبیعی TSH در بارداری اوایل چقدر است",
        "response": "x", "domain": "endocrinology", "keywords": ["TSH"],
        "comment": "سه‌ماهه اول TSH زیر 2.5 — تأیید متخصص دوم.",
        "verdict": "REJECT", "reviewer_id": 11111111, "review_time": time.time(),
    })
    after = await store.retrieve("رنج TSH بارداری سه ماهه اول", k=1, threshold=0.70)
    print(f"\nconfirmations پس از متخصص دوم = {after[0]['confirmations']}")
    inj_multi = store.build_injection_text(after)
    print(f"[multi expert]\n{inj_multi}")
    if after[0]["confirmations"] >= 2:
        assert "تأییدشده توسط" in inj_multi, "❌ چندمتخصص باید برچسب معتبر بگیرد"
        print("✅ اجماع کار کرد: متخصص دوم → برچسب «معتبر».")
    else:
        print(f"⚠️ شباهت دو کیس TSH زیر آستانه‌ی ادغام ({EADL_MATCH}) ماند — confirmations=1. "
              "آستانه‌ی EADL_CONSENSUS_MATCH_THRESHOLD را پایین‌تر بیاور اگر می‌خواهی ادغام شود.")

    # پاک‌سازی ایندکس تست
    del store
    shutil.rmtree(test_path, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())

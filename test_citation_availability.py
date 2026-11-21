# -*- coding: utf-8 -*-
"""
🧪 Citation Performance Test
بررسی عملکرد سیستم RAG در بازیابی و ارجاع‌دهی به منابع
"""
import asyncio
import os
import sys
from typing import List, Dict, Any

# افزودن مسیر پروژه به path برای ایمپورت ماژول‌ها
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_engine import RAGSystem
from async_rag_search import knowledge_base_orchestrator

# تنظیمات تست
TEST_QUERY = "Hemoglobin"  # کوئری که حتماً در دیتابیس موجود است
TEST_USER_ID = 999999
MOCK_HISTORY = []

async def test_retrieval_only():
    """تست مستقیم لایه جستجو (Retrieval Layer)"""
    print(f"\n🔍 [TEST 1] Testing Knowledge Retrieval for: '{TEST_QUERY}'")
    
    if not knowledge_base_orchestrator.provider:
        print("❌ Knowledge Base Provider is NOT active.")
        return False

    results = await knowledge_base_orchestrator.search(TEST_QUERY, k=3)
    
    if results:
        print(f"✅ Found {len(results)} documents.")
        for i, doc in enumerate(results):
            source = doc.get('source', 'Unknown')
            page = doc.get('page', 'N/A')
            content_snippet = doc.get('content', '')[:50].replace('\n', ' ')
            print(f"   📄 Doc {i+1}: [{source}, Pg {page}] -> {content_snippet}...")
        return True
    else:
        print("❌ No documents found in Knowledge Base.")
        return False

async def test_full_rag_pipeline():
    """تست کامل پایپ‌لاین RAG شامل تولید پاسخ و ارجاع‌دهی"""
    print(f"\n🤖 [TEST 2] Testing Full RAG Pipeline (Generation + Citation)")
    
    rag = RAGSystem()
    
    # استراتژی تست
    strategy = {
        "use_rag": True,
        "mode": "text",
        "intent": "EDUCATIONAL",
        "show_references": True
    }

    print("   ⏳ Generating response... (this may take a few seconds)")
    final_answer, sources_text, eadl_meta = await rag.process_query(
        user_id=TEST_USER_ID,
        user_query=f"What is the normal range of {TEST_QUERY}?",
        chat_history=MOCK_HISTORY,
        strategy=strategy
    )
    
    print("\n📝 FINAL ANSWER OUTPUT:")
    print("-" * 40)
    print(final_answer[:500] + "..." if len(final_answer) > 500 else final_answer)
    print("-" * 40)
    
    # بررسی وجود لینک‌های تلگرامی (فرمت ارجاع)
    # فرمت مورد انتظار: [Source Name, Page X](...) یا متن مشابه
    has_citation = "Reference" in final_answer or "Source:" in final_answer or "[" in final_answer
    
    if has_citation:
        print("\n✅ CITATION CHECK PASSED: References detected in output.")
    else:
        print("\n⚠️ CITATION CHECK WARNING: No obvious citations found in the text.")

async def main():
    print("🚀 STARTING CITATION PERFORMANCE TEST")
    print("=" * 40)
    
    # 1. بررسی اینکه آیا اصلاً داکیومنت پیدا می‌شود
    retrieval_success = await test_retrieval_only()
    
    if retrieval_success:
        # 2. بررسی اینکه آیا LLM از آن استفاده می‌کند
        await test_full_rag_pipeline()
    else:
        print("\n⛔ Skipping full pipeline test because retrieval failed.")
    
    print("\n🏁 TEST COMPLETE")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

# -*- coding: utf-8 -*-
"""
Benchmark: measure end-to-end latency for each intent type.
Simulates the exact code path a Telegram message follows.
"""
import asyncio
import sys
import time
import statistics

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Pre-warm imports (same order as app.py)
from ai_models import generate_response, generate_response_stream
from rag_engine import RAGSystem
from intent_manager import intent_manager, Intent
from query_refinement import refine_search_query, refine_search_query_offline
from input_validator import InputValidator
from state_manager import RedisStateManager
from user_manager import UserManager
from case_memory import CaseMemoryStore

rag = RAGSystem()
state = RedisStateManager(host="localhost", port=6379)
user_mgr = UserManager()
validator = InputValidator()
case_store = CaseMemoryStore()

TEST_QUERIES = {
    "CASUAL":     "سلام، حالت چطوره؟",
    "EDUCATIONAL": "رنج نرمال هموگلوبین چنده؟",
    "DIAGNOSTIC":  "بیمار ۴۵ ساله مرد با خستگی مزمن و رنگ پریدگی مراجعه کرده. هموگلوبین ۸.۲. چه تشخیص‌های افتراقی مدنظره؟",
    "IRRELEVANT": "قیمت دلار امروز چنده؟",
}

ITERATIONS = 2  # per query type

async def measure_single(query_text: str, intent_name: str, mode="text") -> dict:
    """Run the full pipeline once and return timing breakdown."""
    t_start = time.perf_counter()

    # Intent detection
    t0 = time.perf_counter()
    intent = await intent_manager.detect_intent(query_text, [])
    t_intent = time.perf_counter() - t0

    # RAG search + LLM (streaming path — the one users actually see)
    use_rag = intent not in (Intent.CASUAL, Intent.IRRELEVANT)
    strategy = {
        "use_rag": use_rag, "mode": mode,
        "intent": intent.name, "language": "fa",
        "show_references": True, "career_context": ""
    }
    from utils import get_time_metadata, detect_language
    metadata = {"time_meta": get_time_metadata(), "detected_domain": "general"}

    t0 = time.perf_counter()
    llm_stream, retrieved_docs, eadl_meta = await rag.process_query_stream(
        user_id=99999, user_query=query_text, chat_history=[],
        strategy=strategy, metadata=metadata
    )
    t_rag_prep = time.perf_counter() - t0

    # Consume stream
    t0 = time.perf_counter()
    chunks = []
    async for chunk in llm_stream:
        chunks.append(chunk)
    t_llm_stream = time.perf_counter() - t0

    total = time.perf_counter() - t_start
    full_text = "".join(chunks)

    return {
        "intent": intent.name,
        "query": query_text[:40],
        "total": round(total, 2),
        "intent_det": round(t_intent, 2),
        "rag_prep": round(t_rag_prep, 2),
        "llm_stream": round(t_llm_stream, 2),
        "chunks": len(chunks),
        "chars": len(full_text),
    }


async def run_benchmark():
    print("=" * 75)
    print("  OLIGOBOT V10 — Response Time Benchmark")
    print("=" * 75)

    results = []
    for intent_name, query in TEST_QUERIES.items():
        print(f"\n--- {intent_name} ---")
        for i in range(ITERATIONS):
            r = await measure_single(query, intent_name)
            results.append(r)
            print(f"  [{i+1}] {r['total']}s total | intent={r['intent_det']}s "
                  f"rag_prep={r['rag_prep']}s llm={r['llm_stream']}s | {r['chars']}ch {r['chunks']} chunks")

    # Summary
    print("\n" + "=" * 75)
    print("  SUMMARY (averages across all iterations)")
    print("=" * 75)

    by_intent = {}
    for r in results:
        key = r["intent"]
        by_intent.setdefault(key, []).append(r)

    for intent, runs in by_intent.items():
        avg_total = statistics.mean([r["total"] for r in runs])
        avg_rag = statistics.mean([r["rag_prep"] for r in runs])
        avg_llm = statistics.mean([r["llm_stream"] for r in runs])
        print(f"  {intent:12s} | total={avg_total:.1f}s  "
              f"rag={avg_rag:.1f}s  llm={avg_llm:.1f}s")

    overall = statistics.mean([r["total"] for r in results])
    print(f"\n  OVERALL AVG: {overall:.1f}s")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_benchmark())

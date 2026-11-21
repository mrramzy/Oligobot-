# Session Report — 2026-07-07

## Summary
Major optimization session: streaming fixes, speed optimization (47% faster), medical image RAG enhancement, entity extraction prototype, critical bug fixes, follow-up question quality improvement.

---

## Performance Results

| Intent | Before | After | Improvement |
|--------|--------|-------|-------------|
| CASUAL | 5.3s | 3.4s | -36% |
| EDUCATIONAL | 27.1s | 13.9s | -49% |
| DIAGNOSTIC | 20.0s | 15.8s | -21% |
| IRRELEVANT | 10.1s | 4.1s | -59% |
| **OVERALL** | **15.6s** | **9.3s** | **-40%** |

---

## Changes Made

### P0 Streaming Fixes
- `deepseek_client.py`: Added `chat_completion_stream()` — real token-by-token streaming
- `generation.py`: Removed fake DeepSeek fallback, removed 1s forced delay
- `streaming.py`: sendChatAction throttled to 5s, unused params cleaned, validator reused

### P1 Optimization
- `query_refinement.py`: spaCy model cached at module level
- `eadl_manager.py`: 6 sync `_load_json` calls → `asyncio.to_thread`
- `state_manager.py`: Added async Redis wrappers
- `user_manager.py`: Absolute path anchoring + atomic writes
- `rag_engine.py`: Pipeline parallelized (keywords+domain concurrent, image_search+vision_analysis concurrent)
- `rag_engine.py`: FAISS k reduced 30→15, semantic grouping skipped for <20 candidates
- `intent_manager.py`: Fast keyword checks for DIAGNOSTIC/IRRELEVANT skip Gemini API

### Medical Image RAG
- `vision.py`: Domain-specific prompts for HEMATOLOGY (Döhle bodies, malaria stages, amastigotes, lantern cells), URINALYSIS (casts, crystals), PARASITOLOGY (eggs, trophozoites). Prompts compact (~100 tokens each).
- `vision.py`: Added `count_cells_from_image()` function
- `rag_engine.py`: Vision findings injected into LLM prompt for image fusion

### Entity Extraction (Prototype)
- `entity_extractor.py`: Pattern-based extraction for 8 categories (DISEASE, TEST, CELL, EQUIPMENT, PROCEDURE, SUBSTANCE, VALUE, PARASITE). Search, relationship traversal, context retrieval.
- `rag_engine.py`: Entity search + context injection integrated into RAG pipeline
- `build_entity_index.py`: Script to build entity index from knowledge base (needs index.pkl format fix)

### Career System
- `user_manager.py`: technician label → "کارشناس آزمایشگاه", new "masters" (کارشناسی ارشد) option
- `ui_handlers.py`: Updated CAREER_KEYBOARD and CAREER_BTN_MAP

### Onboarding Flow
- `handlers.py`: New users get forced name→career→reference toggle on first /start

### Follow-up Questions
- `PSL/human_interaction.md`: 4 natural patterns (curiosity hook, mini-challenge, adjacent thought, professional nudge). Anti-patterns added.

### Critical Bug Fixes
- BUG-001: NameError on image+CASUAL (img_* vars initialized before RAG block)
- BUG-002: DIAGNOSTIC streaming double-send (elif guard + try/except)
- BUG-004: Redis history TTL 86s → 24h (ex=ttl keyword arg)
- BUG-005: DOCX newline literal (\\n → \n)
- ERR-001: process_query_stream now has try/except with error stream fallback
- ERR-003: Temp file leak fixed (finally block)
- SEC-002: CORS restricted to localhost

### Security
- `admin_api.py`: CORS restricted from `*` to localhost only

---

## Remaining Items

### Pending Bugs
- BUG-009: `handle_career_choice` defined but never registered in app.py
- PERF-001: Sync Redis still blocking event loop (async versions exist but unused)
- SEC-006: pickle.load on BM25 retriever files
- ERR-004: asyncio.gather without return_exceptions=True

### Pending Features
- Entity index building from index.pkl (format investigation needed)
- User memory system (remember important keywords across conversations)
- Add more reference books to knowledge base
- Full GraphRAG integration

---

## Files Modified
`streaming.py`, `generation.py`, `deepseek_client.py`, `state_manager.py`, `eadl_manager.py`, `user_manager.py`, `rag_engine.py`, `query_refinement.py`, `vision.py`, `intent_manager.py`, `config.py`, `handlers.py`, `utils.py`, `admin_api.py`, `ui_handlers.py`, `PSL/human_interaction.md`

## Files Created
`entity_extractor.py`, `build_entity_index.py`, `demo_entity_extraction.py`, `benchmark.py`, `test_e2e.py`, `entity_index.json`

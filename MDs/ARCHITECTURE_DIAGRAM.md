# OLIGOBOT V2 — System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER (Telegram)                              │
│                    asks medical question                             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HANDLERS.PY — Message Router                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ /start   │ │ /memory  │ │ /new     │ │ /sub     │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│  ┌─────────────────────────────────────────────────────┐           │
│  │ Intent Detection (CASUAL / DIAGNOSTIC / EDUCATIONAL)│           │
│  └─────────────────────────────────────────────────────┘           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  RAG ENGINE (rag_engine.py) — The Brain                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │ 1. VALIDATE INPUT                                        │       │
│  │ 2. EXTRACT KEYWORDS + DOMAIN (parallel)                  │       │
│  │ 3. RAG SEARCH (parallel)                                 │       │
│  │    ├─ Query Refinement (LLM)                             │       │
│  │    ├─ FAISS Vector Search (bge-m3)                       │       │
│  │    ├─ BM25 Keyword Search (per book)                     │       │
│  │    ├─ Entity Search (knowledge graph)          ← NEW     │       │
│  │    ├─ Semantic Grouping (dedup)                           │       │
│  │    └─ CrossEncoder Reranking + Authority Boost           │       │
│  │ 4. BUILD PROMPT                                          │       │
│  │    ├─ Time Context                                        │       │
│  │    ├─ User Memory Context                       ← NEW     │       │
│  │    ├─ EADL Expert Corrections                            │       │
│  │    ├─ Entity Knowledge Graph                    ← NEW     │       │
│  │    ├─ RAG Context + Citations                             │       │
│  │    └─ System Prompts (PSL/)                               │       │
│  │ 5. GENERATE RESPONSE (DeepSeek/Gemini)                   │       │
│  │ 6. FORMAT WITH CITATIONS                                 │       │
│  └─────────────────────────────────────────────────────────┘       │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│ FAISS INDEX  │   │ ENTITY INDEX │   │ USER MEMORY      │
│ (brain_index)│   │ (entity_     │   │ (user_memory.    │
│              │   │  index.json) │   │  json)           │
│ 24,094 chunks│   │ 411 entities │   │ per-user topics  │
│ 3 books      │   │ 6,759 rels   │   │ cross-session    │
│ bge-m3 embed │   │ 8 categories │   │ Gemini extract   │
└──────────────┘   └──────────────┘   └──────────────────┘
```

## Knowledge Base Pipeline (Adding New Books)

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: DROP PDF INTO knowledge_base/                       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: CLINICAL RAG MANAGER v3.0                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ FAISS Engine │ │ ATLAS Engine │ │ CHROMA Engine│        │
│  │ (text books) │ │ (image books)│ │ (guidelines) │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: MERGE → brain_index/                                │
│  merge_and_save() rebuilds unified FAISS + BM25              │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: REBUILD ENTITY INDEX                                │
│  build_entity_index.py extracts entities from ALL chunks     │
│  → 411+ entities, 6759+ relationships                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: READY FOR PRODUCTION                                │
│  Entity context automatically injected into RAG responses    │
└─────────────────────────────────────────────────────────────┘
```

## Entity Categories (411 total)

```
DISEASE (60)  ──── DIAGNOSES ────→ TEST (98)
    │                                   │
    │ CAUSED_BY                         │ MEASURES
    ▼                                   ▼
AGENT/PARASITE (55)              SUBSTANCE (52)
    │                                   │
    │ STAGE_OF                          │ STAINS_WITH
    ▼                                   ▼
CELL (70) ←────────────────── PROCEDURE (40)
    │
    │ ASSOCIATED_WITH
    ▼
EQUIPMENT (33)
```

## New Features Summary

| Feature | Status | Impact |
|---------|--------|--------|
| User Memory | ✅ Active | Personalized responses across sessions |
| Entity Knowledge Graph | ✅ Active | Multi-hop reasoning, disease-test connections |
| SafeUnpickler (SEC-006) | ✅ Active | Secure index loading |
| Async Redis (PERF-001) | ✅ Active | Non-blocking event loop |
| Career Mode | ✅ Active | Adapted responses by profession |
| Follow-up Questions | ✅ Active | Human-like engagement |

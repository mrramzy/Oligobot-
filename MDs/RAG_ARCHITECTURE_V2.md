# OLIGOBOT RAG Architecture V2 — Entity-Enhanced + GraphRAG

**Date**: 2026-07-09
**Author**: Dev Team Lead
**Status**: Implementation In Progress

---

## Executive Summary

OLIGOBOT's current RAG system retrieves documents via vector similarity search (FAISS) + BM25 keyword search, then reranks with a Cross-Encoder. This works well for direct factual queries but **fails at multi-hop reasoning** — questions that require connecting information across multiple documents.

**Example failure**: "What test confirms the disease caused by Plasmodium, and what stain visualizes its ring stage?"

Current RAG retrieves documents about malaria AND documents about staining separately. It never connects: `Plasmodium → causes malaria → confirmed by peripheral smear → ring stage visualized by Giemsa stain`.

**The solution**: Entity-Enhanced RAG with a lightweight knowledge graph. This gives the bot the ability to **traverse relationships** between medical concepts, enabling multi-hop answers without the infrastructure cost of full GraphRAG.

---

## Current Architecture (V1)

```
User Query
    │
    ▼
┌─────────────────────────────┐
│  Query Refinement (LLM)     │  ← Generates English search variants
└─────────────┬───────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌─────────┐      ┌──────────┐
│  FAISS  │      │  BM25    │  ← Parallel vector + keyword search
│ (bge-m3)│      │ (Okapi)  │
└────┬────┘      └────┬─────┘
     │                │
     ▼                ▼
┌─────────────────────────────┐
│  Semantic Grouping (dedup)  │  ← Remove near-duplicate docs
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Cross-Encoder Reranking    │  ← bge-reranker-base + authority boost
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  LLM Response Generation    │  ← DeepSeek/Gemini with top-5 docs
└─────────────────────────────┘
```

**Strengths**: Fast, accurate for direct queries, good citation support.
**Weaknesses**: No multi-hop reasoning, no entity awareness, no relationship traversal.

---

## New Architecture (V2) — Entity-Enhanced RAG

### Design Principles

1. **Lightweight**: No heavy graph database (Neo4j, Nebula). Use JSON-based entity index + in-memory traversal.
2. **Incremental**: Build on existing FAISS + BM25 infrastructure. Don't replace — enhance.
3. **Practical**: Focus on the 80% use case — medical lab Q&A with entity connections.
4. **Observable**: Every entity lookup and relationship traversal is logged for debugging.

### Architecture Diagram

```
User Query: "What test confirms malaria and what stain shows ring stage?"
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 1: Entity Extraction (from query)            │
│  ┌─────────────────────────────────────────────┐    │
│  │ Pattern Match + Entity Index Lookup          │    │
│  │ → Found: "malaria" (DISEASE)                │    │
│  │ → Found: "ring stage" (CELL)                │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 2: Relationship Traversal                    │
│  ┌─────────────────────────────────────────────┐    │
│  │ malaria → [DIAGNOSES] → peripheral smear    │    │
│  │ malaria → [CAUSED_BY] → Plasmodium          │    │
│  │ ring stage → [STAGE_OF] → Plasmodium        │    │
│  │ ring stage → [VISUALIZED_BY] → Giemsa stain │    │
│  │ peripheral smear → [USES] → Giemsa stain    │    │
│  └─────────────────────────────────────────────┘    │
│  → Entity context: 5 connected facts                │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 3: Enhanced RAG Search                       │
│  ┌─────────────────────────────────────────────┐    │
│  │ Original query variants (existing pipeline) │    │
│  │ + Entity-derived search terms:              │    │
│  │   "malaria peripheral smear"                │    │
│  │   "Plasmodium ring stage Giemsa"            │    │
│  │   "malaria diagnosis confirmation"          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │
    ┌─────────────────┴─────────────────┐
    ▼                                   ▼
┌─────────┐                    ┌──────────────┐
│  FAISS  │                    │ Entity Index │
│  + BM25 │                    │ (traversal)  │
└────┬────┘                    └──────┬───────┘
     │                                │
     ▼                                ▼
┌─────────────────────────────────────────────────────┐
│  STAGE 4: Context Fusion                            │
│  ┌─────────────────────────────────────────────┐    │
│  │ System prompt includes:                     │    │
│  │ 1. RAG retrieved docs (existing)            │    │
│  │ 2. Entity context (NEW):                    │    │
│  │    "Entity: malaria (DISEASE)               │    │
│  │     Related: Plasmodium falciparum          │    │
│  │     Confirmed by: peripheral blood smear    │    │
│  │     Visualized with: Giemsa stain           │    │
│  │     Ring stage: pathognomonic finding"      │    │
│  │ 3. User memory context (existing)           │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  LLM Response Generation                            │
│  → Multi-hop answer with entity connections          │
└─────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Entity Index (`entity_index.json`)

**Current state**: 30 entities, 0 relationships (prototype)
**Target state**: 500+ entities, 1000+ relationships (from full knowledge base)

**Schema**:
```json
{
  "entities": {
    "DISEASE:malaria": {
      "category": "DISEASE",
      "name": "malaria",
      "sources": ["Clinical Hematology Atlas", "Hoffbrand's"],
      "context_snippets": ["Malaria is caused by Plasmodium species..."],
      "aliases": ["paludism", "marsh fever"]
    }
  },
  "relationships": [
    {
      "type": "DIAGNOSES",
      "source": "malaria",
      "target": "peripheral blood smear",
      "context": "Malaria is confirmed by identifying parasites on peripheral smear",
      "source_doc": "Clinical Hematology Atlas"
    }
  ]
}
```

### 2. Entity Extraction Pipeline

**Phase 1 — Pattern-based** (existing): Fast, deterministic extraction of known medical terms.
**Phase 2 — LLM-assisted** (planned): Use Gemini light to extract entities from chunks that pattern matching misses.

### 3. Relationship Types

| Type | Pattern | Example |
|------|---------|---------|
| DIAGNOSES | Disease → confirmed by → Test | Malaria → peripheral smear |
| MEASURES | Test → measures → Substance | CBC → hemoglobin |
| PRODUCES | Equipment → performs → Test | Autoanalyzer → CBC |
| STAINS_WITH | Cell → visualized by → Stain | Blast → MPO stain |
| INDICATES | Finding → suggests → Disease | Schistocytes → TTP/HUS |
| DIFFERENTIAL | Disease ↔ differential → Disease | APL vs AML |
| STAGE_OF | Stage → belongs to → Species | Ring stage → Plasmodium |
| REFERENCE | Test → reference range → Value | Hemoglobin → 12-16 g/dl |
| CAUSED_BY | Disease → caused by → Agent | Malaria → Plasmodium |
| TREATED_BY | Disease → treated by → Drug | Malaria → artemisinin |

### 4. Enhanced Search Queries

When entities are found in the query, we generate **entity-aware search variants**:

```
Original: "What test confirms malaria?"
Entity found: malaria (DISEASE)
Relationships: DIAGNOSES → peripheral smear, CAUSED_BY → Plasmodium

Enhanced queries:
1. "malaria confirmation test" (original)
2. "peripheral blood smear malaria" (from DIAGNOSES relationship)
3. "Plasmodium detection laboratory" (from CAUSED_BY relationship)
4. "malaria Giemsa stain ring stage" (from entity traversal)
```

### 5. Context Injection

Entity context is injected as a **system message** before the RAG context:

```
ENTITY KNOWLEDGE GRAPH:
Topic: malaria (DISEASE)
├── Caused by: Plasmodium falciparum, P. vivax, P. malariae, P. ovale
├── Confirmed by: peripheral blood smear, thick smear, thin smear
├── Visualized with: Giemsa stain, Wright stain
├── Key finding: ring stage trophozoite
├── Differential: babesiosis, artifact
└── Severity indicators: parasitemia >5% (severe), >2% (uncomplicated)
```

---

## Implementation Plan

### Phase 1: Entity Index Rebuild (Current Session)
- [x] Fix `build_entity_index.py` to work with SafeUnpickler
- [ ] Run entity extraction on full knowledge base (3 books)
- [ ] Add relationship extraction patterns
- [ ] Verify entity search quality

### Phase 2: Enhanced RAG Integration (Next Session)
- [ ] Entity-aware query expansion in `rag_engine.py`
- [ ] Entity context injection into prompt
- [ ] Relationship traversal for multi-hop queries
- [ ] Performance benchmarking

### Phase 3: Knowledge Base Expansion
- [ ] Add new medical books/references to FAISS index
- [ ] Rebuild entity index with new sources
- [ ] Validate citation accuracy

### Phase 4: Production Testing
- [ ] Live bot testing on Telegram
- [ ] Multi-hop query testing
- [ ] User experience audit
- [ ] Performance optimization

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Entity extraction misses important terms | LLM-assisted extraction as fallback |
| Relationship extraction produces false positives | Confidence scoring + human review |
| Token budget overflow from entity context | Cap at 5 entities, 3 relationships each |
| Slow query processing from traversal | In-memory traversal (<10ms for 1000 entities) |
| Stale entity index | Rebuild script runs on knowledge base update |

---

## Success Metrics

| Metric | Current (V1) | Target (V2) |
|--------|-------------|-------------|
| Direct factual accuracy | ~85% | ~90% |
| Multi-hop reasoning accuracy | ~30% | ~70% |
| Entity coverage (known entities) | 30 | 500+ |
| Relationship coverage | 0 | 1000+ |
| Average response time | 9.3s | <12s |
| Token usage per query | ~2000 | <3000 |

---

## Appendix: Files Involved

| File | Role | Status |
|------|------|--------|
| `entity_extractor.py` | Entity extraction + index management | ✅ Working |
| `build_entity_index.py` | Build index from knowledge base | ⚠️ Needs SafeUnpickler fix |
| `entity_index.json` | Persistent entity storage | ✅ 30 entities (needs rebuild) |
| `rag_engine.py` | RAG pipeline (entity injection point) | ✅ Modified |
| `async_rag_search.py` | FAISS + BM25 search | ✅ Working |
| `brain_index/index.pkl` | FAISS document store | ✅ 3 books indexed |
| `brain_index/*.pkl` | BM25 retrievers | ✅ 3 books |

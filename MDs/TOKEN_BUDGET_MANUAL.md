# OLIGOBOT Token Budget Manual
# راهنمای بودجه توکن الیگوسافت

---

## Overview

This manual explains how many tokens each component of the OLIGOBOT RAG system uses per query, and how to configure limits for business planning.

**Token estimation:** ~3.5 chars per token (mixed Persian/English medical content)

---

## Token Flow Diagram

```
User Query: "فیریتین رنج نرمالش چنده؟"
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  INPUT TOKENS (what the LLM receives)                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 1. SYSTEM PROMPTS (PSL/)           ~2,350 tokens │   │
│  │    - system_core.md                 ~350 tokens   │   │
│  │    - prompt_injection_shield.md     ~450 tokens   │   │
│  │    - human_interaction.md           ~1,550 tokens │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 2. RAG DOCUMENTS (from FAISS)      ~1,500 tokens │   │
│  │    - 5 documents × ~300 tokens each              │   │
│  │    - Includes: source, page, content              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 3. ENTITY CONTEXT (from JSON)      ~250 tokens   │   │
│  │    - 3 entities × ~80 tokens each                │   │
│  │    - Includes: relationships, page refs           │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 4. USER MEMORY (from JSON)         ~60 tokens    │   │
│  │    - 5 topics × ~12 tokens each                  │   │
│  │    - What user discussed before                   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 5. CONVERSATION HISTORY            ~250 tokens   │   │
│  │    - 4 recent messages × ~50 tokens each         │   │
│  │    - Or 1 summary + 4 messages                   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ 6. OTHER (time, citations, etc.)   ~200 tokens   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  TOTAL INPUT: ~4,600 tokens (typical)                    │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  OUTPUT TOKENS (what the LLM generates)                  │
│                                                          │
│  Response: ~500-1,500 tokens                             │
│  (depends on complexity, set by MAX_OUTPUT_TOKENS)        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
TOTAL PER QUERY: ~5,000-6,000 tokens
```

---

## Component Breakdown

### 1. System Prompts (PSL/)
| File | Tokens | When Loaded |
|------|--------|-------------|
| `system_core.md` | ~350 | ALWAYS |
| `prompt_injection_shield.md` | ~450 | ALWAYS |
| `human_interaction.md` | ~1,550 | ALWAYS |
| `diagnostic_protocol.md` | ~900 | DIAGNOSTIC intent |
| `hematology.md` | ~950 | Image + hematology |
| **TOTAL (EDUCATIONAL)** | **~2,350** | — |
| **TOTAL (DIAGNOSTIC)** | **~4,200** | — |

**Config:** Edit `.md` files in `PSL/` directory. Fewer words = fewer tokens.

---

### 2. RAG Documents
| Parameter | Default | Config Env Var |
|-----------|---------|----------------|
| Documents sent to LLM | 5 | `RAG_MAX_DOCS` |
| Chars per document | 800 | `RAG_MAX_DOC_CHARS` |
| Search results retrieved | 15 | `RAG_SEARCH_K` |

**Token math:** 5 docs × 800 chars ÷ 3.5 = **~1,140 tokens** (content only)
**With metadata:** ~1,500 tokens total

**Config:** Set `RAG_MAX_DOCS=3` for cheaper queries (less context but faster/cheaper).

---

### 3. Entity Context
| Parameter | Default | Config Env Var |
|-----------|---------|----------------|
| Entities searched | 3 | `ENTITY_TOP_K` |
| Related entities per entity | 2 | `ENTITY_RELATED_PER_ENTITY` |
| Relationships per entity | 5 | `ENTITY_MAX_RELATIONSHIPS` |

**Token math:** 3 entities × 80 tokens = **~240 tokens**

**Config:** Set `ENTITY_TOP_K=1` for minimal entity context.

---

### 4. User Memory
| Parameter | Default | Config Env Var |
|-----------|---------|----------------|
| Topics injected | 5 | `MEMORY_MAX_TOPICS` |
| Keywords per topic | 3 | `MEMORY_KEYWORDS_PER_TOPIC` |

**Token math:** 5 topics × 12 tokens = **~60 tokens**

**Config:** Set `MEMORY_MAX_TOPICS=3` for less memory context.

---

### 5. Conversation History
| Parameter | Default | Config Env Var |
|-----------|---------|----------------|
| Max messages before summarize | 10 | `HISTORY_MAX_MESSAGES` |
| Messages kept after summarize | 4 | `HISTORY_KEEP_RECENT` |

**Token math:** 4 messages × 50 tokens = **~200 tokens**

**Config:** Set `HISTORY_KEEP_RECENT=2` for minimal history.

---

### 6. EADL (Experience Layer)
| Parameter | Default | Config Env Var |
|-----------|---------|----------------|
| Corrections retrieved | 3 | `EADL_TOP_K` |
| Similarity threshold | 0.70 | `EADL_SIM_THRESHOLD` |

**Token math:** ~200 tokens (when active)

**Config:** Set `EADL_TOP_K=0` to disable EADL completely.

---

## Cost Scenarios

### Scenario 1: Minimum Cost (Casual Chat)
```bash
export RAG_MAX_DOCS=0
export ENTITY_TOP_K=0
export MEMORY_MAX_TOPICS=0
export HISTORY_KEEP_RECENT=2
```
**Tokens:** ~2,750 input + 500 output = **~3,250 total**
**Cost per query:** ~$0.0003 (Gemini) / ~$0.001 (DeepSeek)

### Scenario 2: Standard Educational
```bash
export RAG_MAX_DOCS=5
export ENTITY_TOP_K=3
export MEMORY_MAX_TOPICS=5
export HISTORY_KEEP_RECENT=4
```
**Tokens:** ~4,490 input + 1,000 output = **~5,490 total**
**Cost per query:** ~$0.0006 (Gemini) / ~$0.002 (DeepSeek)

### Scenario 3: Full Diagnostic + Image
```bash
export RAG_MAX_DOCS=5
export ENTITY_TOP_K=3
export MEMORY_MAX_TOPICS=5
export HISTORY_KEEP_RECENT=4
```
**Tokens:** ~5,640 input + 1,500 output = **~7,140 total**
**Cost per query:** ~$0.0009 (Gemini) / ~$0.003 (DeepSeek)

---

## Monthly Cost Projections

| Queries/Month | Gemini Flash Lite | DeepSeek V3 |
|---------------|-------------------|-------------|
| 1,000 | $0.80 | $2.92 |
| 5,000 | $4.01 | $14.58 |
| 10,000 | $8.02 | $29.16 |
| 30,000 | $24.05 | $87.49 |
| 100,000 | $80.17 | $291.63 |

**Note:** These are estimates. Actual costs depend on:
- Mix of query types (casual vs diagnostic)
- Output length (compound answers are longer)
- Caching (repeated queries cost less)

---

## How to Adjust for Business Plans

### For Free Tier (Cost-Sensitive)
```bash
# Minimal tokens
export RAG_MAX_DOCS=3
export ENTITY_TOP_K=1
export MEMORY_MAX_TOPICS=2
export HISTORY_KEEP_RECENT=2
export MAX_OUTPUT_TOKENS=800
```
**Estimated:** ~3,500 tokens/query → **$0.50/month per 1000 users**

### For Pro Tier (Quality-Focused)
```bash
# Full quality
export RAG_MAX_DOCS=5
export ENTITY_TOP_K=3
export MEMORY_MAX_TOPICS=5
export HISTORY_KEEP_RECENT=4
export MAX_OUTPUT_TOKENS=1500
```
**Estimated:** ~6,000 tokens/query → **$2.50/month per 1000 users**

### For Enterprise (Maximum Quality)
```bash
# No limits
export RAG_MAX_DOCS=8
export ENTITY_TOP_K=5
export MEMORY_MAX_TOPICS=10
export HISTORY_KEEP_RECENT=6
export MAX_OUTPUT_TOKENS=2000
```
**Estimated:** ~9,000 tokens/query → **$5.00/month per 1000 users**

---

## Quick Reference

| Component | Token Impact | Can Reduce? |
|-----------|-------------|-------------|
| System prompts | 2,350-4,200 | Yes (edit .md files) |
| RAG documents | 1,500 | Yes (`RAG_MAX_DOCS`) |
| Entity context | 250 | Yes (`ENTITY_TOP_K`) |
| User memory | 60 | Yes (`MEMORY_MAX_TOPICS`) |
| Conversation history | 200 | Yes (`HISTORY_KEEP_RECENT`) |
| EADL | 200 | Yes (`EADL_TOP_K=0` to disable) |
| Output | 500-1,500 | Yes (`MAX_OUTPUT_TOKENS`) |

**Most effective cost reduction:** Reduce `RAG_MAX_DOCS` from 5 to 3 (saves ~600 tokens/query).

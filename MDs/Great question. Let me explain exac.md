Great question. Let me explain exactly how `entity_index.json` works in the pipeline.

## How Entity Index Works

**It's a prompt helper, NOT a search accelerator.**

Here's the flow:

```
User Query: "مالاریا با چه آزمایشی تایید میشه؟"
    │
    ▼
┌─────────────────────────────────────────┐
│  1. FAISS + BM25 search (existing)      │  ← Finds relevant documents
│     Returns: 5 text chunks from books   │
└─────────────────────┬───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│  2. Entity Search (NEW)                 │  ← Looks up "malaria" in entity_index.json
│     Found: malaria (DISEASE)            │
│     Relationships:                      │
│       - DIAGNOSES → peripheral smear    │
│       - CAUSED_BY → Plasmodium          │
│       - STAINS_WITH → Giemsa stain     │
└─────────────────────┬───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│  3. Context Injection into Prompt       │  ← Adds entity info to system message
│                                          │
│  "ENTITY KNOWLEDGE GRAPH:               │
│   Topic: malaria (DISEASE)              │
│   ├── Caused by: Plasmodium             │
│   ├── Confirmed by: peripheral smear    │
│   └── Visualized with: Giemsa stain"    │
└─────────────────────┬───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│  4. LLM sees:                           │
│   - RAG documents (from FAISS)          │  ← Text chunks from books
│   - Entity context (from JSON)          │  ← Connections between concepts
│   - User memory (from user_memory.json) │  ← What user discussed before
│                                          │
│   → LLM generates answer WITH connections│
└─────────────────────────────────────────┘
```

## In Simple Terms

| Component | What It Does | Analogy |
|-----------|-------------|---------|
| **FAISS index** | Finds relevant text passages | Library search engine |
| **BM25 index** | Finds keyword matches | Dictionary index |
| **Entity index** | Shows connections between concepts | Concept map / mind map |
| **User memory** | Remembers user's past topics | Personal notebook |

## The Key Difference

**Without entity index:**
> User: "What test confirms malaria?"
> Bot: "Malaria is confirmed by peripheral blood smear." (from one book)

**With entity index:**
> User: "What test confirms malaria?"
> Bot: "Malaria is confirmed by peripheral blood smear. The stain used is Giemsa. The causative agent is Plasmodium. Key finding: ring stage trophozoite." (connected from multiple relationships)

The entity index gives the LLM **extra context about connections** that might not be in any single document chunk. It's like giving the LLM a cheat sheet of related concepts.

## Where It's Injected

In `rag_engine.py` line ~555:
```python
# Entity-enhanced context: search entity index for related entities
query_entities = self.entity_extractor.search_entities(user_query, top_k=3)
for ent in query_entities:
    ctx = self.entity_extractor.get_entity_context(ent["name"])
    if ctx:
        entity_context_parts.append(ctx)
```

This gets added to the system prompt before the LLM generates the response.

**So to answer your question:** It's a **prompt helper** that enriches the LLM's context with structured connections. It doesn't accelerate search — it makes the answer more connected and comprehensive.
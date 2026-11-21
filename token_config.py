# -*- coding: utf-8 -*-
"""
Token Budget Configuration — Modular token limits for business planning.

This file controls how many tokens each component of the RAG system uses.
Adjust these values to balance cost vs. quality.

Token estimation: ~3.5 chars per token (mixed Persian/English medical content)
"""

import os

# ============================================================
# RAG DOCUMENT LIMITS
# ============================================================
# How many retrieved documents to send to the LLM
RAG_MAX_DOCS = int(os.getenv("RAG_MAX_DOCS", "5"))

# Max characters per document content (truncation at runtime)
RAG_MAX_DOC_CHARS = int(os.getenv("RAG_MAX_DOC_CHARS", "800"))

# Search results to retrieve before reranking
RAG_SEARCH_K = int(os.getenv("RAG_SEARCH_K", "15"))

# ============================================================
# ENTITY CONTEXT LIMITS
# ============================================================
# How many entities to search per query
ENTITY_TOP_K = int(os.getenv("ENTITY_TOP_K", "3"))

# How many related entities per found entity
ENTITY_RELATED_PER_ENTITY = int(os.getenv("ENTITY_RELATED_PER_ENTITY", "2"))

# Max relationships to include per entity
ENTITY_MAX_RELATIONSHIPS = int(os.getenv("ENTITY_MAX_RELATIONSHIPS", "5"))

# Max context snippets per entity
ENTITY_MAX_SNIPPETS = int(os.getenv("ENTITY_MAX_SNIPPETS", "3"))

# ============================================================
# USER MEMORY LIMITS
# ============================================================
# Max topics to inject into prompt
MEMORY_MAX_TOPICS = int(os.getenv("MEMORY_MAX_TOPICS", "5"))

# Max keywords per topic in prompt
MEMORY_KEYWORDS_PER_TOPIC = int(os.getenv("MEMORY_KEYWORDS_PER_TOPIC", "3"))

# ============================================================
# CONVERSATION HISTORY LIMITS
# ============================================================
# Max messages before summarization triggers
HISTORY_MAX_MESSAGES = int(os.getenv("HISTORY_MAX_MESSAGES", "10"))

# Messages to keep after summarization
HISTORY_KEEP_RECENT = int(os.getenv("HISTORY_KEEP_RECENT", "4"))

# ============================================================
# EADL (Experience Layer) LIMITS
# ============================================================
EADL_TOP_K = int(os.getenv("EADL_TOP_K", "3"))
EADL_SIM_THRESHOLD = float(os.getenv("EADL_SIM_THRESHOLD", "0.70"))

# ============================================================
# OUTPUT LIMITS
# ============================================================
# Max output tokens from LLM
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1500"))

# Max total payload size (safety valve)
MAX_PAYLOAD_CHARS = int(os.getenv("MAX_PAYLOAD_CHARS", "20000"))

# ============================================================
# TOKEN BUDGET CALCULATOR
# ============================================================
def estimate_query_tokens(
    rag_docs: int = RAG_MAX_DOCS,
    entity_top_k: int = ENTITY_TOP_K,
    memory_topics: int = MEMORY_MAX_TOPICS,
    history_messages: int = HISTORY_KEEP_RECENT,
    include_prompts: bool = True,
    include_eadl: bool = True,
    include_image: bool = False,
) -> dict:
    """
    Estimate total tokens for a query based on configuration.
    Returns breakdown by component.
    """
    # Prompt tokens (always loaded)
    prompt_tokens = 0
    if include_prompts:
        prompt_tokens = 2350  # system_core + shield + human_interaction
        if include_image:
            prompt_tokens += 950  # + specialized domain prompt

    # RAG document tokens
    rag_tokens = rag_docs * 280  # ~280 tokens per 800-char chunk

    # Entity context tokens
    entity_tokens = entity_top_k * 80  # ~80 tokens per entity context

    # User memory tokens
    memory_tokens = memory_topics * 20  # ~20 tokens per topic

    # Conversation history tokens
    history_tokens = history_messages * 50  # ~50 tokens per message

    # EADL tokens
    eadl_tokens = 0
    if include_eadl:
        eadl_tokens = 200  # ~200 tokens for corrections

    # Other (time, citations, formatting)
    other_tokens = 200

    total_input = prompt_tokens + rag_tokens + entity_tokens + memory_tokens + history_tokens + eadl_tokens + other_tokens

    return {
        "prompts": prompt_tokens,
        "rag_documents": rag_tokens,
        "entity_context": entity_tokens,
        "user_memory": memory_tokens,
        "conversation_history": history_tokens,
        "eadl": eadl_tokens,
        "other": other_tokens,
        "total_input_tokens": total_input,
        "estimated_output_tokens": MAX_OUTPUT_TOKENS,
        "total_tokens": total_input + MAX_OUTPUT_TOKENS,
    }


def print_budget_summary():
    """Print a formatted budget summary for business planning."""
    print("=" * 60)
    print("  OLIGOBOT TOKEN BUDGET — BUSINESS PLANNING")
    print("=" * 60)

    scenarios = [
        ("CASUAL (text, no RAG)", {"include_prompts": True, "include_eadl": False, "rag_docs": 0, "entity_top_k": 0, "memory_topics": 0}),
        ("EDUCATIONAL (text, with RAG)", {"include_prompts": True, "include_eadl": False}),
        ("DIAGNOSTIC (text, full)", {"include_prompts": True, "include_eadl": True}),
        ("IMAGE (hematology)", {"include_prompts": True, "include_eadl": True, "include_image": True}),
        ("WORST CASE (everything)", {"include_prompts": True, "include_eadl": True, "include_image": True, "memory_topics": 5}),
    ]

    for name, kwargs in scenarios:
        budget = estimate_query_tokens(**kwargs)
        print(f"\n{name}:")
        print(f"  Input tokens:  ~{budget['total_input_tokens']:,}")
        print(f"  Output tokens: ~{budget['estimated_output_tokens']:,}")
        print(f"  Total:         ~{budget['total_tokens']:,}")

    print("\n" + "=" * 60)
    print("  CURRENT PRICING (approximate)")
    print("=" * 60)
    print("  Gemini 3.1 Flash Lite: $0.075 / 1M input tokens")
    print("  Gemini 3.1 Flash Lite: $0.30 / 1M output tokens")
    print("  DeepSeek V3: $0.27 / 1M input tokens")
    print("  DeepSeek V3: $1.10 / 1M output tokens")
    print()

    # Calculate cost per query
    budget = estimate_query_tokens()
    # Gemini pricing
    gemini_input_cost = budget['total_input_tokens'] * 0.075 / 1_000_000
    gemini_output_cost = budget['estimated_output_tokens'] * 0.30 / 1_000_000
    gemini_total = gemini_input_cost + gemini_output_cost

    # DeepSeek pricing
    ds_input_cost = budget['total_input_tokens'] * 0.27 / 1_000_000
    ds_output_cost = budget['estimated_output_tokens'] * 1.10 / 1_000_000
    ds_total = ds_input_cost + ds_output_cost

    print(f"  Estimated cost per query (typical):")
    print(f"    Gemini Flash Lite:  ${gemini_total:.6f}")
    print(f"    DeepSeek V3:        ${ds_total:.6f}")
    print()
    print(f"  Daily cost estimates (1000 queries/day):")
    print(f"    Gemini Flash Lite:  ${gemini_total * 1000:.2f}")
    print(f"    DeepSeek V3:        ${ds_total * 1000:.2f}")
    print()
    print(f"  Monthly cost estimates (30,000 queries/month):")
    print(f"    Gemini Flash Lite:  ${gemini_total * 30000:.2f}")
    print(f"    DeepSeek V3:        ${ds_total * 30000:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    print_budget_summary()

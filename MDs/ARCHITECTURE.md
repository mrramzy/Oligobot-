# OLIGOBOT V10 — Module Architecture

## File Overview

| File | Lines | Role |
|------|-------|------|
| `app.py` | 302 | Entry point — bot init, RedisStateManager, handle_user_message, handle_user_message_stream |
| `handlers.py` | 434 | Core router — handle_message, handle_photo, handle_document, handle_callback |
| `ui_handlers.py` | 296 | UI layer — keyboards, button handlers, career system, membership, subscription display |
| `streaming.py` | 70 | Streaming engine — stream_response() with natural delays and cursor |
| `rag_engine.py` | 568 | RAG orchestrator — RAGSystem, prompt assembly, search, rerank, EADL |
| `prompt_builder.py` | 133 | Prompt assembly — build_system_prompt(), VIP sources, career context injection |
| `ai_models.py` | 130 | Profile layer — re-exports + LLM profile helpers |
| `query_refinement.py` | 165 | Query refinement — API → spaCy → dictionary fallback |
| `vision.py` | 154 | Vision — image classification, atlas captioning |
| `generation.py` | 320 | Generation — generate_response + generate_response_stream (multi-provider) |
| `config.py` | 220 | Configuration — ROUTER, LLM_PROFILES, BTN_*, env vars |
| `user_manager.py` | 224 | User profiles — names, careers, statistics, career system |
| `subscription_manager.py` | 381 | Subscriptions — tiers, access control, overrides |
| `key_manager.py` | 92 | Key rotation — Gemini API key management |
| `conversation_manager.py` | 105 | History — conversation summarization |
| `input_validator.py` | 202 | Security — input validation, injection detection |
| `citation_manager.py` | 155 | Citations — reference formatting |
| `intent_manager.py` | 126 | Intent — CASUAL / DIAGNOSTIC / EDUCATIONAL / IRRELEVANT classification |
| `eadl_manager.py` | 278 | EADL — expert feedback and case management |
| `embeddings.py` | 241 | Embeddings — Arvan / Gemini / OpenAI / Local |
| `redis_cache.py` | 73 | Cache — RAG response caching |
| `exceptions.py` | 39 | Errors — custom exception hierarchy |
| `prompt_manager.py` | 47 | Prompts — PSL directory loading |

## Module Link Map

```
app.py (ENTRY POINT)
├── state_manager.py ── RedisStateManager
├── rag_engine.py ── RAGSystem
├── conversation_manager.py ── ConversationManager
├── redis_cache.py ── RAGCache
└── handlers.py (all handlers injected via bot_data)
         │
         ▼
handlers.py (CORE ROUTER)
├── ui_handlers.py ── button handlers, keyboards, career, membership
├── streaming.py ── stream_response()
├── handle_message() ── intent detection → streaming / non-streaming
├── handle_photo() ── image handler
├── handle_document() ── document handler
└── handle_callback() ── inline button handler
         │
         ├──► ui_handlers.py (UI LAYER)
         │    ├── Keyboards (MAIN, SETTINGS, CAREER)
         │    ├── Button handlers (quota, profile, settings, support)
         │    ├── Career system (on/off/select/choice)
         │    ├── Subscription display
         │    ├── /start, /new, /setname, /feedback commands
         │    └── Helpers: get_quota_info, can_user_use, send_smart_message, check_membership
         │
         └──► streaming.py (STREAMING ENGINE)
              └── stream_response() — async loop with natural delays, cursor, markdown cleanup
         │
         ▼
rag_engine.py (RAG ORCHESTRATOR)
├── prompt_builder.py ── build_system_prompt()
├── ai_models.py ── generate_response, generate_response_stream
├── async_rag_search.py ── async_text_search, async_image_search
├── eadl_manager.py ── EADLManager
├── embeddings.py ── get_rag_embeddings
├── PromptCache ── loads PSL/*.md files
├── process_query() ── non-streaming RAG pipeline
├── process_query_stream() ── streaming RAG pipeline
├── _prepare_llm_payload() ── assembles prompt + retrieves docs + injects EADL
├── parallel_searches() ── concurrent FAISS + ChromaDB
├── _rerank_documents() ── CrossEncoder + authority scoring
└── _select_diverse_candidates() ── semantic dedup
         │
         ├──► prompt_builder.py (PROMPT ASSEMBLY)
         │    ├── build_system_prompt(intent, prompt_cache, career_context, mode, domain)
         │    ├── VIP_SOURCES / GUIDELINE_SOURCES loading
         │    ├── Intent-specific prompt selection
         │    ├── Career context injection
         │    └── Image fusion protocol
         │
         ├──► ai_models.py (PROFILE LAYER)
         │    ├── re-exports from query_refinement.py, vision.py, generation.py
         │    ├── _active_profile(), _profile_uses_openai_compat()
         │    ├── _openai_compat_client(), _gemini_client(), _gemini_generate()
         │    ├── _normalize_roles_openai(), _image_to_data_url()
         │    └── build_medical_dict()
         │         │
         │         ├──► query_refinement.py (QUERY REFINEMENT)
         │         │    ├── refine_search_query_offline() — dictionary fallback
         │         │    └── refine_search_query() — API → spaCy → dictionary
         │         │
         │         ├──► vision.py (VISION)
         │         │    ├── analyze_image_for_rag() — classify + keywords
         │         │    └── caption_atlas_image() — vision-to-text captioning
         │         │
         │         └──► generation.py (GENERATION)
         │              ├── generate_response() — non-streaming, multi-provider + fallback
         │              └── generate_response_stream() — streaming, multi-provider + fallback
         │
         └──► intent_manager.py — CASUAL / DIAGNOSTIC / EDUCATIONAL / IRRELEVANT
```

## Data Flow

```
User Message
    │
    ▼
handlers.handle_message()
    │
    ├── intent_manager.detect_intent() → CASUAL / DIAGNOSTIC / EDUCATIONAL / IRRELEVANT
    │
    ├── if IRRELEVANT → instant reply, stop
    │
    ├── user_manager.get_career_context() → career string or ""
    │
    ▼
app.handle_user_message_stream(user_id, text, intent, career_context)
    │
    ├── strategy["career_context"] = career_context
    │
    ▼
rag_engine.process_query_stream(strategy)
    │
    ├── _prepare_llm_payload(strategy)
    │       │
    │       ├── prompt_builder.build_system_prompt(intent, prompt_cache, career_context)
    │       │       → [system_core + injection_shield + diagnostic_protocol
    │       │          + human_interaction + career_context]
    │       │
    │       ├── async_text_search() + async_image_search() → FAISS + ChromaDB
    │       │
    │       ├── _select_diverse_candidates() → semantic dedup
    │       │
    │       └── _rerank_documents() → CrossEncoder + VIP authority boost
    │
    ├── generate_response_stream()
    │       → yields chunks (OpenAI / Gemini / DeepSeek / ArvanCloud)
    │
    ▼
handlers.stream_response()
    → edits Telegram message with natural delays + cursor ▌
    │
    ▼
User sees live streaming response
```

## Career System Flow

```
User taps "💼 شغل من" (Career) in Settings
    │
    ▼
ui_handlers.handle_career()
    → shows current status (ON/OFF) + career options
    │
    ├── "✅ فعال‌سازی" → handle_career_on() → sets career_enabled=True
    ├── "❌ غیرفعال"   → handle_career_off() → sets career_enabled=False
    └── "📝 انتخاب شغل" → shows CAREER_KEYBOARD with 7 options
            │
            ▼
        handle_career_choice()
            → sets career + enables career mode
            │
            ▼
        User sends next message
            │
            ▼
        handlers.handle_message()
            → user_manager.get_career_context(user_id)
            → returns: "USER PROFILE: Ali is a Physician. Personality: Clinical reasoning..."
            │
            ▼
        app.handle_user_message_stream(career_context=ctx)
            → strategy["career_context"] = ctx
            │
            ▼
        prompt_builder.build_system_prompt(career_context=ctx)
            → career context appended to system prompt
            │
            ▼
        LLM responds adapted to user's professional level

When career_mode is OFF:
    → get_career_context() returns ""
    → No career info in system prompt
    → Bot responds as neutral general assistant
```

## Testing

```bash
# Per-module tests (15 files, 55 tests)
pytest tests/ -v

# Whole-system smoke test
python test.py
```

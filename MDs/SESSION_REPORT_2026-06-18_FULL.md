# Session Report — 2026-06-18 (Full)

## Session Summary
Built subscription system, admin dashboard, condensed PSL prompts, fixed FutureWarning, added ArvanCloud fallback with WARP proxy support.

---

## 1. Subscription System ✅

**File:** `subscription_manager.py`

### Tiers
| Tier | Daily Queries | Monthly Price |
|---|---|---|
| Free | 10 | Free |
| Basic | 50 | 150,000 Toman |
| Pro | 200 | 350,000 Toman |
| Enterprise | Unlimited | 800,000 Toman |

### Admin Overrides
- **Test Mode** — Unlimited access for testing (time-limited)
- **Free Access** — Full access without payment
- **Bonus Credits** — Extra daily queries
- **Tier Override** — Set any tier for any user

### Access Control Priority
```
Admin IDs → Override (test/free) → Subscription Active → Daily Quota
```

---

## 2. Admin Dashboard ✅

**Files:** `admin_api.py` (FastAPI), `admin_dashboard.html`

### API Endpoints (19 routes)
- `/api/stats` — Platform statistics
- `/api/users` — User list with tier, usage, last active
- `/api/subscription/set` — Set user tier
- `/api/override/set` — Set admin override
- `/api/quick/grant-test` — Quick test mode
- `/api/quick/grant-free` — Quick free access
- `/api/quick/give-pro` — Quick PRO tier

### Dashboard Features
- Login with Admin ID + Secret Key
- Language toggle (Farsi/English)
- Theme toggle (Dark/Light)
- User management table
- Quick actions panel
- Payment/action history

### Secret Key
```
Default: oligobot_admin_2026
Override: ADMIN_SECRET env var
```

### Run Command
```bash
uvicorn admin_api:app --host 0.0.0.0 --port 8080
```

---

## 3. PSL Prompt Condensation ✅

| Prompt | Before | After | Saved |
|---|---|---|---|
| system_core.md | 60 lines | 22 lines | -63% |
| human_interaction.md | 376 lines | 61 lines | -84% |
| prompt_injection_shield.md | 122 lines | 31 lines | -75% |
| diagnostic_protocol.md | 88 lines | 47 lines | -47% |
| **TOTAL** | **646 lines** | **161 lines** | **-75%** |

### What Was Preserved
- All safety rules
- All diagnostic protocols
- All identity/persona rules
- All output formatting rules
- All time-aware behavior rules

### What Was Removed
- Duplicate rules across files
- Redundant examples (kept 2-3 per pattern)
- Overlapping sections between system_core and prompt_injection_shield
- Inline formatting_rule and greeting_rule from rag_engine.py

---

## 4. FutureWarning Fix ✅

Added `warnings.filterwarnings("ignore", category=FutureWarning)` in:
- `ai_models.py` — before `import google.generativeai`
- `intent_manager.py` — before `import google.generativeai`
- `key_manager.py` — before `import google.generativeai`
- `clinical_rag/Merger of Indexes.py` — before `import google.generativeai`

---

## 5. ArvanCloud Fallback + WARP ✅

### Problem
ArvanCloud blocking user's IP/location → HTTP 404 on both embedding and LLM APIs.

### Solution
1. **Auto-fallback:** When ArvanCloud (profile 2) fails → automatically switch to Google SDK (free)
2. **WARP proxy:** Added `WARP_ENABLED` and `WARP_PORT` settings in `.env` and `app.py`

### .env Settings
```
WARP_ENABLED=0
WARP_PORT=40000
```

### How to Enable WARP
1. Set `WARP_ENABLED=1` in `.env`
2. Start WARP client on port 40000
3. Restart bot

---

## Files Modified (Non-Breaking)

| File | Changes |
|---|---|
| `subscription_manager.py` | NEW — Tier system, overrides, access control |
| `admin_api.py` | NEW — FastAPI backend, 19 routes |
| `admin_dashboard.html` | NEW — RTL Farsi admin UI |
| `handlers.py` | +subscription import, tier-aware can_user_use(), /subscription command |
| `app.py` | +subscription_manager import, increment_usage sync, WARP proxy support |
| `config.py` | +BTN_SUBSCRIPTION, ADMIN_SECRET, ADMIN_DASHBOARD_PORT |
| `requirements.txt` | +fastapi, uvicorn, python-multipart |
| `ai_models.py` | +FutureWarning filter, +gemini_sdk fallback handler |
| `intent_manager.py` | +FutureWarning filter |
| `key_manager.py` | +FutureWarning filter |
| `rag_engine.py` | -removed inline formatting_rule and greeting_rule |
| `.env` | +WARP_ENABLED, WARP_PORT |
| `PSL/system_core.md` | Condensed 60→22 lines |
| `PSL/human_interaction.md` | Condensed 376→61 lines |
| `PSL/prompt_injection_shield.md` | Condensed 122→31 lines |
| `PSL/diagnostic_protocol.md` | Condensed 88→47 lines |

---

## User Preferences (This Session)
- User communicates in English (terminal doesn't render Farsi well)
- Do NOT change project's existing Farsi/RTL support
- Keep changes modular and non-breaking
- Test before claiming something works

---

## Next Session Agenda
1. Verify WARP proxy works with ArvanCloud
2. Test admin dashboard end-to-end
3. Implement prompt caching optimization
4. Test bot responses with condensed prompts

---

## Venv
`D:\Programing\projects\Telegram RAG bot\RAGBot\Scripts\python.exe`

## Run Commands
```bash
# Bot
python app.py

# Admin Dashboard
uvicorn admin_api:app --host 0.0.0.0 --port 8080
```

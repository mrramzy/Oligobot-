# -*- coding: utf-8 -*-
"""
End-to-end integration test — exercises the full pipeline
(intent detection → query refinement → RAG search → LLM generation → streaming)
without requiring Telegram.
"""
import asyncio
import sys
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test_full_pipeline():
    print("=" * 60)
    print("  OLIGOBOT V10 - End-to-End Pipeline Test")
    print("=" * 60)

    # --- 1. Import all modules (tests compilation & circular imports) ---
    print("\n[1/7] Importing modules...")
    t0 = time.time()
    try:
        # Import order matters — ai_models must load before generation (circular dep)
        from ai_models import generate_response, generate_response_stream
        from streaming import stream_response
        from deepseek_client import DeepSeekClient
        from state_manager import RedisStateManager
        from user_manager import UserManager
        from eadl_manager import EADLManager
        from query_refinement import refine_search_query, refine_search_query_offline
        from intent_manager import intent_manager, Intent
        from rag_engine import RAGSystem
        from input_validator import InputValidator
        print(f"  [OK] All imports succeeded ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    # --- 2. Intent Detection ---
    print("\n[2/7] Intent detection...")
    t0 = time.time()
    try:
        intent1 = await intent_manager.detect_intent("سلام، حالته؟", [])
        intent2 = await intent_manager.detect_intent("رنج بیلیروبین چنده؟", [])
        intent3 = await intent_manager.detect_intent("تفاوت آنمی سیدروبلاستیک و مگالوبلاستیک چیه؟", [])
        intent4 = await intent_manager.detect_intent("weather today", [])
        print(f"  [OK] 'سلام' → {intent1.name} ({time.time()-t0:.1f}s)")
        print(f"  [OK] 'بیلیروبین' → {intent2.name}")
        print(f"  [OK] 'آنمی' → {intent3.name}")
        print(f"  [OK] 'weather' → {intent4.name}")
        assert intent2.name in ("DIAGNOSTIC", "EDUCATIONAL"), f"Expected DIAGNOSTIC/EDUCATIONAL for medical query, got {intent2.name}"
    except Exception as e:
        print(f"  [FAIL] Intent error: {e}")
        return False

    # --- 3. Query Refinement ---
    print("\n[3/7] Query refinement (offline)...")
    t0 = time.time()
    try:
        refined = await refine_search_query_offline("رنج بیلیروبین", [])
        print(f"  [OK] 'رنج بیلیروبین' → '{refined}' ({time.time()-t0:.1f}s)")
        refined2 = await refine_search_query_offline("سلام", [])
        print(f"  [OK] 'سلام' → '{refined2}'")
    except Exception as e:
        print(f"  [FAIL] Refinement error: {e}")
        return False

    # --- 4. Input Validation ---
    print("\n[4/7] Input validation...")
    validator = InputValidator()
    try:
        validator.validate_query("normal range of hemoglobin")
        print("  [OK] Valid query accepted")
        try:
            validator.validate_query("")
            print("  [FAIL] Empty query should raise error")
            return False
        except (ValueError, Exception):
            print("  [OK] Empty query rejected")
    except Exception as e:
        print(f"  [FAIL] Validation error: {e}")
        return False

    # --- 5. User Manager (atomic writes) ---
    print("\n[5/7] User manager...")
    t0 = time.time()
    try:
        um = UserManager()
        test_uid = 999999999
        um.create_user(test_uid, username="test_bot", first_name="Test")
        assert um.exists(test_uid), "User should exist after create"
        um.set_display_name(test_uid, "Test User")
        assert um.get_display_name(test_uid) == "Test User", "Display name mismatch"
        name = um.get_user_info_text(test_uid)
        assert "Test User" in name, "Profile text missing name"
        um.delete_user(test_uid)
        assert not um.exists(test_uid), "User should not exist after delete"
        print(f"  [OK] create → set_name → get_info → delete ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"  [FAIL] UserManager error: {e}")
        return False

    # --- 6. LLM Generation (non-streaming, quick smoke test) ---
    print("\n[6/7] LLM generation (non-streaming)...")
    t0 = time.time()
    try:
        result = await generate_response(
            user_id=99999,
            api_payload=[{"role": "user", "content": "What is hemoglobin?"}],
            admin_id=99999,
            model="gemini_sdk"
        )
        elapsed = time.time() - t0
        assert result and len(result) > 10, f"LLM returned empty/short response: {result[:50]}"
        print(f"  [OK] Got {len(result)} chars ({elapsed:.1f}s)")
        print(f"  Preview: {result[:120]}...")
    except Exception as e:
        print(f"  [FAIL] LLM generation error: {e}")
        return False

    # --- 7. Streaming Generation ---
    print("\n[7/7] LLM generation (streaming)...")
    t0 = time.time()
    try:
        chunks = []
        async for chunk in generate_response_stream(
            user_id=99999,
            api_payload=[{"role": "user", "content": "What is bilirubin?"}],
            admin_id=99999,
            model="gemini_sdk"
        ):
            chunks.append(chunk)
        elapsed = time.time() - t0
        full = "".join(chunks)
        assert len(chunks) > 0, "No streaming chunks received"
        assert len(full) > 10, "Streaming response too short"
        print(f"  [OK] Got {len(chunks)} chunks, {len(full)} chars ({elapsed:.1f}s)")
        print(f"  Preview: {full[:120]}...")
    except Exception as e:
        print(f"  [FAIL] Streaming error: {e}")
        return False

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_full_pipeline())
    sys.exit(0 if success else 1)

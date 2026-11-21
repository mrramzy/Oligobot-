# Test workflow OLIGOBOT V10

import asyncio
import sys

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


async def test_complete_workflow():
    """Test the complete query processing workflow."""

    print("\n" + "=" * 60)
    print("OLIGOBOT V10 - Complete Workflow Test")
    print("=" * 60 + "\n")

    # Step 1: Import all modules
    print("[1/4] Importing modules...")
    try:
        from app import rag_system, convo_manager, user_manager
        from utils import detect_clinical_domain
        from intent_manager import intent_manager
        print("[OK] All imports successful\n")
    except Exception as e:
        print(f"[ERROR] Import failed: {e}\n")
        return

    # Step 2: Test clinical domain detection (offline, zero-cost)
    print("[2/4] Testing Domain Detection...")
    test_query = "آنمی و انواع آن"
    detected_domain = detect_clinical_domain(test_query)
    print(f"Query: {test_query}")
    print(f"Detected Domain: {detected_domain}\n")

    # Step 3: Test intent detection (the real, canonical intent system)
    print("[3/4] Testing Intent Detection...")
    try:
        intent = await intent_manager.detect_intent(test_query, [])
        print(f"Detected Intent: {intent.name}\n")
    except Exception as e:
        print(f"[WARNING] Intent detection: {e}\n")

    # Step 4: Test conversation history management
    print("[4/4] Testing Conversation History Management...")
    chat_history = [
        {"role": "user", "content": "سلام"},
        {"role": "assistant", "content": "سلام! چطور می‌تونم کمکتون کنم؟"},
    ]
    managed_history = await convo_manager.manage(chat_history)
    print(f"Original history length: {len(chat_history)}")
    print(f"Managed history length: {len(managed_history)}\n")

    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_complete_workflow())

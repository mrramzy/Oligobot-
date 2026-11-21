import os
import requests
import json
import sys
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("Error: TELEGRAM_TOKEN not found in environment variables.")
    sys.exit(1)

BASE = f"https://api.telegram.org/bot{TOKEN}"

# Check bot status
r = requests.get(f"{BASE}/getMe")
bot = r.json()
print(f"Bot: @{bot['result']['username']}")
print(f"Name: {bot['result']['first_name']}")
print(f"Active: {bot['ok']}")

# Check for recent messages
r2 = requests.get(f"{BASE}/getUpdates?limit=5")
updates = r2.json()
if updates.get("result"):
    print(f"\nRecent updates: {len(updates['result'])}")
    for u in updates["result"][-3:]:
        msg = u.get("message", {})
        if msg:
            print(f"  From: {msg.get('from', {}).get('first_name', '?')}")
            print(f"  Chat ID: {msg.get('chat', {}).get('id', '?')}")
            print(f"  Text: {msg.get('text', '?')[:50]}")
else:
    print("\nNo recent messages in queue")

# Get bot info for testing
print("\n--- TO TEST ---")
print("1. Open Telegram and find your bot")
print("2. Send: /start")
print("3. Send: مالاریا با چه آزمایشی تایید می‌شه؟")
print("4. The bot should respond with entity-connected answer")

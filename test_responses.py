import os
import sys
import requests
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("ADMIN_ID")

if not TOKEN or not CHAT_ID:
    print("Error: TELEGRAM_TOKEN and ADMIN_ID must be set in .env")
    sys.exit(1)

try:
    CHAT_ID = int(CHAT_ID)
except ValueError:
    pass

print("Waiting 30s for bot to process...")
time.sleep(30)

r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?limit=10")
data = r.json()

print(f"\nTotal updates: {len(data.get('result', []))}")
print("\n--- Recent messages from Hooman ---")

for u in data.get("result", []):
    msg = u.get("message", {})
    if msg and msg.get("from", {}).get("id") == CHAT_ID:
        name = msg.get("from", {}).get("first_name", "?")
        text = msg.get("text", "")[:150]
        print(f"\n[{name}]: {text}")

print("\n--- Bot responses ---")
for u in data.get("result", []):
    msg = u.get("message", {})
    if msg and msg.get("from", {}).get("is_bot"):
        text = msg.get("text", "")[:200]
        print(f"\n[Bot]: {text}")

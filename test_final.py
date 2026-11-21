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

# Send test question
q = "مالاریا چطوری تایید میشه؟"
r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": q})
print(f"Sent: {q} -> OK={r.json().get('ok')}")

# Wait for response
print("Waiting 45s for bot response...")
time.sleep(45)

# Check for bot response
r2 = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?limit=5")
data = r2.json()
print(f"\nUpdates received: {len(data.get('result', []))}")

for u in data.get("result", []):
    msg = u.get("message", {})
    if msg:
        sender = msg.get("from", {})
        is_bot = sender.get("is_bot", False)
        name = sender.get("first_name", "?")
        text = msg.get("text", "")[:300]
        prefix = "[BOT]" if is_bot else "[USER]"
        print(f"\n{prefix} {name}: {text}")

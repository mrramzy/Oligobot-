import os
import sys
import requests
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

test_questions = [
    "مالاریا با چه آزمایشی تایید میشه و با چه رنگی دیده میشه؟",
    "فیریتین چیه و چه نقشی در بدن داره؟",
]

for q in test_questions:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": q}
    )
    print(f"Sent: {q[:30]}... -> {r.json().get('ok', False)}")

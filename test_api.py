import requests
r = requests.get("https://api.telegram.org/bot8345319033:AAEbjtiH7JFnWNZXQtmKbX5jO69Yqghi6fI/getMe", timeout=10)
print(f"Status: {r.status_code}")
print(f"OK: {r.json().get('ok')}")

# -*- coding: utf-8 -*-
import os
import json

CONFIG_PATH = "config.py"
EADL_CONFIG_PATH = "eadl_config.json"

def fix_config_file():
    """Appends REDIS_PASSWORD to config.py if missing."""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ {CONFIG_PATH} not found!")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if "REDIS_PASSWORD" not in content:
        print(f"🔧 Patching {CONFIG_PATH} with REDIS_PASSWORD...")
        with open(CONFIG_PATH, "a", encoding="utf-8") as f:
            f.write("\n# Redis Configuration Patch\n")
            f.write("REDIS_PASSWORD = None  # Added by fix script\n")
        print("✅ config.py patched successfully.")
    else:
        print("✅ config.py already contains REDIS_PASSWORD.")

def add_admin_to_eadl():
    """Adds a Telegram ID to eadl_config.json."""
    try:
        user_input = input("🆔 Enter your Telegram ID (numeric) to add as Admin: ").strip()
        if not user_input.isdigit():
            print("❌ Invalid ID. Must be numeric.")
            return
        
        admin_id = int(user_input)
        
        # Load or Create Config
        if os.path.exists(EADL_CONFIG_PATH):
            with open(EADL_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"experts": [], "admins": []}

        if admin_id not in data["admins"]:
            data["admins"].append(admin_id)
            with open(EADL_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"✅ User {admin_id} added to Admins in {EADL_CONFIG_PATH}.")
        else:
            print(f"ℹ️ User {admin_id} is already an Admin.")
            
    except Exception as e:
        print(f"❌ Error updating EADL config: {e}")

if __name__ == "__main__":
    fix_config_file()
    add_admin_to_eadl()
    print("\n🚀 System fixes applied. You can now run 'app.py'.")
# -*- coding: utf-8 -*-
import json
import os

CONFIG_FILE = "eadl_config.json"

def add_admin():
    print("🚀 EADL Admin Configurator")
    print("--------------------------")
    
    try:
        user_id_str = input("🆔 Please enter your Telegram User ID (numeric): ").strip()
        if not user_id_str.isdigit():
            print("❌ Error: User ID must be a number.")
            return
        
        user_id = int(user_id_str)
        
        # Load existing config or create new
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {"experts": [], "admins": []}
            
        if user_id not in config["admins"]:
            config["admins"].append(user_id)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            print(f"✅ Success! User ID {user_id} added to admins.")
        else:
            print(f"ℹ️ User ID {user_id} is already an admin.")
            
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    add_admin()
# -*- coding: utf-8 -*-
"""
📋 User Management System
- Persists user profiles via Telegram User ID
- Atomic writes to prevent corruption on crash
- Batch saves to reduce disk I/O
"""

import json
import os
from typing import Optional, Dict, Any
from datetime import datetime
import pytz


class UserManager:
    def __init__(self, filename: str = None):
        if filename is None:
            from config import USER_PROFILES_PATH
            filename = USER_PROFILES_PATH
        self.filename = filename
        self.data: Dict[int, Dict[str, Any]] = {}
        self._dirty = False
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    self.data = {int(uid): data for uid, data in raw_data.items()}
                    print(f"✅ Loaded {len(self.data)} user profiles")
            except Exception as e:
                print(f"❌ Error loading profiles: {e}")
                self.data = {}
        else:
            print(f"📄 File {self.filename} not yet created")
            self.data = {}

    def save(self):
        try:
            json_data = {str(uid): data for uid, data in self.data.items()}
            tmp_path = f"{self.filename}.tmp.{os.getpid()}"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.filename)
            self._dirty = False
        except Exception as e:
            print(f"❌ Error saving profiles: {e}")

    def _mark_dirty(self):
        self._dirty = True

    def flush_if_dirty(self):
        if self._dirty:
            self.save()

    def create_user(self, user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
        if user_id not in self.data:
            self.data[user_id] = {
                "user_id": user_id,
                "display_name": None,
                "first_name": first_name,
                "username": username,
                "created_at": datetime.now(pytz.timezone('Asia/Tehran')).isoformat(),
                "last_update": datetime.now(pytz.timezone('Asia/Tehran')).isoformat(),
                "show_references": True,
                "career": None,
                "career_enabled": False,
                "statistics": {
                    "total_queries": 0,
                    "total_images": 0,
                    "total_documents": 0
                },
                "notifications": []
            }
            self.save()
            return True
        return False

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.data.get(user_id)

    def set_display_name(self, user_id: int, name: str) -> bool:
        if user_id in self.data:
            self.data[user_id]["display_name"] = name
            self.data[user_id]["last_update"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
            self.save()
            return True
        return False

    def get_display_name(self, user_id: int) -> Optional[str]:
        if user_id in self.data:
            user = self.data[user_id]
            return user.get("display_name") or user.get("first_name") or "دوست گرامی"
        return "کاربر"

    def update_statistics(self, user_id: int, stat_type: str):
        if user_id in self.data:
            stats = self.data[user_id]["statistics"]
            if stat_type == "query":
                stats["total_queries"] = stats.get("total_queries", 0) + 1
            elif stat_type == "image":
                stats["total_images"] = stats.get("total_images", 0) + 1
            elif stat_type == "document":
                stats["total_documents"] = stats.get("total_documents", 0) + 1
            self.data[user_id]["last_update"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
            self._mark_dirty()

    def get_user_stats(self, user_id: int) -> Dict[str, int]:
        if user_id in self.data:
            return self.data[user_id].get("statistics", {})
        return {"total_queries": 0, "total_images": 0, "total_documents": 0}

    def exists(self, user_id: int) -> bool:
        return user_id in self.data

    def get_all_users(self) -> Dict[int, Dict[str, Any]]:
        return self.data

    def set_show_references(self, user_id: int, show: bool) -> bool:
        if user_id in self.data:
            self.data[user_id]["show_references"] = show
            self.data[user_id]["last_update"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
            self.save()
            return True
        return False

    def get_show_references(self, user_id: int) -> bool:
        if user_id in self.data:
            return self.data[user_id].get("show_references", True)
        return True

    def delete_user(self, user_id: int) -> bool:
        if user_id in self.data:
            del self.data[user_id]
            self.save()
            return True
        return False

    # --- CAREER SYSTEM ---
    CAREER_OPTIONS = {
        "student": {"label": "Student", "label_fa": "دانشجو", "emoji": "📚", "level": "beginner",
                     "personality": "Educational, patient, explains concepts step-by-step. Uses simple analogies."},
        "technician": {"label": "Lab Technician", "label_fa": "کارشناس آزمایشگاه", "emoji": "🔬", "level": "practical",
                        "personality": "Practical, procedure-focused. Talks about SOPs, equipment, daily workflows."},
        "masters": {"label": "Master's Degree", "label_fa": "کارشناسی ارشد", "emoji": "🎓", "level": "advanced",
                     "personality": "Academic depth, research-informed clinical reasoning, evidence-based discussion, familiar with recent literature."},
        "physician": {"label": "Physician", "label_fa": "پزشک", "emoji": "🩺", "level": "clinical",
                       "personality": "Clinical reasoning, differential diagnosis, patient management focus."},
        "pathologist": {"label": "Pathologist", "label_fa": "پاتولوژیست", "emoji": "🔎", "level": "expert",
                         "personality": "Deep morphological detail, grading systems, WHO classification, rare entities."},
        "dcls": {"label": "DCLS / Lab Director", "label_fa": "متخصص علوم آزمایشگاهی", "emoji": "🏥", "level": "expert",
                  "personality": "Quality management, lab director perspective, regulatory compliance, method validation."},
        "phd": {"label": "PhD / Researcher", "label_fa": "دانشجو/فارغ التحصیل دکتری", "emoji": "🧬", "level": "research",
                 "personality": "Research methodology, molecular mechanisms, journal-level discussion, evidence-based."},
        "fcls": {"label": "FCLS Fellow", "label_fa": "فellow علوم آزمایشگاهی", "emoji": "🎓", "level": "fellow",
                  "personality": "Board-exam level, advanced case studies, challenging clinical scenarios."},
    }

    def set_career(self, user_id: int, career: str) -> bool:
        if user_id in self.data and career in self.CAREER_OPTIONS:
            self.data[user_id]["career"] = career
            self.data[user_id]["last_update"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
            self.save()
            return True
        return False

    def get_career(self, user_id: int) -> Optional[str]:
        if user_id in self.data:
            return self.data[user_id].get("career")
        return None

    def set_career_enabled(self, user_id: int, enabled: bool):
        if user_id in self.data:
            self.data[user_id]["career_enabled"] = enabled
            self.data[user_id]["last_update"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
            self.save()

    def get_career_enabled(self, user_id: int) -> bool:
        if user_id in self.data:
            return self.data[user_id].get("career_enabled", False)
        return False

    def get_career_context(self, user_id: int) -> str:
        if not self.get_career_enabled(user_id):
            return ""
        career = self.get_career(user_id)
        if not career or career not in self.CAREER_OPTIONS:
            return ""
        info = self.CAREER_OPTIONS[career]
        name = self.get_display_name(user_id)
        return (
            f"USER PROFILE: {name} is a {info['label']} ({info['label_fa']}). "
            f"Personality: {info['personality']} "
            f"Adjust your tone, depth, and vocabulary to match their professional level."
        )

    # --- NOTIFICATION SYSTEM ---
    def add_notification(self, user_id: int, message: str):
        if user_id in self.data:
            if "notifications" not in self.data[user_id]:
                self.data[user_id]["notifications"] = []
            self.data[user_id]["notifications"].append(message)
            self.save()

    def get_and_clear_notifications(self, user_id: int) -> list[str]:
        if user_id in self.data and self.data[user_id].get("notifications"):
            msgs = self.data[user_id]["notifications"].copy()
            self.data[user_id]["notifications"] = []
            self.save()
            return msgs
        return []

    def get_user_info_text(self, user_id: int) -> str:
        user = self.get_user(user_id)
        if not user:
            return "❌ پروفایل یافت نشد"

        display_name = self.get_display_name(user_id)
        stats = user.get("statistics", {})
        career = user.get("career")
        career_enabled = user.get("career_enabled", False)
        career_text = "Off (Generic mode)"
        if career_enabled and career and career in self.CAREER_OPTIONS:
            c = self.CAREER_OPTIONS[career]
            career_text = f"{c['emoji']} {c['label']} ({c['label_fa']})"

        info = f"""👤 **پروفایل کاربری شما**

📝 **نام نمایشی:** {display_name}
🆔 **شناسه Telegram:** {user_id}
👤 **نام اول:** {user.get('first_name') or 'تنظیم نشده'}
📱 **نام کاربری:** @{user.get('username') or 'تنظیم نشده'}
💼 **شغل:** {career_text}

📊 **آمار استفاده:**
   تعداد سوالات: {stats.get('total_queries', 0)}
   تعداد تصاویر: {stats.get('total_images', 0)}
   تعداد اسناد: {stats.get('total_documents', 0)}

⏰ **زمان عضویت:** {user.get('created_at', 'نامشخص')[:10]}
"""

        return info.strip()

# -*- coding: utf-8 -*-
"""
Subscription & Access Control Manager for OLIGOBOT SaaS
Handles tier-based access, admin overrides, and payment tracking.

Admin can:
- Grant/revoke access to any user (with or without subscription)
- Set test mode for users (unlimited access)
- Grant bonus credits
- Override tier limits
"""

import json
import os
import time
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
from logging_config import get_logger

logger = get_logger(__name__)

# ==========================================
# SUBSCRIPTION TIERS
# ==========================================
class SubscriptionTier(Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

# Tier definitions: (daily_queries, monthly_price_toman, features)
TIER_CONFIG = {
    SubscriptionTier.FREE: {
        "label": "رایگان",
        "label_en": "Free",
        "daily_queries": 10,
        "monthly_price": 0,
        "features": ["text_queries", "basic_rag"],
        "description": "۱۰ سوال در روز - ویژگی‌های پایه"
    },
    SubscriptionTier.BASIC: {
        "label": "پایه",
        "label_en": "Basic",
        "daily_queries": 50,
        "monthly_price": 150000,  # 150K toman
        "features": ["text_queries", "image_analysis", "document_analysis", "full_rag", "references"],
        "description": "۵۰ سوال در روز - تمام ویژگی‌ها"
    },
    SubscriptionTier.PRO: {
        "label": "حرفه‌ای",
        "label_en": "Pro",
        "daily_queries": 200,
        "monthly_price": 350000,  # 350K toman
        "features": ["text_queries", "image_analysis", "document_analysis", "full_rag", "references", "priority_support", "expert_panel"],
        "description": "۲۰۰ سوال در روز - اولویت پشتیبانی"
    },
    SubscriptionTier.ENTERPRISE: {
        "label": "سازمانی",
        "label_en": "Enterprise",
        "daily_queries": -1,  # Unlimited
        "monthly_price": 800000,  # 800K toman
        "features": ["text_queries", "image_analysis", "document_analysis", "full_rag", "references", "priority_support", "expert_panel", "api_access", "custom_kb"],
        "description": "نامحدود - تمام ویژگی‌ها + API"
    },
}

# Admin override types
class OverrideType(Enum):
    NONE = "none"
    TEST_MODE = "test_mode"          # Unlimited access for testing
    BONUS_CREDITS = "bonus_creds"    # Extra daily queries
    FREE_ACCESS = "free_access"      # Full access without payment
    EXPIRED_GRANT = "expired_grant"  # Time-limited access


class SubscriptionManager:
    """
    Manages user subscriptions, admin overrides, and access control.
    Storage: subscription_data.json
    """
    
    def __init__(self, data_file: str = None):
        if data_file is None:
            from config import SUBSCRIPTION_DATA_PATH
            data_file = SUBSCRIPTION_DATA_PATH
        self.data_path = data_file
        self.data = self._load_data()
        
    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load subscription data: {e}")
        return {"users": {}, "payments": [], "overrides": {}}
    
    def _save_data(self):
        try:
            tmp_path = f"{self.data_path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.data_path)
        except Exception as e:
            logger.error(f"Failed to save subscription data: {e}")
    
    # ==========================================
    # USER SUBSCRIPTION MANAGEMENT
    # ==========================================
    
    def get_user_subscription(self, user_id: int) -> Dict[str, Any]:
        """Get user's subscription info."""
        uid_str = str(user_id)
        if uid_str not in self.data["users"]:
            # Initialize new user with FREE tier
            self.data["users"][uid_str] = {
                "user_id": user_id,
                "tier": SubscriptionTier.FREE.value,
                "subscribed_at": None,
                "expires_at": None,
                "is_active": True,
                "daily_queries_used": 0,
                "last_query_date": None,
                "last_active_at": None,
                "total_queries_all_time": 0,
                "payment_history": [],
                "admin_notes": "",
            }
            self._save_data()
        return self.data["users"][uid_str]
    
    def set_tier(self, user_id: int, tier: SubscriptionTier, duration_days: int = 30, admin_id: int = 0, note: str = ""):
        """Set user's subscription tier."""
        uid_str = str(user_id)
        sub = self.get_user_subscription(user_id)
        
        now = datetime.now(pytz.timezone('Asia/Tehran'))
        sub["tier"] = tier.value
        sub["subscribed_at"] = now.isoformat()
        sub["expires_at"] = (now + timedelta(days=duration_days)).isoformat()
        sub["is_active"] = True
        
        # Record payment event
        self.data["payments"].append({
            "user_id": user_id,
            "tier": tier.value,
            "action": "subscribe",
            "duration_days": duration_days,
            "admin_id": admin_id,
            "note": note,
            "timestamp": now.isoformat(),
        })
        
        self._save_data()
        logger.info(f"Subscription set: user={user_id}, tier={tier.value}, duration={duration_days}d, admin={admin_id}")
    
    def cancel_subscription(self, user_id: int, admin_id: int = 0, reason: str = ""):
        """Cancel/downgrade user to FREE."""
        uid_str = str(user_id)
        sub = self.get_user_subscription(user_id)
        
        old_tier = sub["tier"]
        sub["tier"] = SubscriptionTier.FREE.value
        sub["expires_at"] = None
        sub["is_active"] = True
        
        self.data["payments"].append({
            "user_id": user_id,
            "tier": old_tier,
            "action": "cancel",
            "admin_id": admin_id,
            "note": reason,
            "timestamp": datetime.now(pytz.timezone('Asia/Tehran')).isoformat(),
        })
        
        self._save_data()
        logger.info(f"Subscription cancelled: user={user_id}, from={old_tier}, admin={admin_id}")
    
    def is_subscription_active(self, user_id: int) -> bool:
        """Check if subscription is still valid (not expired)."""
        sub = self.get_user_subscription(user_id)
        if not sub.get("is_active"):
            return False
        if sub.get("expires_at"):
            expires = datetime.fromisoformat(sub["expires_at"])
            now = datetime.now(pytz.timezone('Asia/Tehran'))
            if now > expires:
                return False
        return True
    
    def get_tier_config(self, user_id: int) -> Dict[str, Any]:
        """Get tier configuration for user."""
        sub = self.get_user_subscription(user_id)
        try:
            tier = SubscriptionTier(sub["tier"])
        except ValueError:
            tier = SubscriptionTier.FREE
        return TIER_CONFIG[tier]
    
    # ==========================================
    # DAILY QUOTA MANAGEMENT
    # ==========================================
    
    def _reset_daily_if_needed(self, sub: Dict[str, Any]):
        """Reset daily counter if it's a new day."""
        today = datetime.now(pytz.timezone('Asia/Tehran')).strftime("%Y-%m-%d")
        if sub.get("last_query_date") != today:
            sub["daily_queries_used"] = 0
            sub["last_query_date"] = today
    
    def get_remaining_queries(self, user_id: int) -> int:
        """Get remaining queries for today."""
        sub = self.get_user_subscription(user_id)
        self._reset_daily_if_needed(sub)
        
        tier_config = self.get_tier_config(user_id)
        daily_limit = tier_config["daily_queries"]
        
        if daily_limit == -1:  # Unlimited
            return 999999
        
        used = sub.get("daily_queries_used", 0)
        return max(0, daily_limit - used)
    
    def can_query(self, user_id: int) -> bool:
        """Check if user can make a query."""
        # Admin always can
        from config import ADMIN_USER_IDS
        if user_id in ADMIN_USER_IDS:
            return True
        
        # Check test mode override
        override = self.get_override(user_id)
        if override and override.get("type") == OverrideType.TEST_MODE.value:
            return True
        if override and override.get("type") == OverrideType.FREE_ACCESS.value:
            if override.get("expires_at"):
                expires = datetime.fromisoformat(override["expires_at"])
                if datetime.now(pytz.timezone('Asia/Tehran')) < expires:
                    return True
        
        # Check subscription
        if not self.is_subscription_active(user_id):
            return False
        
        return self.get_remaining_queries(user_id) > 0
    
    def increment_usage(self, user_id: int):
        """Increment daily query count and track activity."""
        sub = self.get_user_subscription(user_id)
        self._reset_daily_if_needed(sub)
        sub["daily_queries_used"] = sub.get("daily_queries_used", 0) + 1
        sub["total_queries_all_time"] = sub.get("total_queries_all_time", 0) + 1
        sub["last_active_at"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
        self._save_data()
    
    # ==========================================
    # ADMIN OVERRIDE SYSTEM
    # ==========================================
    
    def set_override(self, user_id: int, override_type: OverrideType, 
                     admin_id: int, expires_days: int = 30, note: str = "",
                     bonus_queries: int = 0):
        """
        Set admin override for a user.
        - TEST_MODE: Unlimited access
        - FREE_ACCESS: Full access without payment
        - BONUS_CREDITS: Extra daily queries on top of tier
        """
        uid_str = str(user_id)
        
        override_data = {
            "type": override_type.value,
            "admin_id": admin_id,
            "created_at": datetime.now(pytz.timezone('Asia/Tehran')).isoformat(),
            "note": note,
            "bonus_queries": bonus_queries,
        }
        
        if expires_days > 0:
            override_data["expires_at"] = (
                datetime.now(pytz.timezone('Asia/Tehran')) + timedelta(days=expires_days)
            ).isoformat()
        else:
            override_data["expires_at"] = None  # Permanent
        
        self.data["overrides"][uid_str] = override_data
        self._save_data()
        
        logger.info(f"Admin override set: user={user_id}, type={override_type.value}, admin={admin_id}, expires={expires_days}d")
    
    def get_override(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get admin override for user (if any and not expired)."""
        uid_str = str(user_id)
        override = self.data["overrides"].get(uid_str)
        
        if not override:
            return None
        
        # Check expiry
        if override.get("expires_at"):
            expires = datetime.fromisoformat(override["expires_at"])
            if datetime.now(pytz.timezone('Asia/Tehran')) > expires:
                # Override expired, remove it
                del self.data["overrides"][uid_str]
                self._save_data()
                return None
        
        return override
    
    def remove_override(self, user_id: int, admin_id: int = 0):
        """Remove admin override."""
        uid_str = str(user_id)
        if uid_str in self.data["overrides"]:
            del self.data["overrides"][uid_str]
            self._save_data()
            logger.info(f"Admin override removed: user={user_id}, admin={admin_id}")
    
    def grant_bonus_queries(self, user_id: int, count: int, admin_id: int, note: str = ""):
        """Grant bonus daily queries to user."""
        sub = self.get_user_subscription(user_id)
        sub["daily_queries_used"] = max(0, sub.get("daily_queries_used", 0) - count)
        self._save_data()
        
        self.data["payments"].append({
            "user_id": user_id,
            "action": "bonus_grant",
            "amount": count,
            "admin_id": admin_id,
            "note": note,
            "timestamp": datetime.now(pytz.timezone('Asia/Tehran')).isoformat(),
        })
        self._save_data()
        logger.info(f"Bonus granted: user={user_id}, count={count}, admin={admin_id}")
    
    # ==========================================
    # ACCESS CHECK (MAIN ENTRY POINT)
    # ==========================================
    
    def check_access(self, user_id: int) -> Dict[str, Any]:
        """
        Main access check. Returns detailed status.
        Use this in handlers to determine access level.
        """
        from config import ADMIN_USER_IDS
        
        result = {
            "allowed": False,
            "reason": "",
            "tier": "free",
            "remaining": 0,
            "is_admin": user_id in ADMIN_USER_IDS,
            "has_override": False,
            "override_type": None,
        }
        
        # Admin always allowed
        if user_id in ADMIN_USER_IDS:
            result["allowed"] = True
            result["reason"] = "admin"
            result["tier"] = "admin"
            result["remaining"] = 999999
            return result
        
        # Check override
        override = self.get_override(user_id)
        if override:
            ot = override.get("type")
            if ot == OverrideType.TEST_MODE.value:
                result["allowed"] = True
                result["reason"] = "test_mode"
                result["has_override"] = True
                result["override_type"] = ot
                result["remaining"] = 999999
                return result
            elif ot == OverrideType.FREE_ACCESS.value:
                result["allowed"] = True
                result["reason"] = "free_access"
                result["has_override"] = True
                result["override_type"] = ot
                result["remaining"] = 999999
                return result
        
        # Check subscription
        if not self.is_subscription_active(user_id):
            result["allowed"] = False
            result["reason"] = "subscription_expired"
            return result
        
        # Check daily quota
        remaining = self.get_remaining_queries(user_id)
        sub = self.get_user_subscription(user_id)
        result["tier"] = sub.get("tier", "free")
        result["remaining"] = remaining
        result["allowed"] = remaining > 0
        if not result["allowed"]:
            result["reason"] = "daily_limit_reached"
        
        return result
    
    # ==========================================
    # ADMIN LISTING & STATS
    # ==========================================
    
    def get_all_users_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all users for admin dashboard."""
        summary = []
        for uid_str, sub in self.data.get("users", {}).items():
            uid = int(uid_str)
            tier_config = self.get_tier_config(uid)
            override = self.get_override(uid)
            remaining = self.get_remaining_queries(uid)
            
            summary.append({
                "user_id": uid,
                "tier": sub.get("tier", "free"),
                "tier_label": tier_config["label"],
                "is_active": sub.get("is_active", True),
                "subscribed_at": sub.get("subscribed_at"),
                "expires_at": sub.get("expires_at"),
                "daily_used": sub.get("daily_queries_used", 0),
                "daily_limit": tier_config["daily_queries"],
                "remaining": remaining,
                "has_override": override is not None,
                "override_type": override.get("type") if override else None,
                "last_active_at": sub.get("last_active_at"),
                "total_queries_all_time": sub.get("total_queries_all_time", 0),
                "admin_notes": sub.get("admin_notes", ""),
            })
        
        return sorted(summary, key=lambda x: x["daily_used"], reverse=True)
    
    def get_platform_stats(self) -> Dict[str, Any]:
        """Get platform-wide statistics."""
        users = self.data.get("users", {})
        overrides = self.data.get("overrides", {})
        payments = self.data.get("payments", [])
        
        tier_counts = {t.value: 0 for t in SubscriptionTier}
        for sub in users.values():
            tier = sub.get("tier", "free")
            if tier in tier_counts:
                tier_counts[tier] += 1
        
        total_queries_today = sum(
            sub.get("daily_queries_used", 0) 
            for sub in users.values()
            if sub.get("last_query_date") == datetime.now(pytz.timezone('Asia/Tehran')).strftime("%Y-%m-%d")
        )
        
        return {
            "total_users": len(users),
            "tier_distribution": tier_counts,
            "active_overrides": len(overrides),
            "total_queries_today": total_queries_today,
            "total_payments": len(payments),
        }
    
    def set_admin_notes(self, user_id: int, notes: str):
        """Set admin notes for a user."""
        sub = self.get_user_subscription(user_id)
        sub["admin_notes"] = notes
        self._save_data()


# Singleton
subscription_manager = SubscriptionManager()

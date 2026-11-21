# -*- coding: utf-8 -*-
"""
Admin Dashboard API for OLIGOBOT SaaS
FastAPI backend for user management, subscription control, and analytics.

Usage:
    uvicorn admin_api:app --host 0.0.0.0 --port 8080 --reload
"""

import os
import sys
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import json as json_mod

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ADMIN_ID, ADMIN_USER_IDS
from subscription_manager import (
    subscription_manager, SubscriptionTier, 
    TIER_CONFIG, OverrideType
)

# ==========================================
# PYDANTIC MODELS
# ==========================================

class SetTierRequest(BaseModel):
    user_id: int
    tier: str  # "free", "basic", "pro", "enterprise"
    duration_days: int = 30
    note: str = ""

class OverrideRequest(BaseModel):
    user_id: int
    override_type: str  # "test_mode", "free_access", "bonus_creds"
    expires_days: int = 30
    note: str = ""
    bonus_queries: int = 0

class CancelRequest(BaseModel):
    user_id: int
    reason: str = ""

class NoteRequest(BaseModel):
    user_id: int
    notes: str

class AdminAuth(BaseModel):
    admin_id: int
    secret: str = ""

# ==========================================
# APP INIT
# ==========================================

app = FastAPI(
    title="OLIGOBOT Admin Dashboard",
    description="Admin API for managing subscriptions, users, and access control",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ==========================================
# UTF-8 ENCODING MIDDLEWARE
# ==========================================
@app.middleware("http")
async def utf8_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Type"] = response.headers.get("content-type", "") + "; charset=utf-8"
    return response

# ==========================================
# AUTH MIDDLEWARE
# ==========================================

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "oligobot_admin_2026")

async def get_admin(request: Request, admin_id: int = Query(...)):
    """Dependency: verifies admin_id + secret from X-Admin-Secret header."""
    secret = request.headers.get("X-Admin-Secret", "")
    if admin_id not in ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Not an admin")
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Invalid secret key")
    return admin_id

# ==========================================
# DASHBOARD UI
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the admin dashboard HTML with UTF-8 encoding."""
    html_path = os.path.join(os.path.dirname(__file__), "admin_dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/html; charset=utf-8")
    return HTMLResponse(content="<h1>Admin Dashboard - HTML file not found</h1>")

# ==========================================
# STATS ENDPOINTS
# ==========================================

@app.get("/api/stats")
async def get_stats(admin_id: int = Depends(get_admin)):
    return subscription_manager.get_platform_stats()

@app.get("/api/users")
async def get_users(admin_id: int = Depends(get_admin)):
    return subscription_manager.get_all_users_summary()

@app.get("/api/users/{user_id}")
async def get_user(user_id: int, admin_id: int = Depends(get_admin)):
    sub = subscription_manager.get_user_subscription(user_id)
    override = subscription_manager.get_override(user_id)
    tier_config = subscription_manager.get_tier_config(user_id)
    remaining = subscription_manager.get_remaining_queries(user_id)
    
    return {
        "subscription": sub,
        "override": override,
        "tier_config": tier_config,
        "remaining_queries": remaining,
    }

# ==========================================
# SUBSCRIPTION MANAGEMENT
# ==========================================

@app.post("/api/subscription/set")
async def set_subscription(req: SetTierRequest, admin_id: int = Depends(get_admin)):
    """Set user's subscription tier."""
    try:
        tier = SubscriptionTier(req.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {req.tier}")
    
    subscription_manager.set_tier(
        user_id=req.user_id,
        tier=tier,
        duration_days=req.duration_days,
        admin_id=admin_id,
        note=req.note
    )
    
    return {"status": "ok", "message": f"Tier set to {req.tier} for user {req.user_id}"}

@app.post("/api/subscription/cancel")
async def cancel_subscription(req: CancelRequest, admin_id: int = Depends(get_admin)):
    """Cancel/downgrade user to FREE."""
    subscription_manager.cancel_subscription(req.user_id, admin_id, req.reason)
    return {"status": "ok", "message": f"Subscription cancelled for user {req.user_id}"}

# ==========================================
# OVERRIDE MANAGEMENT
# ==========================================

@app.post("/api/override/set")
async def set_override(req: OverrideRequest, admin_id: int = Depends(get_admin)):
    """Set admin override for a user."""
    try:
        override_type = OverrideType(req.override_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid override type: {req.override_type}")
    
    subscription_manager.set_override(
        user_id=req.user_id,
        override_type=override_type,
        admin_id=admin_id,
        expires_days=req.expires_days,
        note=req.note,
        bonus_queries=req.bonus_queries
    )
    
    return {"status": "ok", "message": f"Override {req.override_type} set for user {req.user_id}"}

@app.post("/api/override/remove")
async def remove_override(user_id: int = Query(...), admin_id: int = Depends(get_admin)):
    """Remove admin override."""
    subscription_manager.remove_override(user_id, admin_id)
    return {"status": "ok", "message": f"Override removed for user {user_id}"}

@app.post("/api/bonus")
async def grant_bonus(user_id: int, count: int = Query(...), 
                      note: str = "", admin_id: int = Depends(get_admin)):
    """Grant bonus queries to user."""
    subscription_manager.grant_bonus_queries(user_id, count, admin_id, note)
    return {"status": "ok", "message": f"Granted {count} bonus queries to user {user_id}"}

# ==========================================
# NOTES & UTILITIES
# ==========================================

@app.post("/api/user/notes")
async def set_notes(req: NoteRequest, admin_id: int = Depends(get_admin)):
    """Set admin notes for a user."""
    subscription_manager.set_admin_notes(req.user_id, req.notes)
    return {"status": "ok"}

@app.get("/api/tiers")
async def get_tiers():
    """Get all tier configurations (public)."""
    return {
        tier.value: {
            "label": config["label"],
            "label_en": config["label_en"],
            "daily_queries": config["daily_queries"],
            "monthly_price": config["monthly_price"],
            "features": config["features"],
            "description": config["description"],
        }
        for tier, config in TIER_CONFIG.items()
    }

@app.get("/api/payment-history")
async def get_payment_history(admin_id: int = Depends(get_admin), limit: int = Query(50)):
    """Get recent payment/action history."""
    history = subscription_manager.data.get("payments", [])
    return sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

# ==========================================
# QUICK ACTIONS (Convenience Endpoints)
# ==========================================

@app.post("/api/quick/grant-test")
async def quick_grant_test(user_id: int, days: int = Query(7), admin_id: int = Depends(get_admin)):
    """Quick action: Grant test mode to a user."""
    subscription_manager.set_override(
        user_id=user_id,
        override_type=OverrideType.TEST_MODE,
        admin_id=admin_id,
        expires_days=days,
        note="Quick test mode grant"
    )
    return {"status": "ok", "message": f"Test mode granted to user {user_id} for {days} days"}

@app.post("/api/quick/grant-free")
async def quick_grant_free(user_id: int, days: int = Query(30), admin_id: int = Depends(get_admin)):
    """Quick action: Grant free full access to a user."""
    subscription_manager.set_override(
        user_id=user_id,
        override_type=OverrideType.FREE_ACCESS,
        admin_id=admin_id,
        expires_days=days,
        note="Quick free access grant"
    )
    return {"status": "ok", "message": f"Free access granted to user {user_id} for {days} days"}

@app.post("/api/quick/give-pro")
async def quick_give_pro(user_id: int, days: int = Query(30), admin_id: int = Depends(get_admin)):
    """Quick action: Give PRO subscription to a user."""
    subscription_manager.set_tier(
        user_id=user_id,
        tier=SubscriptionTier.PRO,
        duration_days=days,
        admin_id=admin_id,
        note="Quick PRO grant"
    )
    return {"status": "ok", "message": f"PRO tier granted to user {user_id} for {days} days"}

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting OLIGOBOT Admin Dashboard...")
    print(f"📊 Dashboard: http://localhost:8080")
    print(f"🔑 Admin IDs: {ADMIN_USER_IDS}")
    uvicorn.run(app, host="0.0.0.0", port=8080)

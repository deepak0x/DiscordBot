"""
MongoDB helper — wrapper around the users collection.
Supports tracking emails sent, active LLM provider, and user-provided API keys.
"""
import logging
from typing import Any

from pymongo import MongoClient

import config

logger = logging.getLogger(__name__)

_client = MongoClient(config.MONGODB_URI)
_db     = _client["studybot"]
_users  = _db["users"]


def increment_sent(user_id: str) -> int:
    """Increment emails_sent counter for *user_id* and return the new count."""
    _users.update_one(
        {"_id": user_id},
        {"$inc": {"emails_sent": 1}},
        upsert=True,
    )
    doc = _users.find_one({"_id": user_id})
    count: int = doc.get("emails_sent", 1) if doc else 1
    logger.debug("MongoDB update: user=%s count=%d", user_id, count)
    return count

def get_sent_count(user_id: str) -> int:
    doc = _users.find_one({"_id": user_id})
    return doc.get("emails_sent", 0) if doc else 0


def get_user_settings(user_id: str) -> dict[str, Any]:
    """Return user settings, or defaults if not found."""
    doc = _users.find_one({"_id": user_id}) or {}
    return {
        "active_provider": doc.get("active_provider", "gemini"),
        "keys": doc.get("keys", {})
    }

def set_active_provider(user_id: str, provider: str) -> None:
    """Save the user's preferred LLM provider."""
    _users.update_one(
        {"_id": user_id},
        {"$set": {"active_provider": provider}},
        upsert=True,
    )

def set_custom_key(user_id: str, provider: str, key: str) -> None:
    """Save a user's custom API key for a specific provider."""
    _users.update_one(
        {"_id": user_id},
        {"$set": {f"keys.{provider}": key}},
        upsert=True,
    )

"""
FloodSense Cache Service — tiny file-backed JSON cache with TTL + stale flag.

Design: a stale entry is still returned (with stale=True) so the UI can keep
working offline and show a "stale data" warning instead of breaking.
"""
import json
import os
import re
import time

from backend.config import CACHE_DIR, CACHE_TTL_SECONDS

_SAFE_KEY = re.compile(r"[^A-Za-z0-9_.-]+")


def _path(key: str) -> str:
    safe = _SAFE_KEY.sub("_", key)
    return os.path.join(CACHE_DIR, f"{safe}.json")


def cache_set(key: str, value, now: float = None) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    payload = {"stored_at": now if now is not None else time.time(), "value": value}
    tmp = _path(key) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, _path(key))


def cache_get(key: str, ttl: int = CACHE_TTL_SECONDS, now: float = None) -> dict:
    """
    Returns {"hit": bool, "value": ..., "age_seconds": float|None, "stale": bool}.
    hit=False means no entry at all. stale=True means older than ttl.
    """
    p = _path(key)
    if not os.path.exists(p):
        return {"hit": False, "value": None, "age_seconds": None, "stale": True}
    try:
        with open(p, "r", encoding="utf-8") as f:
            payload = json.load(f)
        stored_at = float(payload.get("stored_at", 0))
        value = payload.get("value")
    except (OSError, ValueError, TypeError):
        return {"hit": False, "value": None, "age_seconds": None, "stale": True}
    age = (now if now is not None else time.time()) - stored_at
    return {"hit": True, "value": value, "age_seconds": round(age, 1), "stale": age > ttl}


def cache_clear(key: str = None) -> int:
    """Delete one entry (or all). Returns number of files removed."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    removed = 0
    targets = [_path(key)] if key else [
        os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR) if f.endswith(".json")
    ]
    for t in targets:
        try:
            os.remove(t)
            removed += 1
        except OSError:
            pass
    return removed

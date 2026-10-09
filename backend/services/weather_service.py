"""
FloodSense Weather Service — Open-Meteo (free, no key), cache-first, stale-aware.

get_current_weather(live=False)
    live=False : never touch the network. Serve cache (fresh or stale) or an
                 explicitly-labelled offline fallback.
    live=True  : serve fresh cache; otherwise fetch Open-Meteo, cache, return.
                 On network failure fall back to stale cache, then offline fallback.

get_archive_weather(date_str)
    Hourly precipitation for one date from the Open-Meteo archive (for replay).
"""
import datetime as _dt
import time

import requests

from backend.config import (
    CITY_LAT, CITY_LON, OPEN_METEO_BASE, OPEN_METEO_ARCHIVE, CACHE_TTL_SECONDS,
)
from backend.services.cache_service import cache_get, cache_set

TIMEZONE = "Asia/Kolkata"
REQUEST_TIMEOUT_S = 6
CURRENT_KEY = "current_weather"

# Offline fallback: a plausible light-rain afternoon. Clearly labelled; never
# presented as live. Lets the demo run with no internet.
_OFFLINE_FALLBACK = {
    "precip_1h_mm": 4.2,
    "forecast_6h_mm": [3.1, 5.6, 7.9, 6.2, 3.4, 1.8],
    "observation_time": None,
    "timezone": TIMEZONE,
}


def _fetch_open_meteo_current() -> dict:
    """Single network call. Raises on any failure; caller handles fallback."""
    params = {
        "latitude": CITY_LAT,
        "longitude": CITY_LON,
        "current": "precipitation,rain",
        "hourly": "precipitation",
        "forecast_days": 2,
        "timezone": TIMEZONE,
    }
    r = requests.get(f"{OPEN_METEO_BASE}/forecast", params=params, timeout=REQUEST_TIMEOUT_S)
    r.raise_for_status()
    j = r.json()

    current = j.get("current", {}) or {}
    precip_now = current.get("precipitation")
    if precip_now is None:
        precip_now = current.get("rain", 0.0)
    obs_time = current.get("time")

    hourly = j.get("hourly", {}) or {}
    times = hourly.get("time", []) or []
    vals = hourly.get("precipitation", []) or []

    # Next 6 hourly buckets strictly after the observation hour.
    forecast = []
    if obs_time and times:
        obs_hour = obs_time[:13]  # "YYYY-MM-DDTHH"
        start = 0
        for i, t in enumerate(times):
            if t[:13] > obs_hour:
                start = i
                break
        forecast = [float(v or 0.0) for v in vals[start:start + 6]]
    if len(forecast) < 6:
        forecast = (forecast + [0.0] * 6)[:6]

    return {
        "precip_1h_mm": float(precip_now or 0.0),
        "forecast_6h_mm": forecast,
        "observation_time": obs_time,
        "timezone": TIMEZONE,
    }


def _wrap(value: dict, source: str, stale: bool, age: float, error: str = None) -> dict:
    out = dict(value)
    out.update({
        "source": source,
        "stale": bool(stale),
        "age_seconds": age,
        "fetched_at": time.time() - (age or 0.0),
        "lat": CITY_LAT,
        "lon": CITY_LON,
        "provider": "Open-Meteo" if source in ("open-meteo", "cache", "stale-cache") else source,
    })
    if error:
        out["error"] = error
    return out


def get_current_weather(live: bool = False, ttl: int = CACHE_TTL_SECONDS, sample: bool = False) -> dict:
    if sample:
        # Explicit demo mode: a labelled sample storm. Never presented as live.
        return _wrap(_OFFLINE_FALLBACK, "sample-storm", True, None,
                     error="sample storm selected by user; not live weather")
    cached = cache_get(CURRENT_KEY, ttl=ttl)

    if cached["hit"] and not cached["stale"]:
        return _wrap(cached["value"], "cache", False, cached["age_seconds"])

    if not live:
        if cached["hit"]:
            return _wrap(cached["value"], "stale-cache", True, cached["age_seconds"])
        return _wrap(_OFFLINE_FALLBACK, "offline-fallback", True, None,
                     error="live=False and no cache; serving labelled offline fallback")

    try:
        fresh = _fetch_open_meteo_current()
        cache_set(CURRENT_KEY, fresh)
        return _wrap(fresh, "open-meteo", False, 0.0)
    except Exception as e:  # network, JSON, schema — all degrade gracefully
        err = f"{type(e).__name__}: {e}"[:200]
        if cached["hit"]:
            return _wrap(cached["value"], "stale-cache", True, cached["age_seconds"], error=err)
        return _wrap(_OFFLINE_FALLBACK, "offline-fallback", True, None, error=err)


def _valid_date(date_str: str) -> bool:
    try:
        _dt.date.fromisoformat(date_str)
        return True
    except (TypeError, ValueError):
        return False


def get_archive_weather(date_str: str, live: bool = True) -> dict:
    """
    Hourly precipitation (24 values, mm) for a past date at the city centroid.
    Returns {date, hourly_precip_mm[24], hourly_times[24], source, stale, error?}.
    """
    if not _valid_date(date_str):
        return {"date": date_str, "hourly_precip_mm": [0.0] * 24, "hourly_times": [],
                "source": "invalid-date", "stale": True, "error": "date must be YYYY-MM-DD"}

    key = f"archive_{date_str}"
    cached = cache_get(key, ttl=10 ** 9)  # archive data never goes stale
    if cached["hit"]:
        out = dict(cached["value"])
        out.update({"source": "cache", "stale": False})
        return out

    if live:
        try:
            params = {
                "latitude": CITY_LAT, "longitude": CITY_LON,
                "start_date": date_str, "end_date": date_str,
                "hourly": "precipitation", "timezone": TIMEZONE,
            }
            r = requests.get(f"{OPEN_METEO_ARCHIVE}/archive", params=params,
                             timeout=REQUEST_TIMEOUT_S + 4)
            r.raise_for_status()
            j = r.json()
            hourly = j.get("hourly", {}) or {}
            vals = [float(v or 0.0) for v in (hourly.get("precipitation") or [])][:24]
            times = list(hourly.get("time") or [])[:24]
            if len(vals) < 24:
                vals = (vals + [0.0] * 24)[:24]
            value = {"date": date_str, "hourly_precip_mm": vals, "hourly_times": times,
                     "provider": "Open-Meteo Archive (ERA5 reanalysis)"}
            cache_set(key, value)
            out = dict(value)
            out.update({"source": "open-meteo-archive", "stale": False})
            return out
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:200]
    else:
        err = "live=False and no cached archive"

    # Offline fallback: a synthetic heavy-rain day shape. NOT archive data.
    synthetic = [2, 3, 5, 8, 12, 18, 24, 28, 30, 26, 22, 18, 15, 12, 10, 8, 6, 5, 4, 3, 2, 2, 1, 1]
    return {
        "date": date_str,
        "hourly_precip_mm": [float(v) for v in synthetic],
        "hourly_times": [f"{date_str}T{h:02d}:00" for h in range(24)],
        "provider": "synthetic-fallback",
        "source": "synthetic-fallback",
        "stale": True,
        "error": err,
        "note": "Archive unreachable. This is a SYNTHETIC rainfall shape, not a historical record.",
    }

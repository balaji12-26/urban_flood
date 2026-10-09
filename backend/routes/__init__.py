"""
Shared helpers for FloodSense routes: zone loading and observation assembly.
Routes stay thin; all scoring goes through the pure risk engine.
"""
import json
import os
import time

from backend.config import (
    WEIGHTS, K, THRESHOLDS, DATA_LABELS, OUTPUT_LABEL, CITY,
)
from backend.engine.risk_engine import compute_risk, sanitize_observations, get_water_level_views
from backend.engine.alert_engine import get_action
from backend.services.sensor_simulator import get_water_level, describe as describe_sensor

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

GLOBAL_DISCLAIMER = (
    "Relative Flood Risk Index (0–100). Not a probability. Not a validated prediction. "
    "For scenario exploration and zone comparison only."
)
BOUNDARY_DISCLAIMER = (
    "Approximate demonstration polygons. Not administrative wards or hydrological catchments."
)

_zones_cache = None


def load_zones() -> list:
    global _zones_cache
    if _zones_cache is None:
        with open(os.path.join(_DATA_DIR, "zone_profiles.json"), "r", encoding="utf-8") as f:
            _zones_cache = json.load(f)
    return [dict(z) for z in _zones_cache]  # defensive copies: routes never mutate profiles


def load_geojson() -> dict:
    with open(os.path.join(_DATA_DIR, "city_zones.geojson"), "r", encoding="utf-8") as f:
        return json.load(f)


def zone_by_id(zid: str):
    for z in load_zones():
        if z["id"] == zid:
            return z
    return None


def build_observations(zones: list, weather: dict, sensor_mode: str = "live",
                       seed: int = 42, now: float = None) -> tuple:
    """
    Returns (obs_map, flags_map). Water level comes ONLY from the sensor simulator.
    City-wide rainfall is applied to every zone (one Open-Meteo point for Chennai).
    """
    now = time.time() if now is None else now
    obs_map, flags_map = {}, {}
    precip = weather.get("precip_1h_mm")
    forecast = weather.get("forecast_6h_mm")
    for z in zones:
        wl = get_water_level(
            z["id"], now, precip or 0.0, seed=seed, mode=sensor_mode,
            baseline_cm=z["baseline_water_level_cm"],
        )
        raw = {"precip_1h_mm": precip, "forecast_6h_mm": forecast, "water_level_cm": wl}
        clean, flags = sanitize_observations(raw, z)
        obs_map[z["id"]] = clean
        flags_map[z["id"]] = flags
    return obs_map, flags_map


def enrich_zone(zone: dict, obs: dict, flags: dict, scenario: dict = None,
                weights: dict = None, k: float = None) -> dict:
    """One zone's full API record: profile + observations + risk + views + action."""
    risk = compute_risk(zone, obs, scenario=scenario, weights=weights, k=k)
    views = get_water_level_views(zone, obs, scenario) if weights is None and k is None else None
    action = get_action(risk["risk_level"], risk["top_dynamic"])
    return {
        "id": zone["id"],
        "name": zone["name"],
        "lat": zone["lat"],
        "lon": zone["lon"],
        "notes": zone["notes"],
        "profile": {
            "max_safe_rain_1h": zone["max_safe_rain_1h"],
            "max_safe_rain_6h": zone["max_safe_rain_6h"],
            "flood_water_level_cm": zone["flood_water_level_cm"],
            "baseline_water_level_cm": zone["baseline_water_level_cm"],
            "drainage_capacity_0_1": zone["drainage_capacity_0_1"],
            "terrain_risk_0_1": zone["terrain_risk_0_1"],
            "historical_flood_freq_0_1": zone["historical_flood_freq_0_1"],
        },
        "observations": {
            "precip_1h_mm": obs["precip_1h_mm"],
            "forecast_6h_mm": obs["forecast_6h_mm"],
            "forecast_6h_total_mm": round(sum(obs["forecast_6h_mm"]), 2),
            "water_level_cm": obs["water_level_cm"],
        },
        "quality_flags": flags,
        "scenario_applied": scenario or {},
        "risk": risk,
        "water_level_views": views,
        "action": action,
    }


def envelope(zones_out: list, weather: dict, sensor_mode: str, seed: int,
             extra: dict = None) -> dict:
    out = {
        "label": OUTPUT_LABEL,
        "city": CITY,
        "generated_at": time.time(),
        "weather": weather,
        "sensor": describe_sensor(sensor_mode, seed),
        "model": {"weights": WEIGHTS, "k": K, "thresholds": THRESHOLDS, "data_labels": DATA_LABELS},
        "disclaimer": GLOBAL_DISCLAIMER,
        "boundary_disclaimer": BOUNDARY_DISCLAIMER,
        "zones": zones_out,
    }
    if extra:
        out.update(extra)
    return out

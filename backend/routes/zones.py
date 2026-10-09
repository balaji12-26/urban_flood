"""GET /api/zones, /api/zones/<id>, /api/geojson, /api/methods"""
from flask import Blueprint, jsonify, request

from backend.routes import (
    load_zones, load_geojson, zone_by_id, build_observations, enrich_zone, envelope,
    BOUNDARY_DISCLAIMER,
)
from backend.services.weather_service import get_current_weather
from backend.config import WEIGHTS, K, THRESHOLDS, DATA_LABELS

bp = Blueprint("zones", __name__)

METHODS_TEXT = """FloodSense — Methods & Limitations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT: Relative Flood Risk Index (0–100).
Not a probability. Not a validated prediction.
For scenario exploration and zone comparison only.

FORMULA: index = 100 × (1 − exp(−Σ(factor × weight) / 0.7))
Weights: rainfall 0.30 · forecast 0.20 · water_level 0.20
         drainage 0.15 · terrain 0.10 · history 0.05

DATA SOURCES:
  LIVE        Current rainfall       Open-Meteo API
  FORECAST    Next 6h rainfall       Open-Meteo API
  SIMULATED   Water level            Synthetic sensor (no real device)
  DERIVED     Terrain risk           SRTM elevation, OpenTopoData
  PROFILE     Drainage, history      Zone characteristics

ZONE BOUNDARIES: Approximate demonstration polygons.
Not administrative wards or hydrological catchments.

CANNOT DO: Predict exact flood onset · Replace IMD/NDMA ·
Account for real-time drainage state or upstream inflow.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def _flag(name: str, default: bool) -> bool:
    v = request.args.get(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _common():
    live = _flag("live", True)
    sensor_mode = request.args.get("sensor_mode", "live")
    if sensor_mode not in ("live", "frozen"):
        sensor_mode = "live"
    try:
        seed = int(request.args.get("seed", 42))
    except ValueError:
        seed = 42
    sample = request.args.get("weather") == "sample"
    weather = get_current_weather(live=live, sample=sample)
    zones = load_zones()
    obs_map, flags_map = build_observations(zones, weather, sensor_mode, seed)
    return zones, weather, obs_map, flags_map, sensor_mode, seed


@bp.get("/api/zones")
def all_zones():
    zones, weather, obs_map, flags_map, sensor_mode, seed = _common()
    out = [enrich_zone(z, obs_map[z["id"]], flags_map[z["id"]]) for z in zones]
    out.sort(key=lambda r: -r["risk"]["index"])
    for rank, r in enumerate(out, 1):
        r["rank"] = rank
    return jsonify(envelope(out, weather, sensor_mode, seed))


@bp.get("/api/zones/<zid>")
def one_zone(zid):
    z = zone_by_id(zid)
    if z is None:
        return jsonify({"error": f"unknown zone '{zid}'"}), 404
    zones, weather, obs_map, flags_map, sensor_mode, seed = _common()
    rec = enrich_zone(z, obs_map[zid], flags_map[zid])
    return jsonify(envelope([rec], weather, sensor_mode, seed))


@bp.get("/api/geojson")
def geojson():
    g = load_geojson()
    g.setdefault("_disclaimer", BOUNDARY_DISCLAIMER)
    return jsonify(g)


@bp.get("/api/methods")
def methods():
    return jsonify({
        "text": METHODS_TEXT,
        "weights": WEIGHTS, "k": K, "thresholds": THRESHOLDS, "data_labels": DATA_LABELS,
        "formula": "index = 100 * (1 - exp(-sum(factor_raw * weight) / k))",
    })


@bp.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "floodsense", "zones": len(load_zones())})

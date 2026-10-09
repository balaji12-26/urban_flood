"""
POST /api/scenario
Body: {
  "zone_scenarios": {"velachery": {"rainfall_multiplier": 2.0, ...}, ...},   # per-zone (LOCAL)
  "global": {"rainfall_multiplier": 1.5},                                     # optional, copied to every zone
  "weights": {...}, "k": 0.7,                                                 # optional sweeps
  "sensor_mode": "live"|"frozen", "seed": 42, "live": true
}
Per-zone entries override global ones for that zone only.
"""
from flask import Blueprint, jsonify, request

from backend.config import WEIGHTS
from backend.engine.scenario_engine import apply_scenario_to_all_zones, clamp_scenario
from backend.engine.risk_engine import get_water_level_views
from backend.engine.alert_engine import get_action
from backend.routes import load_zones, build_observations, enrich_zone, envelope
from backend.services.weather_service import get_current_weather

bp = Blueprint("scenario", __name__)


def _parse_weights(raw):
    if not isinstance(raw, dict):
        return None, None
    w = {}
    for key in WEIGHTS:
        try:
            w[key] = max(0.0, float(raw.get(key, WEIGHTS[key])))
        except (TypeError, ValueError):
            w[key] = WEIGHTS[key]
    total = sum(w.values())
    if total <= 0:
        return None, "weights sum to zero; ignored"
    return {k: v / total for k, v in w.items()}, None  # renormalised to 1.0


@bp.post("/api/scenario")
def scenario():
    body = request.get_json(silent=True) or {}
    zones = load_zones()

    live = bool(body.get("live", True))
    sensor_mode = body.get("sensor_mode", "live")
    if sensor_mode not in ("live", "frozen"):
        sensor_mode = "live"
    try:
        seed = int(body.get("seed", 42))
    except (TypeError, ValueError):
        seed = 42

    weather = get_current_weather(live=live, sample=body.get("weather") == "sample")
    obs_map, flags_map = build_observations(zones, weather, sensor_mode, seed)

    # Build an explicit per-zone scenario map. Each zone gets its own dict object.
    global_sc = clamp_scenario(body.get("global"))
    per_zone_raw = body.get("zone_scenarios") or {}
    zone_scenarios = {}
    for z in zones:
        local = dict(global_sc)
        if isinstance(per_zone_raw, dict) and z["id"] in per_zone_raw:
            local.update(clamp_scenario(per_zone_raw[z["id"]]))
        if local:
            zone_scenarios[z["id"]] = local

    weights, w_note = _parse_weights(body.get("weights"))
    k = None
    if body.get("k") is not None:
        try:
            k = float(body["k"])
            if not (0.05 <= k <= 5.0):
                k = None
        except (TypeError, ValueError):
            k = None

    baseline = apply_scenario_to_all_zones(zones, obs_map)                         # no scenario, default model
    scen = apply_scenario_to_all_zones(zones, obs_map, zone_scenarios, weights=weights, k=k)

    out = []
    for z in zones:
        zid = z["id"]
        sc = zone_scenarios.get(zid)
        rec = {
            "id": zid, "name": z["name"], "lat": z["lat"], "lon": z["lon"],
            "scenario_applied": sc or {},
            "baseline_index": baseline[zid]["index"],
            "baseline_level": baseline[zid]["risk_level"],
            "risk": scen[zid],
            "delta": round(scen[zid]["index"] - baseline[zid]["index"], 1),
            "level_changed": scen[zid]["risk_level"] != baseline[zid]["risk_level"],
            "observations": obs_map[zid],
            "quality_flags": flags_map[zid],
            "water_level_views": get_water_level_views(z, obs_map[zid], sc) if weights is None and k is None else None,
            "action": get_action(scen[zid]["risk_level"], scen[zid]["top_dynamic"]),
        }
        out.append(rec)
    out.sort(key=lambda r: -r["risk"]["index"])
    for rank, r in enumerate(out, 1):
        r["rank"] = rank

    extra = {
        "scenario": {"global": global_sc, "zone_scenarios": zone_scenarios},
        "weights_override": weights, "k_override": k,
    }
    if w_note:
        extra["note"] = w_note
    return jsonify(envelope(out, weather, sensor_mode, seed, extra))

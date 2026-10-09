"""
GET /api/forecast-curve?zone=<id|all>&rainfall_multiplier=&drainage_blockage=&water_level_rise_cm=

Projects the Relative Flood Risk Index hour-by-hour over the next 6 hours by
sliding the forecast window:
  hour 0 : current precip, forecast[0:6]
  hour h : precip = forecast[h-1], forecast window = forecast[h:h+6] padded with 0,
           water level = simulated level responding to that hour's precip (frozen noise).
This is a scenario projection, NOT a prediction.
"""
import time

from flask import Blueprint, jsonify, request

from backend.engine.risk_engine import compute_risk, sanitize_observations
from backend.engine.scenario_engine import clamp_scenario
from backend.routes import load_zones, zone_by_id
from backend.services.sensor_simulator import get_water_level, RAIN_RESPONSE_CM_PER_MM
from backend.services.weather_service import get_current_weather
from backend.config import OUTPUT_LABEL

bp = Blueprint("forecast_curve", __name__)


def _curve_for_zone(zone: dict, weather: dict, scenario: dict, now: float) -> dict:
    precip_now = float(weather.get("precip_1h_mm") or 0.0)
    fc = [float(v or 0.0) for v in (weather.get("forecast_6h_mm") or [])]
    fc = (fc + [0.0] * 6)[:6]

    base_wl = get_water_level(zone["id"], now, precip_now, mode="live",
                              baseline_cm=zone["baseline_water_level_cm"])
    points = []
    for h in range(0, 7):
        precip_h = precip_now if h == 0 else fc[h - 1]
        window = (fc[h:h + 6] + [0.0] * 6)[:6]
        # Simulated level: today's level + response to this hour's rain, no fresh noise.
        wl_h = max(0.0, base_wl + (precip_h - precip_now) * RAIN_RESPONSE_CM_PER_MM)
        obs, _ = sanitize_observations(
            {"precip_1h_mm": precip_h, "forecast_6h_mm": window, "water_level_cm": round(wl_h, 1)}, zone
        )
        r = compute_risk(zone, obs, scenario=scenario)
        points.append({
            "hour": h, "label": "now" if h == 0 else f"+{h}h",
            "precip_mm": round(precip_h, 2),
            "forecast_window_mm": round(sum(window), 2),
            "water_level_cm": round(wl_h, 1),
            "index": r["index"], "risk_level": r["risk_level"], "top_driver": r["top_driver"],
        })
    return {
        "id": zone["id"], "name": zone["name"],
        "points": points,
        "peak": max(points, key=lambda p: p["index"]),
    }


@bp.get("/api/forecast-curve")
def forecast_curve():
    zid = request.args.get("zone", "all")
    live = request.args.get("live", "1").lower() in ("1", "true", "yes", "on")
    scenario = clamp_scenario({
        "rainfall_multiplier": request.args.get("rainfall_multiplier"),
        "drainage_blockage": request.args.get("drainage_blockage"),
        "water_level_rise_cm": request.args.get("water_level_rise_cm"),
    } if any(k in request.args for k in ("rainfall_multiplier", "drainage_blockage", "water_level_rise_cm")) else {})

    weather = get_current_weather(live=live, sample=request.args.get("weather") == "sample")
    now = time.time()
    if zid == "all":
        zones = load_zones()
    else:
        z = zone_by_id(zid)
        if z is None:
            return jsonify({"error": f"unknown zone '{zid}'"}), 404
        zones = [z]

    curves = [_curve_for_zone(z, weather, scenario, now) for z in zones]
    return jsonify({
        "label": OUTPUT_LABEL,
        "generated_at": now,
        "weather": weather,
        "scenario_applied": scenario,
        "note": "Hour-by-hour projection using the sliding forecast window and a SIMULATED water level. "
                "Scenario exploration only — not a flood prediction.",
        "curves": curves,
    })

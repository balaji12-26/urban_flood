"""
GET /api/validation/monotone
GET /api/validation/sensitivity
GET /api/validation/baseline
GET /api/validation/replay?date=2015-12-01
GET /api/validation/all
All run live against the engine using the current observations.
"""
from flask import Blueprint, jsonify, request

from backend.routes import load_zones, build_observations
from backend.services.weather_service import get_current_weather
from backend.validation import monotone_tests, weight_sensitivity, baseline_comparison, replay

bp = Blueprint("validation", __name__)


def _ctx():
    live = request.args.get("live", "1").lower() in ("1", "true", "yes", "on")
    sensor_mode = request.args.get("sensor_mode", "frozen")  # frozen by default: stable validation numbers
    if sensor_mode not in ("live", "frozen"):
        sensor_mode = "frozen"
    weather = get_current_weather(live=live, sample=request.args.get("weather") == "sample")
    zones = load_zones()
    obs_map, _ = build_observations(zones, weather, sensor_mode)
    return zones, obs_map, weather, sensor_mode, live


@bp.get("/api/validation/monotone")
def monotone():
    zones, obs_map, weather, sensor_mode, _ = _ctx()
    out = monotone_tests.run(zones, obs_map)
    out.update({"weather_stale": weather.get("stale"), "sensor_mode": sensor_mode})
    return jsonify(out)


@bp.get("/api/validation/sensitivity")
def sensitivity():
    zones, obs_map, weather, sensor_mode, _ = _ctx()
    out = weight_sensitivity.run(zones, obs_map)
    out.update({"weather_stale": weather.get("stale"), "sensor_mode": sensor_mode})
    return jsonify(out)


@bp.get("/api/validation/baseline")
def baseline():
    zones, obs_map, weather, sensor_mode, _ = _ctx()
    out = baseline_comparison.run(zones, obs_map)
    out.update({"weather_stale": weather.get("stale"), "sensor_mode": sensor_mode})
    return jsonify(out)


@bp.get("/api/validation/replay")
def replay_route():
    date = request.args.get("date", replay.DEFAULT_DATE)
    live = request.args.get("live", "1").lower() in ("1", "true", "yes", "on")
    return jsonify(replay.run(date, load_zones(), live=live))


@bp.get("/api/validation/all")
def all_checks():
    zones, obs_map, weather, sensor_mode, live = _ctx()
    date = request.args.get("date", replay.DEFAULT_DATE)
    return jsonify({
        "weather_stale": weather.get("stale"), "weather_source": weather.get("source"),
        "sensor_mode": sensor_mode,
        "monotone": monotone_tests.run(zones, obs_map),
        "sensitivity": weight_sensitivity.run(zones, obs_map),
        "baseline": baseline_comparison.run(zones, obs_map),
        "replay": replay.run(date, zones, live=live),
    })

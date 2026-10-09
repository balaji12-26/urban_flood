import pytest
from backend.engine.risk_engine import (
    soft_scale, compute_risk, sanitize_observations,
    get_water_level_views, classify
)
from backend.config import WEIGHTS, K

VELACHERY = {
    "id": "velachery", "max_safe_rain_1h": 25.0, "max_safe_rain_6h": 80.0,
    "flood_water_level_cm": 120.0, "baseline_water_level_cm": 45.0,
    "drainage_capacity_0_1": 0.30, "terrain_risk_0_1": 0.80,
    "historical_flood_freq_0_1": 0.90,
}
GUINDY = {
    "id": "guindy", "max_safe_rain_1h": 38.0, "max_safe_rain_6h": 120.0,
    "flood_water_level_cm": 85.0, "baseline_water_level_cm": 15.0,
    "drainage_capacity_0_1": 0.70, "terrain_risk_0_1": 0.30,
    "historical_flood_freq_0_1": 0.30,
}
BASE_OBS = {
    "precip_1h_mm": 15.0,
    "forecast_6h_mm": [3.0, 2.5, 2.0, 1.5, 1.0, 0.5],
    "water_level_cm": 50.0,
}

def test_soft_scale_no_ceiling():
    assert soft_scale(0.5) < soft_scale(1.0) < soft_scale(2.0) < soft_scale(3.0)
    assert soft_scale(3.0) < 100.0

def test_repeatability():
    results = [compute_risk(VELACHERY, BASE_OBS)["index"] for _ in range(5)]
    assert len(set(results)) == 1, f"Non-deterministic: {results}"

def test_monotone_rainfall():
    indices = [
        compute_risk(VELACHERY, BASE_OBS, scenario={"rainfall_multiplier": m})["index"]
        for m in [0.5, 1.0, 2.0, 3.0]
    ]
    assert indices == sorted(indices), f"Not monotone: {indices}"

def test_monotone_drainage():
    indices = [
        compute_risk(VELACHERY, BASE_OBS, scenario={"drainage_blockage": b})["index"]
        for b in [0.0, 0.2, 0.5, 0.8]
    ]
    assert indices == sorted(indices), f"Drainage not monotone: {indices}"

def test_missing_data_safe():
    raw = {"precip_1h_mm": None, "forecast_6h_mm": None, "water_level_cm": None}
    clean, flags = sanitize_observations(raw, VELACHERY)
    result = compute_risk(VELACHERY, clean)
    assert 0 <= result["index"] <= 100
    assert "forecast" in flags and "rainfall" in flags and "water_level" in flags

def test_zone_independence():
    from backend.engine.scenario_engine import apply_scenario_to_all_zones
    zones   = [VELACHERY, GUINDY]
    obs_map = {z["id"]: BASE_OBS for z in zones}
    baseline_guindy = compute_risk(GUINDY, BASE_OBS)["index"]
    results = apply_scenario_to_all_zones(
        zones, obs_map,
        zone_scenarios={"velachery": {"drainage_blockage": 0.6}}
    )
    assert results["guindy"]["index"] == baseline_guindy, \
        f"ISOLATION BROKEN: Guindy {baseline_guindy} → {results['guindy']['index']}"
    assert results["velachery"]["index"] > baseline_guindy

def test_weights_sum():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

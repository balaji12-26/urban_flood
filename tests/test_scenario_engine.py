from backend.engine.risk_engine import compute_risk
from backend.engine.scenario_engine import (
    apply_scenario_to_all_zones, apply_global_scenario, clamp_scenario
)
from tests.test_risk_engine import VELACHERY, GUINDY, BASE_OBS

ZONES = [VELACHERY, GUINDY]
OBS = {z["id"]: BASE_OBS for z in ZONES}


def test_no_scenario_equals_compute_risk():
    out = apply_scenario_to_all_zones(ZONES, OBS)
    for z in ZONES:
        assert out[z["id"]] == compute_risk(z, BASE_OBS)


def test_scenario_is_local():
    base = apply_scenario_to_all_zones(ZONES, OBS)
    out = apply_scenario_to_all_zones(ZONES, OBS, {"guindy": {"rainfall_multiplier": 3.0}})
    assert out["velachery"]["index"] == base["velachery"]["index"]
    assert out["guindy"]["index"] > base["guindy"]["index"]


def test_unknown_zone_scenario_ignored():
    base = apply_scenario_to_all_zones(ZONES, OBS)
    out = apply_scenario_to_all_zones(ZONES, OBS, {"nowhere": {"rainfall_multiplier": 5.0}})
    assert out == base


def test_global_scenario_hits_every_zone():
    base = apply_scenario_to_all_zones(ZONES, OBS)
    out = apply_global_scenario(ZONES, OBS, {"water_level_rise_cm": 40})
    for z in ZONES:
        assert out[z["id"]]["index"] > base[z["id"]]["index"]


def test_global_scenario_copies_not_shared():
    out = apply_global_scenario(ZONES, OBS, {"drainage_blockage": 0.5})
    # per-zone results must be independent objects
    assert out["velachery"] is not out["guindy"]


def test_missing_obs_falls_back_to_sanitized_defaults():
    out = apply_scenario_to_all_zones(ZONES, {"velachery": BASE_OBS})
    assert 0 <= out["guindy"]["index"] <= 100


def test_clamp_scenario_bounds_and_junk():
    c = clamp_scenario({"rainfall_multiplier": 99, "drainage_blockage": -1,
                        "water_level_rise_cm": "abc", "bogus": 1})
    assert c == {"rainfall_multiplier": 5.0, "drainage_blockage": 0.0}
    assert clamp_scenario(None) == {}


def test_weights_override_does_not_mutate_defaults():
    from backend.config import WEIGHTS
    before = dict(WEIGHTS)
    custom = {"rainfall": 0.5, "forecast": 0.1, "water_level": 0.1,
              "drainage": 0.1, "terrain": 0.1, "history": 0.1}
    apply_scenario_to_all_zones(ZONES, OBS, weights=custom, k=0.5)
    assert WEIGHTS == before

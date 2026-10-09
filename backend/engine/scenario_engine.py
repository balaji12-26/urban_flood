"""
FloodSense Scenario Engine.
Applies per-zone scenario overrides. STRICTLY LOCAL: a scenario keyed to one
zone is never passed to any other zone's compute_risk() call.
"""
from backend.engine.risk_engine import compute_risk, sanitize_observations

SCENARIO_BOUNDS = {
    "rainfall_multiplier":  (0.0, 5.0),
    "drainage_blockage":    (0.0, 1.0),
    "water_level_rise_cm":  (0.0, 300.0),
}


def clamp_scenario(scenario: dict) -> dict:
    """Coerce a raw scenario dict into a safe, bounded one. Never raises."""
    clean = {}
    if not isinstance(scenario, dict):
        return clean
    for key, (lo, hi) in SCENARIO_BOUNDS.items():
        if key not in scenario:
            continue
        try:
            v = float(scenario[key])
        except (TypeError, ValueError):
            continue
        if v != v:  # NaN guard
            continue
        clean[key] = min(hi, max(lo, v))
    return clean


def apply_scenario_to_all_zones(
    zones: list,
    obs_map: dict,
    zone_scenarios: dict = None,
    weights: dict = None,
    k: float = None,
) -> dict:
    """
    Returns {zone_id: compute_risk(...)} for every zone.
    zone_scenarios: {zone_id: scenario_dict}. A zone with no entry gets NO scenario.
    Scenarios are looked up by the zone's own id ONLY — never shared, never merged.
    """
    zone_scenarios = zone_scenarios or {}
    results = {}
    for zone in zones:
        zid = zone["id"]
        local_scenario = zone_scenarios.get(zid)          # None for untouched zones
        obs = obs_map.get(zid)
        if obs is None:
            obs, _ = sanitize_observations({}, zone)
        results[zid] = compute_risk(
            zone, obs,
            scenario=local_scenario,
            weights=weights,
            k=k,
        )
    return results


def apply_global_scenario(zones: list, obs_map: dict, scenario: dict,
                          weights: dict = None, k: float = None) -> dict:
    """
    Convenience: the SAME scenario applied to every zone (city-wide storm).
    Implemented by building an explicit per-zone map so isolation semantics hold
    (each zone receives its own copy; nothing is shared by reference).
    """
    sc = clamp_scenario(scenario)
    per_zone = {z["id"]: dict(sc) for z in zones}
    return apply_scenario_to_all_zones(zones, obs_map, per_zone, weights=weights, k=k)

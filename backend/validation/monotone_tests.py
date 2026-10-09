"""
Monotonicity checks, run live against the engine with current observations.
For every zone and every scenario lever, raising the lever must never lower the index.
"""
from backend.engine.risk_engine import compute_risk

LEVERS = {
    "rainfall_multiplier": [0.5, 1.0, 1.5, 2.0, 3.0],
    "drainage_blockage":   [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "water_level_rise_cm": [0, 20, 40, 60, 100],
}


def _is_nondecreasing(seq):
    return all(b >= a for a, b in zip(seq, seq[1:]))


def run(zones: list, obs_map: dict) -> dict:
    checks = []
    for z in zones:
        obs = obs_map[z["id"]]
        for lever, values in LEVERS.items():
            idx = [compute_risk(z, obs, scenario={lever: v})["index"] for v in values]
            checks.append({
                "zone": z["id"], "zone_name": z.get("name", z["id"]),
                "lever": lever, "values": values, "indices": idx,
                "monotone": _is_nondecreasing(idx),
            })
    passed = sum(1 for c in checks if c["monotone"])
    return {
        "name": "Monotonicity",
        "description": "Raising rainfall, drainage blockage, or water level must never lower the index.",
        "passed": passed, "total": len(checks), "all_passed": passed == len(checks),
        "checks": checks,
    }

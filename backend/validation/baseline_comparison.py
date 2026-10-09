"""
Baseline comparison: does the full weighted model add anything over naive baselines?
Baselines (all passed through the same soft_scale so numbers are comparable):
  rainfall_only  : weight 1.0 on rainfall, 0 elsewhere
  static_only    : profile factors only (drainage/terrain/history, renormalised)
  equal_weights  : 1/6 each
Reports per-zone indices and Spearman rank agreement with the full model.
"""
from backend.config import WEIGHTS
from backend.engine.scenario_engine import apply_scenario_to_all_zones
from backend.validation.weight_sensitivity import _ranking, _spearman

BASELINES = {
    "rainfall_only": {"rainfall": 1.0, "forecast": 0.0, "water_level": 0.0,
                      "drainage": 0.0, "terrain": 0.0, "history": 0.0},
    "static_only":   {"rainfall": 0.0, "forecast": 0.0, "water_level": 0.0,
                      "drainage": 0.5, "terrain": 1 / 3, "history": 1 / 6},
    "equal_weights": {k: 1 / 6 for k in WEIGHTS},
}


def run(zones: list, obs_map: dict) -> dict:
    full = apply_scenario_to_all_zones(zones, obs_map)
    full_rank = _ranking(full)
    rows = {"full_model": {zid: r["index"] for zid, r in full.items()}}
    comparisons = []
    for name, w in BASELINES.items():
        res = apply_scenario_to_all_zones(zones, obs_map, weights=w)
        rank = _ranking(res)
        rows[name] = {zid: r["index"] for zid, r in res.items()}
        comparisons.append({
            "baseline": name, "weights": {k: round(v, 4) for k, v in w.items()},
            "ranking": rank, "rank_agreement_with_full": _spearman(full_rank, rank),
            "spread": round(max(rows[name].values()) - min(rows[name].values()), 1),
        })
    return {
        "name": "Baseline comparison",
        "description": "Full model vs rainfall-only, static-only and equal-weight baselines. "
                       "High agreement with static-only means current weather is not separating zones; "
                       "low agreement with rainfall-only shows the profile factors matter.",
        "full_ranking": full_rank,
        "full_spread": round(max(rows["full_model"].values()) - min(rows["full_model"].values()), 1),
        "indices_by_model": rows,
        "comparisons": comparisons,
        "zone_names": {z["id"]: z.get("name", z["id"]) for z in zones},
    }

"""
Weight & k sensitivity sweep.
Perturb each weight by +/- delta (renormalised to sum 1.0) and k by +/- 0.2,
then ask: does the zone RANKING change? Reports rank agreement with the default model.
"""
from backend.config import WEIGHTS, K
from backend.engine.scenario_engine import apply_scenario_to_all_zones

DELTA = 0.10
K_VALUES = [0.5, 0.7, 0.9]


def _ranking(results: dict) -> list:
    return [zid for zid, _ in sorted(results.items(), key=lambda kv: -kv[1]["index"])]


def _spearman(rank_a: list, rank_b: list) -> float:
    """Spearman rank correlation between two orderings of the same ids."""
    n = len(rank_a)
    if n < 2:
        return 1.0
    pos_b = {zid: i for i, zid in enumerate(rank_b)}
    d2 = sum((i - pos_b[zid]) ** 2 for i, zid in enumerate(rank_a))
    return round(1 - (6 * d2) / (n * (n * n - 1)), 3)


def _perturbed(factor: str, delta: float) -> dict:
    w = dict(WEIGHTS)
    w[factor] = max(0.0, w[factor] + delta)
    total = sum(w.values())
    return {k: round(v / total, 4) for k, v in w.items()}


def run(zones: list, obs_map: dict) -> dict:
    base = apply_scenario_to_all_zones(zones, obs_map)
    base_rank = _ranking(base)
    base_idx = {zid: r["index"] for zid, r in base.items()}

    sweeps = []
    for factor in WEIGHTS:
        for delta in (-DELTA, +DELTA):
            w = _perturbed(factor, delta)
            res = apply_scenario_to_all_zones(zones, obs_map, weights=w)
            rank = _ranking(res)
            sweeps.append({
                "kind": "weight", "factor": factor, "delta": delta, "weights": w,
                "indices": {zid: r["index"] for zid, r in res.items()},
                "max_abs_change": round(max(abs(res[z]["index"] - base_idx[z]) for z in base_idx), 1),
                "ranking": rank, "rank_agreement": _spearman(base_rank, rank),
                "top_zone_unchanged": rank[0] == base_rank[0],
            })
    for kv in K_VALUES:
        res = apply_scenario_to_all_zones(zones, obs_map, k=kv)
        rank = _ranking(res)
        sweeps.append({
            "kind": "k", "factor": "k", "delta": round(kv - K, 2), "k": kv,
            "indices": {zid: r["index"] for zid, r in res.items()},
            "max_abs_change": round(max(abs(res[z]["index"] - base_idx[z]) for z in base_idx), 1),
            "ranking": rank, "rank_agreement": _spearman(base_rank, rank),
            "top_zone_unchanged": rank[0] == base_rank[0],
        })

    agreements = [s["rank_agreement"] for s in sweeps]
    return {
        "name": "Weight sensitivity",
        "description": f"Each weight perturbed by ±{DELTA} (renormalised) and k swept over {K_VALUES}. "
                       "Reports whether the zone ranking survives.",
        "baseline_ranking": base_rank,
        "baseline_indices": base_idx,
        "min_rank_agreement": min(agreements), "mean_rank_agreement": round(sum(agreements) / len(agreements), 3),
        "top_zone_stable_in": sum(1 for s in sweeps if s["top_zone_unchanged"]),
        "total_sweeps": len(sweeps),
        "sweeps": sweeps,
    }

"""
FloodSense Risk Engine — Pure Functions Only.
No randomness. No I/O. No side effects.
Same inputs → same output, always.
"""
import math
from backend.config import WEIGHTS, K, THRESHOLDS, DYNAMIC_FACTORS, STATIC_FACTORS, DATA_LABELS


def soft_scale(weighted_sum: float, k: float = K) -> float:
    """
    Maps [0, ∞) → [0, 100). No hard ceiling.
    LOWER k = FASTER rise for the same weighted_sum.
    k=0.7: raw=1.0 → 76.0, raw=2.0 → 94.0, raw=3.0 → 98.7
    """
    return 100.0 * (1.0 - math.exp(-weighted_sum / k))


def classify(index: float, thresholds: dict = None) -> str:
    t = thresholds or THRESHOLDS
    if index < t["MODERATE"]: return "LOW"
    if index < t["HIGH"]:     return "MODERATE"
    if index < t["CRITICAL"]: return "HIGH"
    return "CRITICAL"


def sanitize_observations(obs: dict, zone: dict) -> tuple:
    """
    Coerce raw observations to safe values. Never raises.
    Returns (clean_obs, quality_flags).
    compute_risk() must only receive clean_obs from here.
    """
    def nonneg(val, default):
        try:
            v = float(val)
            if math.isnan(v) or math.isinf(v):
                return default
            return v if v >= 0 else default
        except (TypeError, ValueError):
            return default

    obs = obs or {}
    flags = {}
    clean = {}

    clean["precip_1h_mm"] = nonneg(obs.get("precip_1h_mm"), default=0.0)
    if obs.get("precip_1h_mm") is None:
        flags["rainfall"] = "MISSING — using 0.0 mm"

    raw_fc = obs.get("forecast_6h_mm")
    if raw_fc is None or not isinstance(raw_fc, (list, tuple)) or len(raw_fc) == 0:
        clean["forecast_6h_mm"] = [0.0] * 6
        flags["forecast"] = "MISSING — using zero forecast"
    else:
        clean["forecast_6h_mm"] = [max(0.0, nonneg(v, 0.0)) for v in raw_fc]

    clean["water_level_cm"] = nonneg(
        obs.get("water_level_cm"),
        default=zone["baseline_water_level_cm"]
    )
    if obs.get("water_level_cm") is None:
        flags["water_level"] = "MISSING — using zone baseline"

    return clean, flags


def compute_risk(
    zone: dict,
    observations: dict,
    scenario: dict = None,
    weights: dict = None,
    k: float = None,
) -> dict:
    """
    Pure function. Computes the Relative Flood Risk Index for one zone.
    scenario overrides are LOCAL — they affect only this zone's call.
    weights/k allow sensitivity sweeps without changing module constants.
    """
    w     = weights if weights is not None else WEIGHTS
    k_val = k       if k       is not None else K
    sc    = scenario or {}

    rain_mult = sc.get("rainfall_multiplier", 1.0)
    drain_blk = sc.get("drainage_blockage",   0.0)
    wl_rise   = sc.get("water_level_rise_cm", 0.0)

    rain_raw     = (observations["precip_1h_mm"]        * rain_mult) / zone["max_safe_rain_1h"]
    forecast_raw = (sum(observations["forecast_6h_mm"]) * rain_mult) / zone["max_safe_rain_6h"]
    wl_raw       = (observations["water_level_cm"]      + wl_rise)   / zone["flood_water_level_cm"]
    drain_eff    = zone["drainage_capacity_0_1"]         * (1.0 - drain_blk)
    drain_raw    = 1.0 - drain_eff
    terrain_raw  = zone["terrain_risk_0_1"]
    history_raw  = zone["historical_flood_freq_0_1"]

    raws = {
        "rainfall":    rain_raw,
        "forecast":    forecast_raw,
        "water_level": wl_raw,
        "drainage":    drain_raw,
        "terrain":     terrain_raw,
        "history":     history_raw,
    }

    weighted_sum  = sum(raws[key] * w[key] for key in w)
    index         = soft_scale(weighted_sum, k=k_val)
    contributions = {key: round(raws[key] * w[key], 4) for key in w}

    top_driver         = max(contributions, key=contributions.get)
    top_dynamic_driver = max(
        {key: v for key, v in contributions.items() if key in DYNAMIC_FACTORS},
        key=lambda key: contributions[key]
    )
    top_static_driver  = max(
        {key: v for key, v in contributions.items() if key in STATIC_FACTORS},
        key=lambda key: contributions[key]
    )

    return {
        "zone_id":       zone["id"],
        "index":         round(index, 1),
        "risk_level":    classify(index),
        "top_driver":    top_driver,
        "top_dynamic":   top_dynamic_driver,
        "top_static":    top_static_driver,
        "factor_raws":   {key: round(raws[key], 3) for key in raws},
        "contributions": contributions,
        "weighted_sum":  round(weighted_sum, 4),
        "data_labels":   DATA_LABELS,
        "weights_used":  w,
        "k_used":        k_val,
    }


def get_water_level_views(zone: dict, observations: dict, scenario: dict = None) -> dict:
    """
    Shows index with and WITHOUT simulated water-level factor.
    TRUE DROP — no renormalization. Difference = real contribution.
    """
    full       = compute_risk(zone, observations, scenario)
    wl_contrib = full["contributions"]["water_level"]
    partial_sum = full["weighted_sum"] - wl_contrib
    without_wl  = round(soft_scale(partial_sum, k=K), 1)

    return {
        "with_water_level":    full["index"],
        "without_water_level": without_wl,
        "wl_contribution":     round(wl_contrib, 4),
        "note": "without_water_level drops the factor entirely (no renormalization). "
                "Difference is the true water-level contribution to the index.",
    }

"""
FloodSense Sensor Simulator — the ONLY place sensor noise lives.

Pure function. No instance state. No shared RNG. Noise is derived from a
cryptographic hash of (seed, zone_id, 30-second bucket), so the same inputs
always return the same value, and two callers can never perturb each other.

Every value produced here is SIMULATED. There is no real water-level device.
"""
import hashlib
import json
import math
import os

DATA_LABEL = "SIMULATED"
BUCKET_SECONDS = 30
RAIN_RESPONSE_CM_PER_MM = 1.2     # how much a mm of hourly rain lifts the simulated level
NOISE_AMPLITUDE_CM = 4.0          # peak-to-peak/2 deterministic jitter
SLOW_WAVE_AMPLITUDE_CM = 3.0      # slow drift so the demo visibly "breathes"
SLOW_WAVE_PERIOD_S = 600.0

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "zone_profiles.json")
_BASELINES = None


def _baseline_lookup() -> dict:
    """Lazy, read-once lookup of zone baselines. Pure w.r.t. the function inputs."""
    global _BASELINES
    if _BASELINES is None:
        try:
            with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
                _BASELINES = {z["id"]: float(z["baseline_water_level_cm"]) for z in json.load(f)}
        except (OSError, ValueError, KeyError):
            _BASELINES = {}
    return _BASELINES


def _unit_noise(seed: int, zone_id: str, bucket: int, salt: str = "") -> float:
    """Deterministic value in [-1, 1] from a SHA-256 of the inputs. No RNG object."""
    h = hashlib.sha256(f"{seed}:{zone_id}:{bucket}:{salt}".encode("utf-8")).digest()
    n = int.from_bytes(h[:8], "big")
    return (n / float(2 ** 64)) * 2.0 - 1.0


def get_water_level(
    zone_id: str,
    timestamp: float,
    precip_1h_mm: float,
    seed: int = 42,
    mode: str = "live",
    replay_value: float = None,
    baseline_cm: float = None,
) -> float:
    """
    Returns a SIMULATED water level in cm for a zone.

    mode="live"   : baseline + rain response + deterministic 30s-bucket noise
    mode="frozen" : baseline only (stable for screenshots / tests)
    mode="replay" : exactly replay_value (falls back to frozen if None)

    Same (zone_id, timestamp bucket, precip, seed, mode) -> same output, always.
    """
    if baseline_cm is None:
        baseline_cm = _baseline_lookup().get(zone_id, 30.0)
    baseline_cm = float(baseline_cm)

    if mode == "replay":
        if replay_value is None:
            return round(baseline_cm, 1)
        try:
            return round(max(0.0, float(replay_value)), 1)
        except (TypeError, ValueError):
            return round(baseline_cm, 1)

    if mode == "frozen":
        return round(baseline_cm, 1)

    # --- live ---
    try:
        precip = max(0.0, float(precip_1h_mm or 0.0))
    except (TypeError, ValueError):
        precip = 0.0
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        ts = 0.0

    bucket = int(ts // BUCKET_SECONDS)
    rain_lift = precip * RAIN_RESPONSE_CM_PER_MM
    jitter = _unit_noise(seed, zone_id, bucket) * NOISE_AMPLITUDE_CM

    # Slow deterministic wave: phase from a stable per-zone hash, period 10 min.
    # Evaluated at the bucket start so every timestamp in a bucket maps to one value.
    bucket_ts = bucket * BUCKET_SECONDS
    phase = _unit_noise(seed, zone_id, 0, salt="phase") * math.pi
    slow = math.sin((bucket_ts % SLOW_WAVE_PERIOD_S) / SLOW_WAVE_PERIOD_S * 2 * math.pi + phase) \
        * SLOW_WAVE_AMPLITUDE_CM

    level = baseline_cm + rain_lift + jitter + slow
    return round(max(0.0, level), 1)


def describe(mode: str = "live", seed: int = 42) -> dict:
    """Provenance metadata to attach to any response that carries a simulated level."""
    return {
        "label": DATA_LABEL,
        "mode": mode,
        "seed": seed,
        "bucket_seconds": BUCKET_SECONDS,
        "note": "Synthetic water-level sensor. No real device. Noise is deterministic per "
                f"(seed, zone, {BUCKET_SECONDS}s bucket).",
    }

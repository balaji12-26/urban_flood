# ALL constants live here. Module-level, auditable, sweepable.

WEIGHTS = {
    "rainfall":    0.30,   # LIVE
    "forecast":    0.20,   # FORECAST
    "water_level": 0.20,   # SIMULATED
    "drainage":    0.15,   # PROFILE
    "terrain":     0.10,   # DERIVED
    "history":     0.05,   # PROFILE
}
# sum(WEIGHTS.values()) MUST equal 1.00
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, f"WEIGHTS must sum to 1.0, got {sum(WEIGHTS.values())}"

K = 0.7  # Soft-saturation parameter. LOWER k = FASTER rise.
         # At raw=1.0 → index≈76; raw=2.0 → index≈94; raw=3.0 → index≈99

THRESHOLDS = {
    "MODERATE": 30,
    "HIGH":     55,
    "CRITICAL": 75,
}

DYNAMIC_FACTORS = {"rainfall", "forecast", "water_level"}
STATIC_FACTORS  = {"drainage", "terrain", "history"}

DATA_LABELS = {
    "rainfall":    "LIVE",
    "forecast":    "FORECAST",
    "water_level": "SIMULATED",
    "drainage":    "PROFILE",
    "terrain":     "DERIVED",
    "history":     "PROFILE",
}

CITY = "Chennai"
CITY_LAT = 13.0827
CITY_LON = 80.2707

OPEN_METEO_BASE = "https://api.open-meteo.com/v1"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1"
CACHE_DIR = "backend/data/cache"
CACHE_TTL_SECONDS = 600

OUTPUT_LABEL = "Relative Flood Risk Index (0–100)"

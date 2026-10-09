"""
Historical replay: run the engine hour-by-hour over an archived rainfall day.
Default date 2015-12-01 (Chennai floods peak day).

Water level has NO historical record here. It is reconstructed as a SIMULATED
series: zone baseline + a leaky accumulation of the archived rainfall. This is
labelled synthetic everywhere it appears.
"""
from backend.engine.risk_engine import compute_risk, sanitize_observations
from backend.services.sensor_simulator import get_water_level, RAIN_RESPONSE_CM_PER_MM
from backend.services.weather_service import get_archive_weather

DEFAULT_DATE = "2015-12-01"
REPLAY_BANNER = (
    "HISTORICAL REPLAY — rainfall from the Open-Meteo archive (ERA5 reanalysis, city centroid). "
    "Water level is SYNTHETIC (reconstructed, no sensor existed). Indices are what the model "
    "WOULD have shown — not a validation of flood outcomes. ERA5 is a ~25 km grid average and "
    "under-represents local cloudbursts (e.g. Chennai 2015-12-01 station totals far exceeded the grid value)."
)
RECESSION = 0.85  # hour-to-hour retention of accumulated rain lift (leaky bucket)


def run(date_str: str = DEFAULT_DATE, zones: list = None, live: bool = True) -> dict:
    archive = get_archive_weather(date_str, live=live)
    hourly = [float(v or 0.0) for v in archive.get("hourly_precip_mm", [])]
    hourly = (hourly + [0.0] * 24)[:24]
    times = archive.get("hourly_times") or [f"{date_str}T{h:02d}:00" for h in range(24)]

    series = []
    for z in zones or []:
        lift = 0.0
        points = []
        for h in range(24):
            precip = hourly[h]
            window = (hourly[h + 1:h + 7] + [0.0] * 6)[:6]
            lift = lift * RECESSION + precip * RAIN_RESPONSE_CM_PER_MM
            wl = get_water_level(z["id"], 0, precip, mode="replay",
                                 replay_value=z["baseline_water_level_cm"] + lift,
                                 baseline_cm=z["baseline_water_level_cm"])
            obs, _ = sanitize_observations(
                {"precip_1h_mm": precip, "forecast_6h_mm": window, "water_level_cm": wl}, z
            )
            r = compute_risk(z, obs)
            points.append({
                "hour": h, "time": times[h] if h < len(times) else None,
                "precip_mm": round(precip, 2), "water_level_cm": wl,
                "index": r["index"], "risk_level": r["risk_level"], "top_driver": r["top_driver"],
            })
        peak = max(points, key=lambda p: p["index"])
        series.append({
            "id": z["id"], "name": z.get("name", z["id"]),
            "points": points,
            "peak_index": peak["index"], "peak_hour": peak["hour"], "peak_level": peak["risk_level"],
            "hours_at_or_above_high": sum(1 for p in points if p["risk_level"] in ("HIGH", "CRITICAL")),
        })

    return {
        "name": "Historical replay",
        "date": date_str,
        "banner": REPLAY_BANNER,
        "rainfall_source": archive.get("source"),
        "rainfall_provider": archive.get("provider"),
        "rainfall_is_synthetic": archive.get("source") == "synthetic-fallback",
        "archive_error": archive.get("error"),
        "hourly_precip_mm": hourly,
        "hourly_times": times,
        "daily_total_mm": round(sum(hourly), 1),
        "water_level_label": "SIMULATED (reconstructed)",
        "series": series,
    }

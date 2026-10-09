"""
FloodSense Alert Engine.
Maps (risk_level, top_dynamic) -> pre-authored action text.
No free-form generation. Every action carries the prototype disclaimer.
"""
import json
import os

DISCLAIMER = "Prototype recommendation — not official emergency guidance."

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "action_templates.json")

_FALLBACK = {
    "LOW":      "Conditions within normal range. No action needed; routine monitoring only.",
    "MODERATE": "Monitor conditions. Review local drain status and keep informed via IMD bulletins.",
    "HIGH":     "Elevated relative risk. Avoid low-lying roads, move vehicles to higher ground, "
                "and prepare for possible waterlogging.",
    "CRITICAL": "Very high relative risk. Avoid travel through this zone; follow instructions "
                "from Greater Chennai Corporation and NDMA/IMD advisories.",
}

_templates_cache = None


def load_templates(path: str = None) -> dict:
    """Load action_templates.json once. Falls back to in-code defaults if missing."""
    global _templates_cache
    if _templates_cache is not None and path is None:
        return _templates_cache
    p = path or _TEMPLATE_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if path is None:
        _templates_cache = data
    return data


def get_action(risk_level: str, top_dynamic: str, templates: dict = None) -> dict:
    """
    Returns {text, disclaimer, based_on}.
    Lookup order: "<LEVEL>_<top_dynamic>" -> "<LEVEL>_default" -> in-code fallback.
    """
    t = templates if templates is not None else load_templates()
    level = (risk_level or "LOW").upper()
    dyn = (top_dynamic or "rainfall").lower()

    key = f"{level}_{dyn}"
    text = t.get(key)
    source_key = key
    if text is None:
        source_key = f"{level}_default"
        text = t.get(source_key)
    if text is None:
        source_key = "fallback"
        text = _FALLBACK.get(level, _FALLBACK["LOW"])

    return {
        "text": text,
        "disclaimer": DISCLAIMER,
        "based_on": {
            "risk_level": level,
            "top_dynamic": dyn,
            "template_key": source_key,
        },
    }

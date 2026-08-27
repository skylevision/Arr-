"""Open-Meteo, serverseitig gecacht. Kein Schluessel, kein Konto.

Ersetzt den Temperaturregler des Prototypen. Der Abruf ist der einzige
Verkehr nach aussen ausser der Anthropic-API.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx2 as httpx

from .config import settings

log = logging.getLogger("rack.weather")

URL = "https://api.open-meteo.com/v1/forecast"
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def current(lat: float, lon: float) -> dict[str, Any]:
    key = f"{lat:.2f},{lon:.2f}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < settings.weather_cache_minutes * 60:
        return {**hit[1], "gecacht": True}

    try:
        r = httpx.get(URL, timeout=10.0, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,apparent_temperature,weather_code",
            "daily": "temperature_2m_min,temperature_2m_max",
            "forecast_days": 1, "timezone": "auto",
        })
        r.raise_for_status()
        data = r.json()
    except Exception as exc:                       # noqa: BLE001
        log.warning("Wetterabruf fehlgeschlagen: %s", type(exc).__name__)
        if hit:
            return {**hit[1], "gecacht": True, "veraltet": True}
        raise RuntimeError("Wetter nicht erreichbar") from None

    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    out = {
        "temp": cur.get("temperature_2m"),
        "gefuehlt": cur.get("apparent_temperature"),
        "code": cur.get("weather_code"),
        "min": (daily.get("temperature_2m_min") or [None])[0],
        "max": (daily.get("temperature_2m_max") or [None])[0],
        "zeit": cur.get("time"),
        "gecacht": False,
    }
    _cache[key] = (time.time(), out)
    return out

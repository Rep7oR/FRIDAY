"""Real current-weather lookup via Open-Meteo (https://open-meteo.com) -- free, no API key.
The browser supplies lat/lon via its own geolocation; this just proxies+caches the request
server-side so the frontend doesn't need a key or CORS workaround."""
from __future__ import annotations

import time

import httpx

_CACHE_TTL_SECONDS = 600
_cache: dict[tuple[float, float], tuple[float, dict]] = {}

# https://open-meteo.com/en/docs#weathervariables -- WMO weather interpretation codes
_WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def get_weather(lat: float, lon: float) -> dict:
    cache_key = (round(lat, 2), round(lon, 2))
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        },
        timeout=5,
    )
    response.raise_for_status()
    current = response.json().get("current", {})

    result = {
        "temperature_c": current.get("temperature_2m"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_kmh": current.get("wind_speed_10m"),
        "condition": _WEATHER_CODES.get(current.get("weather_code"), "Unknown"),
    }
    _cache[cache_key] = (time.monotonic(), result)
    return result

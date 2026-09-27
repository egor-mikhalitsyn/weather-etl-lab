"""Current location detection through an IP geolocation API."""

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

import requests

from config import Settings


logger = logging.getLogger(__name__)


class GeoLocationError(RuntimeError):
    """Raised when geolocation data cannot be loaded or parsed."""


@dataclass(frozen=True)
class Location:
    city: str
    lat: float | None = None
    lon: float | None = None


def detect_location(settings: Settings) -> Location:
    try:
        response = requests.get(settings.geo_api_url, timeout=8)
        response.raise_for_status()
        data = response.json()
        return _parse_location(data)
    except (requests.RequestException, ValueError, GeoLocationError) as error:
        logger.warning("Не удалось определить локацию автоматически: %s", error)
        if not settings.geo_api_fallback_city:
            raise GeoLocationError("Не указан GEO_API_FALLBACK_CITY") from error
        return Location(city=settings.geo_api_fallback_city)


def _parse_location(data: Any) -> Location:
    if not isinstance(data, Mapping):
        raise GeoLocationError("гео-API вернул некорректный JSON")

    city = data.get("city") or data.get("City") or data.get("cityName")
    lat: float | None = None
    lon: float | None = None

    if isinstance(data.get("loc"), str) and "," in data["loc"]:
        lat_raw, lon_raw = data["loc"].split(",", maxsplit=1)
        lat = float(lat_raw.strip())
        lon = float(lon_raw.strip())
    elif data.get("latitude") is not None and data.get("longitude") is not None:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    elif data.get("lat") is not None and data.get("lon") is not None:
        lat = float(data["lat"])
        lon = float(data["lon"])

    if not city:
        raise GeoLocationError("гео-API не вернул город")
    if lat is None or lon is None:
        raise GeoLocationError("гео-API не вернул координаты")

    return Location(city=str(city), lat=lat, lon=lon)

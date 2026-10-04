"""Определение города по IP и переход к резервной локации при сбое."""

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

import requests

from core.settings import Settings
from core.exceptions import GeoLocationError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Location:
    """Город и координаты для запроса погоды; объект неизменяемый."""

    city: str
    lat: float | None = None
    lon: float | None = None


def detect_location(settings: Settings) -> Location:
    """Определить локацию по IP; при сбое использовать резерв из настроек."""
    try:
        # Токен нужен для настройки 2ip.io; без токена работает ipinfo.
        params = {"token": settings.geo_api_key} if settings.geo_api_key else None
        response = requests.get(settings.geo_api_url, params=params, timeout=8)
        response.raise_for_status()
        data = response.json()
        return _parse_location(data)
    except (requests.RequestException, TypeError, ValueError, GeoLocationError) as error:
        logger.warning("Геолокация недоступна (%s); используем резерв", type(error).__name__)
        if not settings.geo_api_fallback_city:
            raise GeoLocationError("Не указан GEO_API_FALLBACK_CITY") from error
        return Location(
            city=settings.geo_api_fallback_city,
            lat=settings.geo_api_fallback_lat, lon=settings.geo_api_fallback_lon,
        )


def _parse_location(data: Any) -> Location:
    """Нормализовать форматы ipinfo и 2ip в единый объект Location."""
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

    if lat is not None and not -90 <= lat <= 90:
        raise GeoLocationError("Некорректная широта")
    if lon is not None and not -180 <= lon <= 180:
        raise GeoLocationError("Некорректная долгота")

    if not city:
        raise GeoLocationError("гео-API не вернул город")
    if lat is None or lon is None:
        raise GeoLocationError("гео-API не вернул координаты")

    return Location(city=str(city), lat=lat, lon=lon)

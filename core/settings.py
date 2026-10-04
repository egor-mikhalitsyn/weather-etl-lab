"""Загрузка настроек из .env и окружения без запросов к API и БД."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

# .env и относительные файлы ищем в проекте, а не в каталоге терминала.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """Неизменяемая конфигурация, явно передаваемая модулям."""

    weather_api_key: str
    weather_api_base_url: str
    geo_api_url: str
    geo_api_fallback_city: str
    db_url: str
    db_user: str
    db_password: str
    environment: str
    output_file: str
    geo_api_key: str = ""
    geo_api_fallback_lat: float | None = None
    geo_api_fallback_lon: float | None = None
    output_dir: str = "data_weather"
    log_level: str = "INFO"
    log_dir: str = "log"


def project_path(value: str) -> Path:
    """Разрешить относительный путь от корня 1LAB; абсолютный оставить как есть."""
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_settings() -> Settings:
    """Прочитать настройки при запуске; окружение приоритетнее .env."""
    load_dotenv(PROJECT_ROOT / ".env")
    lat_raw = os.getenv("GEO_API_FALLBACK_LAT", "").strip()
    lon_raw = os.getenv("GEO_API_FALLBACK_LON", "").strip()
    lat = float(lat_raw) if lat_raw else None
    lon = float(lon_raw) if lon_raw else None
    if (lat is None) != (lon is None):
        raise ValueError("Резервные широта и долгота должны быть заданы вместе")
    if lat is not None and not -90 <= lat <= 90:
        raise ValueError("GEO_API_FALLBACK_LAT должен быть от -90 до 90")
    if lon is not None and not -180 <= lon <= 180:
        raise ValueError("GEO_API_FALLBACK_LON должен быть от -180 до 180")
    return Settings(
        weather_api_key=os.getenv("WEATHER_API_KEY", ""),
        weather_api_base_url=os.getenv(
            "WEATHER_API_BASE_URL", "https://api.openweathermap.org/data/2.5"
        ).rstrip("/"),
        geo_api_url=os.getenv("GEO_API_URL", "https://ipinfo.io/json"),
        geo_api_fallback_city=os.getenv("GEO_API_FALLBACK_CITY", "Kirov"),
        db_url=os.getenv("DB_URL", "sqlite:///weather_lab.db"),
        # SQLite не использует логин и пароль; поля сохранены по образцу задания.
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        environment=os.getenv("ENVIRONMENT", "development"),
        output_file=os.getenv("OUTPUT_FILE", "weather_report.md"),
        geo_api_key=os.getenv("GEO_API_KEY", ""),
        geo_api_fallback_lat=lat,
        geo_api_fallback_lon=lon,
        output_dir=os.getenv("OUTPUT_DIR", "data_weather"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_dir=os.getenv("LOG_DIR", "log"),
    )

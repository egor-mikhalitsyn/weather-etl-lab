"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    weather_api_key: str
    weather_api_base_url: str
    geo_api_url: str
    geo_api_fallback_city: str
    db_url: str
    db_user: str
    db_password: str
    environment: str
    output_file: str


def get_settings() -> Settings:
    return Settings(
        weather_api_key=os.getenv("WEATHER_API_KEY", ""),
        weather_api_base_url=os.getenv(
            "WEATHER_API_BASE_URL", "https://api.openweathermap.org/data/2.5"
        ).rstrip("/"),
        geo_api_url=os.getenv("GEO_API_URL", "https://ipinfo.io/json"),
        geo_api_fallback_city=os.getenv("GEO_API_FALLBACK_CITY", "Kirov"),
        db_url=os.getenv("DB_URL", "sqlite:///weather_lab.db"),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        environment=os.getenv("ENVIRONMENT", "development"),
        output_file=os.getenv("OUTPUT_FILE", "weather_report.md"),
    )

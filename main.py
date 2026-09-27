"""Run the weather ETL pipeline."""

import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from config import get_settings
from db_models import create_session_factory, get_forecasts_for_city, save_forecasts
from exporter import export_to_markdown
from geo_locator import GeoLocationError, detect_location
from weather_client import WeatherApiError, aggregate_daily_forecast, fetch_forecast


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    setup_logging()
    settings = get_settings()

    try:
        session_factory = create_session_factory(settings)
    except SQLAlchemyError as error:
        logging.error("Не удалось подключиться к базе данных: %s", error)
        return 1

    try:
        location = detect_location(settings)
    except GeoLocationError as error:
        logging.error("Не удалось определить местоположение: %s", error)
        return 1
    logging.info("Город: %s", location.city)
    if location.lat is not None and location.lon is not None:
        logging.info("Координаты: %.4f, %.4f", location.lat, location.lon)
    else:
        logging.info("Координаты не получены, прогноз будет запрошен по городу")

    try:
        raw_forecast = fetch_forecast(settings, location)
        daily_forecasts = aggregate_daily_forecast(raw_forecast)
    except WeatherApiError as error:
        logging.error("Не удалось получить прогноз: %s", error)
        return 1

    try:
        inserted_count = save_forecasts(session_factory, location.city, daily_forecasts)
        saved_forecasts = get_forecasts_for_city(session_factory, location.city)
    except SQLAlchemyError as error:
        logging.error("Ошибка при работе с базой данных: %s", error)
        return 1

    report_dates = {item.forecast_date for item in daily_forecasts}
    report_forecasts = [
        item for item in saved_forecasts if item.forecast_date in report_dates
    ]
    try:
        output_path = export_to_markdown(
            location.city, report_forecasts, settings.output_file
        )
    except (OSError, ValueError) as error:
        logging.error("Не удалось создать Markdown-отчёт: %s", error)
        return 1

    logging.info(
        "Даты прогноза: %s - %s",
        daily_forecasts[0].forecast_date,
        daily_forecasts[-1].forecast_date,
    )
    logging.info("Новых записей сохранено: %s", inserted_count)
    logging.info("Всего строк для города в БД: %s", len(saved_forecasts))
    logging.info("Markdown-отчёт: %s", output_path.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())

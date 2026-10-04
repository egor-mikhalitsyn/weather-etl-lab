"""Точка входа: последовательно запустить ETL и вывести результаты работы."""

import logging
import sys

from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import GeoLocationError, WeatherApiError
from core.logger import setup_logging
from core.settings import get_settings, project_path
from db_models import create_session_factory, get_full_db, save_forecasts
from exporter import export_all_to_markdown, export_to_markdown
from geo_locator import detect_location
from weather_client import aggregate_daily_forecast, fetch_forecast


def main() -> int:
    """Координировать модули; вернуть 0 при успехе и 1 при ожидаемой ошибке."""
    session_factory = None
    try:
        settings = get_settings()
        setup_logging(settings)
        session_factory = create_session_factory(settings)

        # Extract: определить локацию и получить исходные точки погодного API.
        location = detect_location(settings)
        logging.info("Город: %s; координаты: %s, %s", location.city, location.lat, location.lon)
        raw_forecast = fetch_forecast(settings, location)

        # Transform: чистая функция сводит трёхчасовые точки к четырём местным датам.
        daily_forecasts = aggregate_daily_forecast(raw_forecast)

        # Load: сохранить новые или изменившиеся данные и прочитать их из БД.
        inserted, updated = save_forecasts(session_factory, location.city, daily_forecasts)
        forecasts = get_full_db(session_factory)
        # Основной отчёт содержит только текущий город и нужные четыре даты.
        report_dates = {item.forecast_date for item in daily_forecasts}
        current_forecasts = [item for item in forecasts
                             if item.city == location.city and item.forecast_date in report_dates]
        output_path = export_to_markdown(
            location.city, current_forecasts, project_path(settings.output_file),
        )
        logging.info(
            "Основной отчёт | Даты: %s - %s | Записей: %s | Файл: %s",
            daily_forecasts[0].forecast_date, daily_forecasts[-1].forecast_date,
            len(current_forecasts), output_path.resolve(),
        )
        # Дополнительные файлы содержат накопленную историю каждого города.
        reports = export_all_to_markdown(
            forecasts, project_path(settings.output_dir), settings.output_file,
        )
        logging.info("Новых записей: %s; обновлено: %s", inserted, updated)
        logging.info("ОТЧЁТ О РАБОТЕ: все города из БД")
        for report in reports:
            logging.info(
                "Город: %s | Даты: %s - %s | Записей: %s | Файл: %s",
                report.city, report.start_date, report.end_date,
                report.records_count, report.file_path.resolve(),
            )
        return 0
    except (GeoLocationError, WeatherApiError, SQLAlchemyError, OSError, ValueError) as error:
        # Не выводим текст исключений HTTP/SQL: он может содержать секреты или параметры.
        message = str(error) if isinstance(error, (GeoLocationError, WeatherApiError)) else type(error).__name__
        logging.error("Не удалось выполнить ETL: %s", message)
        return 1
    finally:
        # Закрываем соединения и при успехе, и при ошибке любого этапа.
        if session_factory is not None:
            session_factory.kw["bind"].dispose()


if __name__ == "__main__":
    sys.exit(main())

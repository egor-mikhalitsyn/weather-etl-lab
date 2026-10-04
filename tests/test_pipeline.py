"""Проверки расчётов, повторного запуска и ошибок без сети и рабочей БД."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from core.exceptions import WeatherApiError
from core.settings import Settings, get_settings
from db_models import create_session_factory, get_full_db, save_forecasts
from exporter import export_all_to_markdown
from geo_locator import Location, _parse_location, detect_location
from main import main
from weather_client import aggregate_daily_forecast, fetch_forecast


def sample_forecast() -> dict:
    """UTC-точки пересекают местную полночь, проверяя правильные границы суток."""
    start = datetime(2026, 9, 27, 21, tzinfo=UTC)
    points = []
    for i in range(40):
        points.append({
            "dt": int((start + timedelta(hours=3 * i)).timestamp()),
            "main": {"temp_min": 1.23 + i, "temp_max": 5.67 + i, "humidity": 50 + i % 8},
            "wind": {"speed": 2.34 + i / 10},
            "weather": [{"description": f"weather {i}"}],
        })
    return {"city": {"timezone": 10800}, "list": points}


class PipelineTests(unittest.TestCase):
    """Каждый тест использует отдельную временную БД и каталог отчётов."""

    def setUp(self) -> None:
        """Создать изолированное окружение, не меняя .env и weather_lab.db."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = Settings(
            weather_api_key="test-key", weather_api_base_url="https://weather.invalid",
            geo_api_url="https://geo.invalid", geo_api_fallback_city="Kirov",
            db_url="sqlite:///:memory:", db_user="", db_password="",
            environment="test", output_file="weather_report.md",
            output_dir=str(self.root / "reports"), log_dir=str(self.root / "logs"),
            geo_api_fallback_lat=58.6035, geo_api_fallback_lon=49.6679,
        )
        self.factory = create_session_factory(self.settings)
        self.addCleanup(self.factory.kw["bind"].dispose)

    def test_local_dates_and_exact_daily_values(self) -> None:
        """Сдвиг даты, четыре дня, экстремумы, влажность и полуденное описание."""
        result = aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 28))
        self.assertEqual([item.forecast_date for item in result],
                         [date(2026, 9, 28), date(2026, 9, 29),
                                        date(2026, 9, 30), date(2026, 10, 1)])
        self.assertEqual(result[0].temp_min, 1.23)
        self.assertEqual(result[0].temp_max, 12.67)
        self.assertAlmostEqual(result[0].wind_speed, 3.04)
        self.assertEqual(result[0].humidity, 54)
        self.assertEqual(result[0].description, "Weather 4")

    def test_bad_forecast_is_application_error(self) -> None:
        """Некорректный JSON и недостаточное число дней обрабатываются явно."""
        for data in ({"list": []}, {"city": None, "list": []},
                     {"list": [{"dt": "invalid"}]},
                     {"list": [sample_forecast()["list"][0]]}):
            with self.subTest(data=data), self.assertRaises(WeatherApiError):
                aggregate_daily_forecast(data, today=date(2026, 9, 28))

    def test_repeated_run_updates_without_duplicates(self) -> None:
        """Новый прогноз для той же даты должен заменить старые показатели."""
        data = aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 28))
        self.assertEqual(save_forecasts(self.factory, "Kirov", data), (4, 0))
        changed = [replace(item, temp_min=-10.12) for item in data]
        self.assertEqual(save_forecasts(self.factory, "Kirov", changed), (0, 4))
        rows = get_full_db(self.factory)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(item.temp_min == -10.12 for item in rows))

    def test_failed_batch_rolls_back(self) -> None:
        """Ошибка второй записи не должна оставлять первую запись в БД."""
        data = aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 28))
        with self.assertRaises(IntegrityError):
            save_forecasts(self.factory, "Kirov", [data[0], replace(data[1], description=None)])
        self.assertEqual(get_full_db(self.factory), [])

    def test_export_all_cities_and_safe_filenames(self) -> None:
        """Отдельные города получают разные файлы даже при совпадении очищенных имён."""
        data = aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 28))
        for city in ("Kirov", "A/B", "A?B"):
            save_forecasts(self.factory, city, data)
        reports = export_all_to_markdown(get_full_db(self.factory), self.root / "reports")
        self.assertEqual(len(reports), 3)
        self.assertEqual(len({report.file_path for report in reports}), 3)
        for report in reports:
            self.assertEqual(report.records_count, 4)
            self.assertEqual(report.file_path.parent, self.root / "reports")
            content = report.file_path.read_text(encoding="utf-8")
            self.assertIn("1.23", content)
            self.assertIn("2026-09-28", content)

    def test_geo_response_formats(self) -> None:
        """Одинаково понимаем координаты ipinfo и 2ip."""
        self.assertEqual(_parse_location({"city": "Kirov", "loc": "58.6,49.6"}),
                         Location("Kirov", 58.6, 49.6))
        self.assertEqual(_parse_location({"city": "Kirov", "lat": 58.6, "lon": 49.6}),
                         Location("Kirov", 58.6, 49.6))

    def test_target_dates_start_today_not_first_available_day(self) -> None:
        """Более ранняя дата в ответе не должна сдвигать требуемый период."""
        result = aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 29))
        self.assertEqual([item.forecast_date for item in result],
                         [date(2026, 9, 29), date(2026, 9, 30),
                          date(2026, 10, 1), date(2026, 10, 2)])

    def test_missing_today_is_not_replaced_by_tomorrow(self) -> None:
        """При отсутствии сегодня API не должен незаметно подставлять другой период."""
        with self.assertRaisesRegex(WeatherApiError, "2026-09-27"):
            aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 27))

    @patch("weather_client.datetime", wraps=datetime)
    def test_default_today_uses_city_timezone(self, clock: Mock) -> None:
        """Дата по умолчанию определяется в часовом поясе из ответа API."""
        clock.now.return_value = datetime(2026, 9, 28, tzinfo=UTC)
        result = aggregate_daily_forecast(sample_forecast())
        self.assertEqual(result[0].forecast_date, date(2026, 9, 28))
        self.assertEqual(clock.now.call_args.args[0].utcoffset(None), timedelta(hours=3))

    def test_identical_records_are_not_rewritten(self) -> None:
        """Повтор одинакового пакета не меняет время записи и не создаёт дублей."""
        data = aggregate_daily_forecast(sample_forecast(), today=date(2026, 9, 28))
        save_forecasts(self.factory, "Kirov", data)
        timestamps = [item.created_at for item in get_full_db(self.factory)]
        self.assertEqual(save_forecasts(self.factory, "Kirov", data), (0, 0))
        self.assertEqual([item.created_at for item in get_full_db(self.factory)], timestamps)

    @patch("geo_locator.requests.get")
    def test_geo_limit_and_malformed_response_use_fallback(self, request: Mock) -> None:
        """Лимит и некорректные координаты обрабатываются резервной локацией."""
        request.return_value.raise_for_status.side_effect = requests.HTTPError("429")
        self.assertEqual(detect_location(self.settings).city, "Kirov")
        request.return_value.raise_for_status.side_effect = None
        request.return_value.json.return_value = {"city": "Other", "lat": [], "lon": 1}
        self.assertEqual(detect_location(self.settings).city, "Kirov")

    @patch("weather_client.requests.get")
    def test_weather_network_errors(self, request: Mock) -> None:
        """Таймаут и отсутствие соединения преобразуются в ошибку погодного API."""
        for error in (requests.Timeout(), requests.ConnectionError()):
            request.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(WeatherApiError):
                fetch_forecast(self.settings, Location("Kirov"))
    @patch("geo_locator.requests.get", side_effect=requests.Timeout)
    def test_geo_fallback_uses_coordinates(self, request: Mock) -> None:
        """При сбое геосервиса получаем резервный город и его координаты."""
        self.assertEqual(detect_location(self.settings), Location("Kirov", 58.6035, 49.6679))

    @patch("weather_client.requests.get")
    def test_weather_errors_and_coordinate_request(self, request: Mock) -> None:
        """Специальные HTTP-коды и повреждённый JSON не проходят в агрегацию."""
        for status in (401, 404, 429):
            request.return_value = Mock(status_code=status)
            request.return_value.json.return_value = {"cod": str(status)}
            with self.subTest(status=status), self.assertRaises(WeatherApiError):
                fetch_forecast(self.settings, Location("Kirov", 58.6, 49.6))
        self.assertEqual(request.call_args.kwargs["params"]["lat"], 58.6)
        request.return_value = Mock(status_code=200)
        request.return_value.json.side_effect = ValueError("not JSON")
        with self.assertRaises(WeatherApiError):
            fetch_forecast(self.settings, Location("Kirov"))

    def test_missing_key_does_not_make_request(self) -> None:
        """Не обращаться к API, если пользователь ещё не настроил ключ."""
        with patch("weather_client.requests.get") as request, self.assertRaises(WeatherApiError):
            fetch_forecast(replace(self.settings, weather_api_key=""), Location("Kirov"))
        request.assert_not_called()

    def test_partial_fallback_coordinates_rejected(self) -> None:
        """Половина пары координат считается ошибкой настроек."""
        with patch("core.settings.load_dotenv"), patch.dict(
            "os.environ", {"GEO_API_FALLBACK_LAT": "58.6", "GEO_API_FALLBACK_LON": ""},
        ), self.assertRaises(ValueError):
            get_settings()

    def test_main_runs_twice_with_real_database_and_reports(self) -> None:
        """Весь сценарий использует настоящий SQLite и файлы, заменяется только сеть."""
        settings = replace(self.settings, db_url=f"sqlite:///{self.root / 'test.db'}",
                           output_file=str(self.root / "weather_report.md"))
        with patch("main.get_settings", return_value=settings), patch(
            "main.detect_location", return_value=Location("Kirov", 58.6, 49.6),
        ), patch("main.fetch_forecast", return_value=sample_forecast()), patch(
            "main.aggregate_daily_forecast",
            side_effect=lambda data: aggregate_daily_forecast(data, today=date(2026, 9, 28)),
        ):
            try:
                self.assertEqual(main(), 0)
                self.assertEqual(main(), 0)
            finally:
                # Закрыть файловый лог перед удалением временной папки на Windows.
                for handler in logging.getLogger().handlers[:]:
                    handler.close()
                    logging.getLogger().removeHandler(handler)
        factory = create_session_factory(settings)
        self.addCleanup(factory.kw["bind"].dispose)
        self.assertEqual(len(get_full_db(factory)), 4)
        self.assertTrue((self.root / "reports/weather_report_kirov.md").exists())
        self.assertTrue((self.root / "logs/app.log").exists())
        primary = (self.root / "weather_report.md").read_text(encoding="utf-8")
        self.assertIn("Суточный прогноз", primary)
        self.assertIn("2026-09-28 – 2026-10-01", primary)

    def test_main_handles_database_error(self) -> None:
        """Ошибка БД даёт ненулевой код завершения вместо необработанного падения."""
        with patch("main.get_settings", return_value=self.settings), patch(
            "main.setup_logging",
        ), patch("main.create_session_factory", side_effect=SQLAlchemyError("failure")):
            with self.assertLogs(level="ERROR"):
                self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()

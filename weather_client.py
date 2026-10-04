"""Получение прогноза OpenWeatherMap и расчёт суточных показателей."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import requests

from core.settings import Settings
from core.exceptions import WeatherApiError
from geo_locator import Location


@dataclass(frozen=True)
class DailyForecast:
    """Суточная сводка для сохранения в БД после обработки точек API."""

    forecast_date: date
    temp_min: float
    temp_max: float
    humidity: int
    wind_speed: float
    description: str


def fetch_forecast(settings: Settings, location: Location) -> dict[str, Any]:
    """Запросить прогноз с таймаутом и обработать ошибки API."""
    if not settings.weather_api_key:
        raise WeatherApiError("Не задан WEATHER_API_KEY")

    # requests экранирует параметры; метрическая система даёт °C и м/с.
    params: dict[str, Any] = {
        "appid": settings.weather_api_key,
        "units": "metric",
        "lang": "ru",
    }
    if location.lat is not None and location.lon is not None:
        params["lat"] = location.lat
        params["lon"] = location.lon
    else:
        params["q"] = location.city

    url = f"{settings.weather_api_base_url}/forecast"
    try:
        response = requests.get(url, params=params, timeout=10)
        try:
            data = response.json()
        except ValueError as error:
            raise WeatherApiError("OpenWeatherMap вернул не JSON") from error

        if not isinstance(data, dict):
            raise WeatherApiError("OpenWeatherMap вернул некорректный JSON")

        code = str(data.get("cod", response.status_code))
        if response.status_code == 401 or code == "401":
            raise WeatherApiError("Неверный API-ключ OpenWeatherMap")
        if response.status_code == 404 or code == "404":
            raise WeatherApiError("Город не найден в OpenWeatherMap")
        if response.status_code == 429 or code == "429":
            raise WeatherApiError("Превышен лимит запросов OpenWeatherMap")

        response.raise_for_status()
        if not isinstance(data.get("list"), list):
            raise WeatherApiError("В ответе OpenWeatherMap нет списка прогноза")
        return data
    except requests.Timeout as error:
        raise WeatherApiError("OpenWeatherMap не ответил вовремя") from error
    except requests.ConnectionError as error:
        raise WeatherApiError("Нет соединения с OpenWeatherMap") from error
    except requests.RequestException as error:
        raise WeatherApiError("Ошибка HTTP-запроса OpenWeatherMap") from error


def aggregate_daily_forecast(
    raw_data: dict[str, Any], today: date | None = None,
) -> list[DailyForecast]:
    """Рассчитать сегодня и три следующих дня по местному времени города."""
    try:
        timezone_shift = int(raw_data.get("city", {}).get("timezone", 0))
        api_tz = timezone(timedelta(seconds=timezone_shift))
        points_by_day: dict[date, list[dict[str, Any]]] = {}

        # Перевод из UTC нужен, чтобы даты соответствовали часовому поясу города.
        for point in raw_data["list"]:
            local_dt = datetime.fromtimestamp(int(point["dt"]), tz=UTC).astimezone(api_tz)
            points_by_day.setdefault(local_dt.date(), []).append(point)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, OSError) as error:
        raise WeatherApiError("Некорректные данные прогноза OpenWeatherMap") from error

    if not points_by_day:
        raise WeatherApiError("OpenWeatherMap вернул пустой прогноз")

    # Параметр today позволяет проверять расчёт независимо от даты запуска тестов.
    local_today = today if today is not None else datetime.now(api_tz).date()
    target_dates = [local_today + timedelta(days=offset) for offset in range(4)]
    missing_dates = [day for day in target_dates if day not in points_by_day]
    if missing_dates:
        dates = ", ".join(str(day) for day in missing_dates)
        raise WeatherApiError(f"В ответе API нет прогнозных точек на даты: {dates}")

    result: list[DailyForecast] = []
    for day in target_dates:
        points = points_by_day[day]
        try:
            descriptions = [
                str(point["weather"][0]["description"]).capitalize()
                for point in points
                if point.get("weather")
            ]
            if not descriptions:
                raise KeyError("weather.description")

            # Берём описание ближайшей к полудню точки, а не ночной погоды.
            noon_points = [point for point in points if point.get("weather")]
            noon_point = min(
                noon_points,
                key=lambda point: abs(
                    datetime.fromtimestamp(int(point["dt"]), tz=UTC)
                    .astimezone(api_tz)
                    .hour
                    - 12
                ),
            )
            noon_description = str(
                noon_point["weather"][0]["description"]
            ).capitalize()
            description = noon_description or Counter(descriptions).most_common(1)[0][0]

            result.append(
                DailyForecast(
                    forecast_date=day,
                    temp_min=min(float(p["main"]["temp_min"]) for p in points),
                    temp_max=max(float(p["main"]["temp_max"]) for p in points),
                    humidity=round(
                        sum(int(p["main"]["humidity"]) for p in points) / len(points)
                    ),
                    wind_speed=max(float(p["wind"]["speed"]) for p in points),
                    description=description,
                )
            )
        except (AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError, OSError) as error:
            raise WeatherApiError(
                f"Некорректные данные прогноза за {day}"
            ) from error

    return result

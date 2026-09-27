"""Markdown report export."""

from pathlib import Path
from typing import Sequence

from db_models import WeatherForecast


def export_to_markdown(
    city: str, forecasts: Sequence[WeatherForecast], output_file: str
) -> Path:
    if not forecasts:
        raise ValueError("Нет данных для экспорта")

    path = Path(output_file)
    start_date = forecasts[0].forecast_date
    end_date = forecasts[-1].forecast_date

    lines = [
        "# Прогноз погоды",
        "",
        "Дневной прогноз, автоматически полученный и обработанный из OpenWeatherMap.",
        "",
        f"Автоматически определённая локация: {city}  ",
        f"Период: {start_date} - {end_date}  ",
        "",
        "| Дата | Мин. темп. (°C) | Макс. темп. (°C) | Описание | Влажность (%) | Ветер (м/с) |",
        "|---|---:|---:|---|---:|---:|",
    ]

    for item in forecasts:
        lines.append(
            "| "
            f"{item.forecast_date} | "
            f"{item.temp_min:g} | "
            f"{item.temp_max:g} | "
            f"{item.description} | "
            f"{item.humidity} | "
            f"{item.wind_speed:g} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

"""Экспорт сохранённых прогнозов: отдельная Markdown-таблица для каждого города."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from db_models import WeatherForecast


@dataclass(frozen=True)
class ExportResult:
    """Метаданные отчёта для итогового сообщения в журнале."""

    city: str
    start_date: date
    end_date: date
    records_count: int
    file_path: Path


def _escape_cell(value: str) -> str:
    """Убрать переносы и экранировать вертикальную черту, чтобы сохранить таблицу."""
    return value.replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def _format_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Выровнять колонки для чтения Markdown как исходного текста."""
    widths = [max(len(header), *(len(row[i]) for row in rows))
              for i, header in enumerate(headers)]
    def format_row(row: list[str]) -> str:
        """Собрать одну строку с одинаковой шириной каждой колонки."""
        return "| " + " | ".join(value.ljust(widths[i]) for i, value in enumerate(row)) + " |"
    separator = "| " + " | ".join("-" * max(3, width) for width in widths) + " |"
    return "\n".join([format_row(headers), separator, *(format_row(row) for row in rows)])


def export_to_markdown(
    city: str, forecasts: Sequence[WeatherForecast], output_file: str | Path,
) -> Path:
    """Записать упорядоченный прогноз одного города в указанный Markdown-файл."""
    if not forecasts:
        raise ValueError("Нет данных для экспорта")
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(forecasts, key=lambda item: item.forecast_date)
    headers = ["Дата", "Мин. темп. (°C)", "Макс. темп. (°C)",
               "Описание", "Влажность (%)", "Ветер (м/с)"]
    rows = [[str(item.forecast_date), f"{item.temp_min:g}", f"{item.temp_max:g}",
             _escape_cell(item.description), str(item.humidity), f"{item.wind_speed:g}"]
            for item in ordered]
    content = (
        "# Прогноз погоды\n"
        "\nСуточный прогноз из OpenWeatherMap, агрегированный из трёхчасовых интервалов.\n\n"
        f"Автоматически определённая локация: {_escape_cell(city)}  \n"
        f"Период: {ordered[0].forecast_date} – {ordered[-1].forecast_date}  \n\n"
        f"{_format_markdown_table(headers, rows)}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def export_all_to_markdown(
    forecasts: Sequence[WeatherForecast], output_dir: str | Path,
    output_file: str = "weather_report.md",
) -> list[ExportResult]:
    """Сгруппировать все строки БД по городам и вернуть результаты экспорта."""
    grouped: dict[str, list[WeatherForecast]] = defaultdict(list)
    for forecast in forecasts:
        grouped[forecast.city].append(forecast)
    # Для отчётов по городам добавляем к основе имени безопасный суффикс.
    prefix = Path(output_file).stem or "weather_report"
    results = []
    used_names: set[str] = set()
    for city in sorted(grouped):
        ordered = sorted(grouped[city], key=lambda item: item.forecast_date)
        safe_city = "".join(c if c.isalnum() or c in "-_" else "_" for c in city)
        safe_city = safe_city.strip("_").lower() or "city"
        # Разные названия могут совпасть после очистки или приведения к нижнему регистру.
        if safe_city in used_names:
            safe_city += "_" + sha256(city.encode("utf-8")).hexdigest()[:8]
        used_names.add(safe_city)
        path = export_to_markdown(city, ordered, Path(output_dir) / f"{prefix}_{safe_city}.md")
        results.append(ExportResult(
            city, ordered[0].forecast_date, ordered[-1].forecast_date, len(ordered), path,
        ))
    return results

"""Общий журнал работы: консоль и файл с ограничением размера."""

import logging
from logging.handlers import RotatingFileHandler

from core.settings import Settings, project_path


def setup_logging(settings: Settings) -> None:
    """Настроить журнал в точке входа, не создавая файлов при импорте модулей."""
    log_dir = project_path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    # Основной файл и три резервных ограничивают общий объём журнала.
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=10 * 1024 * 1024,
        backupCount=3, encoding="utf-8",
    )
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(), file_handler], force=True,
    )

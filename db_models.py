"""ORM-модель и операции БД: создание, вставка, обновление и чтение."""

from datetime import UTC, date, datetime
from typing import Iterable

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from core.settings import Settings, project_path
from weather_client import DailyForecast


class Base(DeclarativeBase):
    """Реестр ORM-моделей, по которому SQLAlchemy создаёт таблицы."""


class WeatherForecast(Base):
    """Суточная запись; город и дата уникальны на уровне БД."""

    __tablename__ = "weather_forecast"
    __table_args__ = (UniqueConstraint("city", "forecast_date", name="uq_city_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    temp_min: Mapped[float] = mapped_column(Float, nullable=False)
    temp_max: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[int] = mapped_column(Integer, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    # Функция вычисляет время для каждой записи, а не один раз при импорте.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Подключить БД и создать отсутствующие таблицы, сохраняя старые данные."""
    url = make_url(settings.db_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        database_path = project_path(url.database)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        url = url.set(database=str(database_path))
    engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    # Значения остаются доступны для экспорта после закрытия сессии.
    return sessionmaker(bind=engine, expire_on_commit=False)


def save_forecasts(
    session_factory: sessionmaker[Session], city: str, forecasts: Iterable[DailyForecast],
) -> tuple[int, int]:
    """Сохранить пакет транзакцией; вернуть число вставок и обновлений."""
    inserted = updated = 0
    # begin автоматически откатывает всю транзакцию при исключении.
    with session_factory.begin() as session:
        for forecast in forecasts:
            existing = session.scalar(
                select(WeatherForecast).where(
                    WeatherForecast.city == city,
                    WeatherForecast.forecast_date == forecast.forecast_date,
                )
            )
            if existing is None:
                existing = WeatherForecast(city=city, forecast_date=forecast.forecast_date)
                session.add(existing)
                inserted += 1
            else:
                # Если показатели не изменились, сохраняем запись и её время как есть.
                fields = ("temp_min", "temp_max", "humidity", "wind_speed", "description")
                if all(getattr(existing, field) == getattr(forecast, field) for field in fields):
                    continue
                updated += 1
            # Перезапись необходима только при изменении самого прогноза.
            existing.temp_min = forecast.temp_min
            existing.temp_max = forecast.temp_max
            existing.humidity = forecast.humidity
            existing.wind_speed = forecast.wind_speed
            existing.description = forecast.description
            existing.created_at = datetime.now(UTC)
    return inserted, updated


def get_full_db(session_factory: sessionmaker[Session]) -> list[WeatherForecast]:
    """Прочитать все города для отдельных отчётов, упорядоченных по датам."""
    with session_factory() as session:
        return list(session.scalars(
            select(WeatherForecast).order_by(WeatherForecast.city, WeatherForecast.forecast_date)
        ))

"""SQLAlchemy models and persistence helpers."""

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from config import Settings
from weather_client import DailyForecast


class Base(DeclarativeBase):
    pass


class WeatherForecast(Base):
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine(settings.db_url, echo=False, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def save_forecasts(
    session_factory: sessionmaker[Session],
    city: str,
    forecasts: Iterable[DailyForecast],
) -> int:
    inserted = 0
    with session_factory() as session:
        for forecast in forecasts:
            # The city/date pair is unique, so repeated launches do not create copies.
            exists = session.scalar(
                select(WeatherForecast).where(
                    WeatherForecast.city == city,
                    WeatherForecast.forecast_date == forecast.forecast_date,
                )
            )
            if exists:
                continue

            session.add(
                WeatherForecast(
                    city=city,
                    forecast_date=forecast.forecast_date,
                    temp_min=forecast.temp_min,
                    temp_max=forecast.temp_max,
                    humidity=forecast.humidity,
                    wind_speed=forecast.wind_speed,
                    description=forecast.description,
                )
            )
            inserted += 1
        session.commit()
    return inserted


def get_forecasts_for_city(
    session_factory: sessionmaker[Session], city: str
) -> list[WeatherForecast]:
    with session_factory() as session:
        return list(
            session.scalars(
                select(WeatherForecast)
                .where(WeatherForecast.city == city)
                .order_by(WeatherForecast.forecast_date)
            )
        )

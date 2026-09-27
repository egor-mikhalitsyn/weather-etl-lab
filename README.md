# Лабораторная работа: Weather ETL

Проект получает прогноз погоды через OpenWeatherMap, автоматически определяет город по IP, агрегирует 3-часовые точки прогноза в дневные сводки, сохраняет результат в SQLite через SQLAlchemy и выгружает аккуратный Markdown-отчёт.

## Технологии

- Python 3.10+
- requests
- SQLAlchemy 2.x
- python-dotenv
- SQLite
- OpenWeatherMap Forecast API
- IP Geolocation API, по умолчанию `https://ipinfo.io/json`

## Установка

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd weather-etl-lab
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка

Создайте `.env` на основе `.env.example`:

```bash
copy .env.example .env
```

Зарегистрируйтесь на [openweathermap.org](https://openweathermap.org/api), получите бесплатный API-ключ и заполните:

```env
WEATHER_API_KEY=your_real_key
WEATHER_API_BASE_URL=https://api.openweathermap.org/data/2.5
GEO_API_URL=https://ipinfo.io/json
GEO_API_FALLBACK_CITY=Kirov
DB_URL=sqlite:///weather_lab.db
DB_USER=unused_for_sqlite
DB_PASSWORD=unused_for_sqlite
ENVIRONMENT=development
OUTPUT_FILE=weather_report.md
```

`DB_USER` и `DB_PASSWORD` оставлены в конфигурации согласно заданию, но SQLite их не использует: путь к локальной базе задаётся целиком через `DB_URL`.

Файл `.env`, база данных и итоговый Markdown-отчёт добавлены в `.gitignore` и не должны попадать в репозиторий.

## Запуск

```bash
python main.py
```

Программа выведет в консоль город, координаты, период прогноза, количество новых записей, число строк отчёта и путь к Markdown-файлу.

## Структура

- `main.py` — последовательный запуск ETL-процесса.
- `config.py` — чтение переменных окружения из `.env`.
- `geo_locator.py` — определение города и координат через IP Geolocation API.
- `weather_client.py` — запрос к OpenWeatherMap и агрегация прогноза по дням.
- `db_models.py` — модель `weather_forecast`, создание таблицы и сохранение без дублей.
- `exporter.py` — выгрузка данных из БД в Markdown.
- `.env.example` — шаблон конфигурации без настоящих секретов.
- `.gitignore` — исключения для `.env`, БД, отчётов, кэшей и виртуальных окружений.

## Пример отчёта

```markdown
# Прогноз погоды

Автоматически определённая локация: Kirov  
Период: 2026-09-27 - 2026-09-30  

| Дата | Мин. темп. (°C) | Макс. темп. (°C) | Описание | Влажность (%) | Ветер (м/с) |
|---|---:|---:|---|---:|---:|
| 2026-09-27 | 8 | 14 | Облачно | 75 | 4 |
| 2026-09-28 | 6 | 13 | Дождь | 85 | 5 |
```

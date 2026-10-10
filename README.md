# Прогноз погоды

Лабораторная работа по Python. Программа определяет город по IP, получает
прогноз из OpenWeatherMap на сегодня и три следующих дня, сохраняет его
в SQLite и создаёт отчёт в Markdown.

## Что используется

- Python 3.11 или новее
- `requests` — запросы к API
- `SQLAlchemy` — работа с SQLite
- `python-dotenv` — чтение настроек из `.env`
- ipinfo.io — определение города и координат
- OpenWeatherMap — прогноз погоды

## Установка

Команды для PowerShell:

```powershell
git clone https://github.com/egor-mikhalitsyn/weather-etl-lab.git
cd weather-etl-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Настройка

Зарегистрируйтесь на [OpenWeatherMap](https://openweathermap.org/) и получите
бесплатный API-ключ в личном кабинете для сервиса «5 Day / 3 Hour Forecast».

Создайте `.env` из шаблона:

```powershell
Copy-Item .env.example .env
```

Если `.env` уже есть, просто отредактируйте его. Пример настроек:

```dotenv
WEATHER_API_KEY=your_api_key
WEATHER_API_BASE_URL=https://api.openweathermap.org/data/2.5
GEO_API_URL=https://ipinfo.io/json
GEO_API_FALLBACK_CITY=Kirov
GEO_API_FALLBACK_LAT=58.6035
GEO_API_FALLBACK_LON=49.6679
DB_URL=sqlite:///weather_lab.db
DB_USER=unused_for_sqlite
DB_PASSWORD=unused_for_sqlite
ENVIRONMENT=development
OUTPUT_FILE=weather_report.md
OUTPUT_DIR=data_weather
LOG_LEVEL=INFO
LOG_DIR=log
```

В `WEATHER_API_KEY` укажите свой ключ. `DB_URL` задаёт путь к базе,
а `OUTPUT_FILE` — имя основного отчёта. SQLite не использует `DB_USER`
и `DB_PASSWORD`, но эти параметры оставлены по заданию.

Если определить город по IP не удалось, используется резервный город из
`GEO_API_FALLBACK_CITY`. Его координаты можно оставить пустыми — тогда поиск
будет по названию. При смене резервного города поменяйте и обе координаты.
Остальные настройки показаны в `.env.example`.

## Запуск

Из папки проекта с активированным окружением:

```powershell
python main.py
```

## Пример отчёта

Данные в примере вымышленные.

```markdown
# Прогноз погоды

Суточный прогноз из OpenWeatherMap, агрегированный из трёхчасовых интервалов.

Автоматически определённая локация: Kirov
Период: 2026-10-04 – 2026-10-07

| Дата       | Мин. темп. (°C) | Макс. темп. (°C) | Описание | Влажность (%) | Ветер (м/с) |
|------------|-----------------|------------------|----------|---------------|-------------|
| 2026-10-04 | 8               | 14               | Облачно  | 75            | 4           |
| 2026-10-05 | 6               | 13               | Дождь    | 85            | 5           |
| 2026-10-06 | 5               | 11               | Пасмурно | 80            | 3           |
| 2026-10-07 | 7               | 15               | Ясно     | 70            | 2           |
```

## Файлы проекта

- `main.py` — запускает все шаги по порядку.
- `geo_locator.py` — определяет город и координаты.
- `weather_client.py` — запрашивает погоду и считает показатели по дням.
- `db_models.py` — описывает таблицу, сохраняет и читает данные.
- `exporter.py` — создаёт Markdown-отчёты.
- `core/settings.py` — загружает настройки.
- `core/logger.py` — настраивает журнал работы.
- `core/exceptions.py` — содержит ошибки API.
- `tests/` — тесты проекта.
- `requirements.txt` — список зависимостей.
- `pyproject.toml` — сведения о проекте и версии Python.
- `.env.example` — пример настроек.
- `.gitignore` — исключает `.env`, БД, отчёты, логи и окружение из Git.
- `.github/workflows/tests.yml` — запускает тесты на GitHub.

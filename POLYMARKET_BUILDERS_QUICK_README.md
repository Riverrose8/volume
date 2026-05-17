# Polymarket Builders Statistics

Сбор статистики по всем проектам экосистемы Polymarket Builders через официальные API.

## Быстрый старт

```bash
pip install aiohttp
python3 polymarket_builders_stats.py
python3 polymarket_builders_analyzer.py
```

## API Endpoints

- **Leaderboard**: `GET https://data-api.polymarket.com/v1/builders/leaderboard`
  - Параметры: `timePeriod` (DAY/WEEK/MONTH/ALL), `limit` (0-50), `offset` (0-1000)
  
- **Volume Time-Series**: `GET https://data-api.polymarket.com/v1/builders/volume`
  - Параметры: `timePeriod` (DAY/WEEK/MONTH/ALL)

## Собираемые метрики

- Volume (объем торговли)
- Active Users (активные пользователи)
- Rank (рейтинг)
- Verified (статус верификации)
- Daily volume trends (временные ряды)
- Volume growth (рост объема)

## Выходные файлы

- `polymarket_builders_stats.json` - полные данные
- `polymarket_builders_stats.csv` - агрегированная статистика
- `polymarket_builders_report_*.txt` - детальный отчет
- `polymarket_builders_detailed.csv` - расширенная статистика

## Пример использования

```python
from polymarket_builders_stats import PolymarketBuildersStats
import asyncio

async def main():
    async with PolymarketBuildersStats() as collector:
        stats = await collector.collect_all_stats(time_period="WEEK")
        # stats содержит словарь со статистикой по каждому builder'у

asyncio.run(main())
```

## Структура данных

### Leaderboard Response
```json
{
  "rank": "1",
  "builder": "betmoar",
  "volume": 11850000,
  "activeUsers": 1234,
  "verified": true,
  "builderLogo": "https://..."
}
```

### Volume Time-Series Response
```json
{
  "dt": "2025-11-15T00:00:00Z",
  "builder": "betmoar",
  "volume": 1500000,
  "activeUsers": 150,
  "rank": "1",
  "verified": true
}
```

## Файлы проекта

- `polymarket_builders_stats.py` - основной скрипт сбора данных
- `polymarket_builders_analyzer.py` - анализатор и генератор отчетов
- `test_polymarket_api.py` - тестирование API endpoints

## Документация

- [Polymarket API Docs](https://docs.polymarket.com/api-reference/builders/)
- [Builders Program](https://builders.polymarket.com/)
- [Dune Analytics Dashboard](https://dune.com/datadashboards/polymarket-builders)

## Требования

- Python 3.7+
- aiohttp

## Rate Limits

API имеет rate limits. Скрипт автоматически добавляет задержки между запросами (0.5 сек).

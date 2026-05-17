# Polymarket Builders Statistics Collector

Набор инструментов для сбора и анализа статистики по всем проектам экосистемы Polymarket Builders.

## 📋 Описание

Эти скрипты используют официальные API Polymarket для сбора полной статистики по всем builders в экосистеме:

- **Объем торговли** (volume)
- **Активные пользователи** (active users)
- **Рейтинг** (rank)
- **Статус верификации** (verified)
- **Временные ряды** (daily volume trends)
- **Рост объема** (volume growth)

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install aiohttp
```

### 2. Сбор статистики

```bash
python3 polymarket_builders_stats.py
```

Скрипт автоматически:
- Получает данные из API Polymarket
- Агрегирует статистику по каждому builder'у
- Сохраняет результаты в JSON и CSV форматах

### 3. Анализ данных

```bash
python3 polymarket_builders_analyzer.py
```

Генерирует детальный текстовый отчет с:
- Топ builders по различным метрикам
- Сравнительной статистикой
- Распределением по категориям

## 📊 Используемые API Endpoints

### 1. Builder Leaderboard API
```
GET https://data-api.polymarket.com/v1/builders/leaderboard
```

**Параметры:**
- `timePeriod`: DAY, WEEK, MONTH, ALL (по умолчанию: DAY)
- `limit`: 0-50 (по умолчанию: 25)
- `offset`: 0-1000 (для пагинации)

**Ответ:**
```json
[
  {
    "rank": "1",
    "builder": "betmoar",
    "volume": 11850000,
    "activeUsers": 1234,
    "verified": true,
    "builderLogo": "https://..."
  }
]
```

### 2. Builder Volume Time-Series API
```
GET https://data-api.polymarket.com/v1/builders/volume
```

**Параметры:**
- `timePeriod`: DAY, WEEK, MONTH, ALL (по умолчанию: DAY)

**Ответ:**
```json
[
  {
    "dt": "2025-11-15T00:00:00Z",
    "builder": "betmoar",
    "builderLogo": "https://...",
    "verified": true,
    "volume": 1500000,
    "activeUsers": 150,
    "rank": "1"
  }
]
```

## 📁 Выходные файлы

### 1. `polymarket_builders_stats.json`
Полные данные в JSON формате:
- Leaderboard данные
- Временные ряды объема
- Агрегированная статистика

### 2. `polymarket_builders_stats.csv`
Агрегированная статистика в CSV:
- Rank, Builder Name, Verified
- Current Volume, Active Users
- Total Volume, Avg Daily Volume
- Max Daily Volume, Days Active
- Volume Growth %

### 3. `polymarket_builders_report_YYYYMMDD_HHMMSS.txt`
Детальный текстовый отчет с анализом

### 4. `polymarket_builders_detailed.csv`
Расширенная статистика с дополнительными метриками

## 🔧 Настройка

### Изменение периода анализа

В файле `polymarket_builders_stats.py` измените параметр `time_period`:

```python
# Сбор статистики за день
stats = await collector.collect_all_stats(time_period="DAY")

# Сбор статистики за месяц
stats = await collector.collect_all_stats(time_period="MONTH")

# Вся история
stats = await collector.collect_all_stats(time_period="ALL")
```

### Rate Limits

API Polymarket имеет rate limits. Скрипт автоматически добавляет задержки между запросами. При необходимости можно увеличить:

```python
await asyncio.sleep(0.5)  # Увеличьте до 1.0 или больше
```

## 📈 Примеры использования

### Получить топ-10 builders по объему

```python
from polymarket_builders_stats import PolymarketBuildersStats
import asyncio

async def get_top_builders():
    async with PolymarketBuildersStats() as collector:
        leaderboard = await collector.fetch_all_builders_leaderboard("WEEK")
        top_10 = sorted(leaderboard, key=lambda x: x.get("volume", 0), reverse=True)[:10]
        for builder in top_10:
            print(f"{builder['builder']}: ${builder['volume']:,}")

asyncio.run(get_top_builders())
```

### Анализ роста объема конкретного builder'а

```python
async def analyze_builder_growth(builder_name: str):
    async with PolymarketBuildersStats() as collector:
        volume_data = await collector.fetch_builder_volume_timeseries("MONTH")
        builder_data = [v for v in volume_data if v.get("builder") == builder_name]
        
        if builder_data:
            volumes = [v["volume"] for v in builder_data]
            print(f"Средний объем: ${statistics.mean(volumes):,.0f}")
            print(f"Максимальный объем: ${max(volumes):,.0f}")
            print(f"Минимальный объем: ${min(volumes):,.0f}")
```

## 🔍 Дополнительные источники данных

### Dune Analytics

Для более глубокого анализа можно использовать Dune Analytics:

- [Polymarket Builders Dashboard](https://dune.com/datadashboards/polymarket-builders)
- [Polymarket Activity Dashboard](https://www.dune.com/filarm/polymarket-activity)

### Официальный сайт Builders

- [Builders Leaderboard](https://builders.polymarket.com/)
- [Builders Documentation](https://docs.polymarket.com/developers/builders/builder-intro)

## 📝 Метрики, которые собираются

### Основные метрики
- **Volume** - Текущий объем торговли
- **Active Users** - Количество активных пользователей
- **Rank** - Позиция в рейтинге
- **Verified** - Статус верификации

### Агрегированные метрики
- **Total Volume (All Time)** - Общий объем за весь период
- **Avg Daily Volume** - Средний дневной объем
- **Max Daily Volume** - Максимальный дневной объем
- **Days Active** - Количество дней активности
- **Volume Growth %** - Процент роста объема

### Временные ряды
- Ежедневные значения объема
- Ежедневные значения активных пользователей
- Тренды роста/падения

## 🛠️ Требования

- Python 3.7+
- aiohttp
- asyncio (встроенный)

## 📄 Лицензия

Скрипты предоставляются "как есть" для использования в проектах экосистемы Polymarket Builders.

## 🤝 Вклад

Если вы хотите улучшить скрипты или добавить новые функции:
1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Создайте Pull Request

## 📞 Поддержка

Для вопросов и предложений:
- Polymarket Discord: https://discord.gg/polymarket
- Polymarket Builders Telegram: (для Verified builders)

## 🔗 Полезные ссылки

- [Polymarket API Documentation](https://docs.polymarket.com/)
- [Builders Program](https://builders.polymarket.com/)
- [Data API Reference](https://docs.polymarket.com/api-reference/builders/get-aggregated-builder-leaderboard)

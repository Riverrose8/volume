# Команды для проверки логов на сервере

## 🔍 Как работают проверки GMGN через Apify (BSC бот)

1. **Когда вызывается:** после того как токен прошёл фильтры по объёму/возрасту и перед финальной проверкой (bundler, total_fees, banned dev и т.д.).
2. **Источник:** переменная окружения `APIFY_API_TOKEN` (на сервере в `~/pancake-bot/.env`).
3. **Актор Apify:** `muhammetakkurtt~gmgn-token-stat-scraper` — запрос по адресу токена и `chain: bsc`, ожидание до ~2 минут, затем разбор результата.
4. **Что забираем из ответа:** `total_fee` (BNB), `bundler`/`bundler_percentage`, `dev.creator_address`, `dev.top_10_holder_rate`, `dev.creator_open_count`, buy/sell volume для ratio.
5. **Если Apify не сработал:** fallback — парсинг HTML страницы `https://gmgn.ai/bsc/token/{address}` (BeautifulSoup).
6. **Использование в фильтрах:** `EXCLUDE_HIGH_BUNDLER` (bundler > 55%), `EXCLUDE_LOW_TOTAL_FEES` (total_fees < 0.03 BNB или нет данных; при отсутствии данных — попытка расчёта по `volume_24h`).

---

## 📋 Проверка логов GMGN/Apify

Подключитесь к серверу и перейдите в каталог бота:

```bash
ssh -l ubuntu 84.201.165.100
cd ~/pancake-bot
```

### Успешные запросы к Apify (данные получены)

```bash
grep "GMGN data from Apify" new_tokens_bot.log | tail -20
```

или по всем GMGN-записям с данными:

```bash
grep -E "GMGN data from Apify|GMGN data fetched" new_tokens_bot.log | tail -20
```

### Apify вернул пустой ответ или ошибка

```bash
grep -E "Apify returned empty|Apify GMGN fetch failed|trying HTML fallback" new_tokens_bot.log | tail -20
```

### Блокировки по total_fees / GMGN

```bash
grep -E "Skipping.*total fees|low total fees|GMGN total fees not available|using calculated total_fees" new_tokens_bot.log | tail -20
```

### Блокировки по bundler

```bash
grep "high bundler percentage" new_tokens_bot.log | tail -10
```

### Одной командой: последняя активность GMGN/Apify

```bash
grep -E "GMGN|Apify|total_fees|bundler" new_tokens_bot.log | tail -30
```

### Логи systemd (BSC бот) — если нужно смотреть вывод процесса

```bash
sudo journalctl -u pancake-bsc -n 100 --no-pager | grep -E "GMGN|Apify|total_fees|bundler"
```

*(Бот пишет основной лог в `new_tokens_bot.log`; в journal видны те же строки, если они идут в stdout/stderr.)*

---

## 🔌 Подключение к серверу

```bash
ssh -i ~/.ssh/id_rsa -p 22 ubuntu@158.160.78.224
cd ~/pancake-bot
```

## 📊 Основные команды для проверки логов

### 1. Последние строки лога (последние 50 строк)
```bash
tail -50 new_tokens_bot.log
```

### 2. Последние строки в реальном времени (мониторинг)
```bash
tail -f new_tokens_bot.log
```
*(Нажмите Ctrl+C чтобы выйти)*

### 3. Проверка получения GMGN данных
```bash
tail -100 new_tokens_bot.log | grep -E "GMGN data fetched|total_fees|Apify"
```

### 4. Проверка блокировки токенов по total_fees
```bash
tail -200 new_tokens_bot.log | grep -E "Skipping.*total fees|low total fees|GMGN total fees data not available"
```

### 5. Проверка отправленных алертов
```bash
tail -100 new_tokens_bot.log | grep -E "Alert sent|Sending Telegram|✅ Alert"
```

### 6. Проверка конкретных токенов
```bash
# Замените ADDRESS на адрес токена
grep "0xdd2422a7f797cdfb060193bd20f514d8759c7777" new_tokens_bot.log | tail -20
```

### 7. Все записи о total_fees за последний час
```bash
tail -500 new_tokens_bot.log | grep -i "total.fees" | tail -20
```

### 8. Статистика блокировок по total_fees
```bash
tail -500 new_tokens_bot.log | grep -c "low total fees"
```

### 9. Проверка работы фильтра (последние блокировки)
```bash
tail -300 new_tokens_bot.log | grep "🚫 Skipping.*total fees" | tail -10
```

### 10. Полная информация о токене (все записи)
```bash
# Замените ADDRESS на адрес токена
grep "0xdd2422a7f797cdfb060193bd20f514d8759c7777" new_tokens_bot.log
```

## 🔍 Комплексная проверка (одна команда)

```bash
echo "=== Статус бота ===" && \
ps aux | grep "[p]ython3.*main\.py" | grep -v "main_base.py" && \
echo "" && \
echo "=== Последние GMGN данные ===" && \
tail -200 new_tokens_bot.log | grep "GMGN data fetched" | tail -5 && \
echo "" && \
echo "=== Последние блокировки по total_fees ===" && \
tail -200 new_tokens_bot.log | grep "Skipping.*total fees" | tail -5 && \
echo "" && \
echo "=== Последние отправленные алерты ===" && \
tail -200 new_tokens_bot.log | grep "Alert sent" | tail -5
```

## 📈 Мониторинг в реальном времени

### Мониторинг всех событий
```bash
tail -f new_tokens_bot.log
```

### Мониторинг только GMGN и total_fees
```bash
tail -f new_tokens_bot.log | grep -E "GMGN|total_fees|Skipping.*total fees|total fees data not available"
```

### Мониторинг только блокировок
```bash
tail -f new_tokens_bot.log | grep "🚫 Skipping"
```

### Мониторинг только отправленных алертов
```bash
tail -f new_tokens_bot.log | grep -E "Alert sent|Sending Telegram"
```

## 🧪 Тестирование конкретных токенов

### Проверка всех трех токенов из вашего запроса
```bash
echo "=== Токен 1 ===" && \
grep "0xdd2422a7f797cdfb060193bd20f514d8759c7777" new_tokens_bot.log | tail -5 && \
echo "" && \
echo "=== Токен 2 ===" && \
grep "0x1a5acdd9467854a85b9c45fb20010ebb89114444" new_tokens_bot.log | tail -5 && \
echo "" && \
echo "=== Токен 3 ===" && \
grep "0xae7b3bea74d81d3e4e75eb359a56bf3340ac7777" new_tokens_bot.log | tail -5
```

## 📋 Полезные команды

### Размер лог файла
```bash
ls -lh new_tokens_bot.log
```

### Количество строк в логе
```bash
wc -l new_tokens_bot.log
```

### Поиск ошибок
```bash
tail -200 new_tokens_bot.log | grep -i "error\|exception\|failed\|❌"
```

### Поиск предупреждений
```bash
tail -200 new_tokens_bot.log | grep -i "warning\|⚠️"
```

## 🚀 Быстрая проверка (одна команда с локального компьютера)

```bash
ssh -i ~/.ssh/id_rsa -p 22 ubuntu@158.160.78.224 "cd ~/pancake-bot && tail -100 new_tokens_bot.log | grep -E 'GMGN data fetched|Skipping.*total fees|Alert sent' | tail -10"
```

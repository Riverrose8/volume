# BSC Pancake бот: почему нет сигналов с 23 января

## Краткий вывод

**Причина:** Включён фильтр `EXCLUDE_LOW_TOTAL_FEES=true`. Для проверки используется **только** total fees из GMGN (Apify). Если GMGN/Apify не возвращает данные (таймаут, ошибка, смена вёрстки GMGN), то `total_fees_bnb` остаётся `None`, и **все** токены блокируются сообщением:

```
🚫 Skipping <symbol>: GMGN total fees data not available (required for filtering)
```

В результате с 23 января не отправляется ни одного алерта по BSC Pancake.

Base Uniswap Alerts работают отдельно (другой бот, без GMGN total_fees), поэтому там всё в порядке.

---

## Что сделано в коде

1. **Fallback на расчёт total fees**  
   Если GMGN не вернул `total_fees_bnb`, используется расчёт по `volume_24h` (функция `calculate_total_fees()`).  
   Алерты снова могут проходить, когда Apify недоступен или не отдаёт данные.

2. **Блокировка только при полном отсутствии данных**  
   Токен пропускается только если и GMGN не вернул данные, и расчёт по `volume_24h` невозможен (нет `volume_24h`).

---

## Как проверить на сервере (BSC Pancake бот)

Сервер из `CHECK_LOGS_COMMANDS.md`: **ubuntu@158.160.78.224**, директория **~/pancake-bot**, лог **new_tokens_bot.log**.

### 1. Подключение и последние строки лога

```bash
ssh -i ~/.ssh/id_rsa -p 22 ubuntu@158.160.78.224
cd ~/pancake-bot
tail -100 new_tokens_bot.log
```

### 2. Есть ли блокировки из‑за отсутствия GMGN total fees

```bash
tail -500 new_tokens_bot.log | grep "GMGN total fees data not available"
# или после правки:
tail -500 new_tokens_bot.log | grep "GMGN total fees not available and could not calculate"
```

Если такие строки есть часто — причина отсутствия сигналов именно в этом.

### 3. Приходят ли вообще данные от GMGN/Apify

```bash
tail -300 new_tokens_bot.log | grep -E "✅ GMGN data fetched|⚠️ GMGN data not fetched|Apify"
```

### 4. Есть ли токены, проходящие по объёму (до фильтров)

```bash
tail -300 new_tokens_bot.log | grep "Found.*tokens matching criteria"
```

Если видно `Found 0 tokens` — возможно, просто нет подходящих по объёму/возрасту; если `Found 1+` и при этом нет алертов — с большой вероятностью режут фильтры (в т.ч. GMGN total fees).

### 5. Быстрая проверка с одной команды (по SSH)

```bash
ssh -i ~/.ssh/id_rsa -p 22 ubuntu@158.160.78.224 "cd ~/pancake-bot && tail -200 new_tokens_bot.log | grep -E 'GMGN total fees|Alert sent|Found.*tokens matching'"
```

---

## После обновления main.py на сервере

1. Задеплойте обновлённый `main.py` (с fallback на `calculate_total_fees`).
2. Перезапустите BSC Pancake бот.
3. Проследите логи на сообщения:
   - `ℹ️ <symbol>: using calculated total_fees (GMGN unavailable): X.XXXX BNB` — сработал fallback, алерты снова могут идти.
   - `🚫 Skipping ... GMGN total fees not available and could not calculate` — нет ни GMGN, ни volume_24h; такие токены по-прежнему блокируются.

При необходимости можно временно отключить фильтр по total fees в `.env` на сервере:

```bash
EXCLUDE_LOW_TOTAL_FEES=false
```

Тогда алерты пойдут и без GMGN/расчёта (риск скама выше).

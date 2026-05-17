# Apify возвращает пустые данные — что проверить

Сообщения в логах:
- `⚠️ Apify returned empty data for 0x..., trying HTML fallback...`
- `🚫 Skipping SYMBOL: GMGN total fees data not available (required for filtering)`

Означают: Apify-актор GMGN Token Stat Scraper либо не вернул данные, либо вернул пустой dataset. Ниже — возможные причины и что проверить.

---

## 1. Токен на сервере (APIFY_API_TOKEN)

Бот читает токен из `.env` в каталоге проекта.

**Проверка на сервере:**
```bash
ssh -l ubuntu YOUR_SERVER
cd ~/pancake-bot
grep APIFY_API_TOKEN .env
```

- Если строки нет или значение пустое — Apify не вызывается (или используется старый/другой токен). Добавьте в `.env`:
  ```bash
  APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  ```
  Токен берётся здесь: https://console.apify.com/account/integrations  
- Токен должен быть тот же, с которым локальный тест `python3 test_apify_gmgn.py` успешно проходит.

После изменения `.env` перезапустите BSC бота:
```bash
sudo systemctl restart pancake-bsc
```

---

## 2. Apify: лимиты и подписка

- **Credits / план:** если закончились кредиты или подписка неактивна, запуски актора могут не выполняться или возвращать пустой результат.  
  Проверка: https://console.apify.com/account/billing  
- **Лимиты актора:** у актора могут быть ограничения по числу запусков/дня.  
  Проверка: страница актора GMGN Token Stat Scraper в Apify Store.

---

## 3. Apify: история запусков (Runs)

Чтобы понять, что именно делает Apify по вашим запросам:

1. Откройте https://console.apify.com/actors/runs  
2. Найдите актор **GMGN Token Stat Scraper** (или `muhammetakkurtt/gmgn-token-stat-scraper`).  
3. Посмотрите последние runs:
   - **Status: Succeeded** — запуск прошёл; если бот всё равно пишет "empty data", значит dataset пустой (см. п. 4).  
   - **Status: Failed / Aborted** — причина будет в логах run (Error, Log).  
   - Runs нет или очень старые — возможно, токен не тот, не передаётся с сервера или запросы не доходят (сеть/файрвол).

В коде бота теперь пишется `run_id` в лог при старте Apify run — по нему можно найти нужный run в консоли Apify.

---

## 4. Актор вернул 0 записей (dataset пустой)

Актор может завершиться успешно (Succeeded), но вернуть **0 items** в dataset, если:

- Токен ещё не появился на GMGN (слишком новый).  
- GMGN не отдал данные (изменение вёрстки, блокировка, таймаут).  
- Ошибка внутри актора без явного Failed (например, пустой результат по логике скрапера).

В логах бота теперь есть сообщение:
`Apify returned 0 items for 0x... (token may not be on GMGN yet)`.

Что сделать: открыть run в Apify → вкладка **Output** — посмотреть, есть ли там хотя бы одна запись и какие поля (например, `total_fee` / `totalFee`).

---

## 5. Неверный формат входных данных

Бот передаёт в актор:

- `tokenAddresses`: массив с одним адресом токена (строка, например `"0x..."`),  
- `chain`: `"bsc"`,  
- `proxyConfiguration`: `{ "useApifyProxy": true }`.

Проверьте в коде (поиск по `input_data` в `main.py`), что на сервере не подставляется другой chain или пустой адрес. В логах теперь есть строка `Apify run started for 0x... run_id=...` — по ней видно, что запрос к Apify ушёл.

---

## 6. Что добавлено в код для диагностики

При пустом ответе Apify в логах теперь будут видны причины (уровень INFO/WARNING):

- `Apify run failed: HTTP 401/403 ...` — неверный или отсутствующий токен, нет доступа.  
- `Apify run started for 0x... run_id=...` — запуск создан, можно искать run в Apify.  
- `Apify run FAILED/ABORTED for 0x... run_id=...` — run упал, смотреть логи в Apify.  
- `Apify timeout after 120s for 0x... run_id=...` — актор не успел завершиться.  
- `Apify dataset fetch failed: HTTP ...` — не удалось забрать dataset.  
- `Apify returned 0 items for 0x... (token may not be on GMGN yet)` — dataset пустой.

После деплоя обновлённого `main.py` и перезапуска (`sudo systemctl restart pancake-bsc`) при следующем срабатывании GMGN-проверки по логам будет понятно, на каком шаге пусто.

---

## Краткий чек-лист

| Проверка | Где |
|----------|-----|
| В `.env` есть `APIFY_API_TOKEN` и он не пустой | Сервер: `~/pancake-bot/.env` |
| Тот же токен успешно работает локально | `python3 test_apify_gmgn.py` |
| Есть кредиты и активная подписка | https://console.apify.com/account/billing |
| Последние runs актора — статус и вывод | https://console.apify.com/actors/runs |
| В логах бота — новая диагностика (run_id, HTTP, timeout, 0 items) | `grep -E "Apify|GMGN" ~/pancake-bot/new_tokens_bot.log \| tail -50` |

Если после этого Apify по-прежнему отдаёт пустые данные, пришлите:  
1) последние строки лога с "Apify" / "GMGN" для одного токена,  
2) скрин или описание соответствующего run в Apify (Status, Output, при необходимости Log).

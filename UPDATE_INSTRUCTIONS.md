# Инструкция по обновлению основного бота на сервере

## Изменения
- Убрана фильтрация по fees (MIN_TOTAL_FEES_BNB)
- Fees теперь просто отображается в алертах для всех токенов
- Используется pool_fee_percentage из GeckoTerminal API

## Способ 1: Через SSH (рекомендуется)

```bash
# 1. Загрузите main.py на сервер
scp -P 22 main.py Administrator@84.201.161.90:~/pancake-bot/main.py

# 2. Подключитесь к серверу
ssh Administrator@84.201.161.90

# 3. На сервере выполните:
cd ~/pancake-bot

# 4. Остановите старый процесс
pkill -f "python.*main.py" | grep -v "main_base.py"

# 5. Запустите обновленный бот
nohup python3 main.py >> new_tokens_bot.log 2>&1 &

# 6. Проверьте статус
ps aux | grep "python.*main.py" | grep -v "main_base.py"
tail -20 new_tokens_bot.log
```

## Способ 2: Использовать скрипт update_main_bot.sh

```bash
# Убедитесь, что SSH ключ настроен правильно в скрипте
./update_main_bot.sh
```

## Способ 3: Через git (если настроен на сервере)

```bash
# На сервере:
cd ~/pancake-bot
git pull origin main
pkill -f "python.*main.py" | grep -v "main_base.py"
nohup python3 main.py >> new_tokens_bot.log 2>&1 &
```

## Проверка после обновления

```bash
# Проверьте логи
tail -f new_tokens_bot.log

# Проверьте, что fees отображается в алертах
# Должна быть строка: 💼 Total fees: X.XXBNB
```

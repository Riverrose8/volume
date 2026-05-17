# Инструкция по обновлению Base бота на сервере

## 📋 Подготовка

### 1. Настройте скрипты

Откройте файлы `update_server.sh` и `connect_server.sh` и измените следующие переменные:

```bash
SERVER_USER="your_username"          # Ваше имя пользователя на сервере
SERVER_HOST="your_server_ip"         # IP адрес или домен сервера
SERVER_PORT="22"                     # SSH порт (обычно 22)
PROJECT_DIR="~/pancake-pools-bot"    # Путь к проекту на сервере
SSH_KEY=""                           # Путь к SSH ключу (если используется)
```

### 2. Проверьте SSH доступ

Убедитесь, что у вас есть доступ к серверу по SSH:

```bash
ssh your_username@your_server_ip
```

## 🚀 Использование

### Вариант 1: Автоматическое обновление (рекомендуется)

Запустите скрипт `update_server.sh`:

```bash
./update_server.sh
```

Скрипт автоматически:
- ✅ Подключится к серверу
- ✅ Перейдет в директорию проекта
- ✅ Обновит код с GitHub (`git pull`)
- ✅ Остановит старый процесс Base бота
- ✅ Запустит обновленную версию
- ✅ Покажет статус и последние логи

### Вариант 2: Ручное подключение

Если нужно выполнить команды вручную:

```bash
./connect_server.sh
```

Это откроет SSH сессию и автоматически перейдет в директорию проекта.

Затем выполните команды вручную:

```bash
# Обновить код
git pull origin main

# Остановить бот
pkill -f "python.*main_base.py"

# Запустить обновленную версию
nohup python3 main_base.py > /dev/null 2>&1 &

# Проверить статус
ps aux | grep main_base.py
tail -20 new_tokens_bot.log
```

## 🔧 Ручное обновление (если скрипты не работают)

### 1. Подключитесь к серверу

```bash
ssh your_username@your_server_ip
```

### 2. Перейдите в директорию проекта

```bash
cd ~/pancake-pools-bot
# или
cd ~/pancake\ pools\ bot
```

### 3. Обновите код

```bash
git pull origin main
```

### 4. Перезапустите бот

```bash
# Остановить
pkill -f "python.*main_base.py"

# Запустить
nohup python3 main_base.py > /dev/null 2>&1 &
```

### 5. Проверьте статус

```bash
# Проверить, что процесс запущен
ps aux | grep main_base.py

# Посмотреть логи
tail -f new_tokens_bot.log
```

## 📝 Проверка после обновления

1. **Проверьте, что бот запущен:**
   ```bash
   ps aux | grep main_base.py
   ```

2. **Проверьте логи:**
   ```bash
   tail -50 new_tokens_bot.log
   ```

3. **Проверьте, что нет ошибок:**
   ```bash
   grep -i error new_tokens_bot.log | tail -10
   ```

## ⚠️ Устранение проблем

### Проблема: "Permission denied"

**Решение:** Убедитесь, что скрипты исполняемые:
```bash
chmod +x update_server.sh connect_server.sh
```

### Проблема: "Connection refused"

**Решение:** Проверьте:
- Правильность IP адреса и порта
- Доступность сервера
- Настройки firewall

### Проблема: "Директория не найдена"

**Решение:** Найдите правильный путь к проекту:
```bash
ssh your_username@your_server_ip
find ~ -name "main_base.py" -type f 2>/dev/null
```

### Проблема: Бот не запускается

**Решение:** Проверьте логи:
```bash
tail -100 new_tokens_bot.log
python3 main_base.py  # Запуск в foreground для просмотра ошибок
```

## 🔐 Безопасность

- ✅ Используйте SSH ключи вместо паролей
- ✅ Не храните пароли в скриптах
- ✅ Используйте переменные окружения для чувствительных данных

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи: `tail -100 new_tokens_bot.log`
2. Проверьте статус процесса: `ps aux | grep main_base.py`
3. Проверьте последние коммиты: `git log --oneline -10`


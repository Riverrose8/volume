#!/bin/bash

# ============================================
# Скрипт для обновления основного BSC бота на сервере
# ============================================

# Настройки сервера (ИЗМЕНИТЕ ПОД ВАШ СЕРВЕР)
SERVER_USER="ubuntu"                 # Имя пользователя на сервере
SERVER_HOST="158.160.78.224"        # IP адрес или домен сервера
SERVER_PORT=""                      # SSH порт (оставьте пустым для автоматического определения, обычно 22)
PROJECT_DIR="~/pancake-bot"          # Путь к проекту на сервере
SSH_KEY="$HOME/.ssh/id_rsa"         # Путь к SSH ключу

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Обновление основного BSC бота на сервере${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Автоматическое определение порта, если не указан
if [ -z "$SERVER_PORT" ]; then
    echo -e "${YELLOW}Порт не указан, пытаюсь определить автоматически...${NC}"
    
    # Пробуем стандартные порты
    for port in 22 2222; do
        echo -n "  Проверка порта $port... "
        if (timeout 2 bash -c "echo > /dev/tcp/$SERVER_HOST/$port" 2>/dev/null) || \
           (command -v nc >/dev/null && nc -z -w2 $SERVER_HOST $port 2>/dev/null); then
            SERVER_PORT=$port
            echo -e "${GREEN}✓ Работает${NC}"
            break
        else
            echo -e "${RED}✗ Недоступен${NC}"
        fi
    done
    
    if [ -z "$SERVER_PORT" ]; then
        echo -e "${YELLOW}Не удалось определить порт автоматически.${NC}"
        read -p "Введите SSH порт (обычно 22): " SERVER_PORT
        SERVER_PORT=${SERVER_PORT:-22}
    fi
fi

echo -e "${GREEN}Используется порт: $SERVER_PORT${NC}"
echo ""

# Формируем команду SSH
SSH_CMD="ssh"
if [ ! -z "$SSH_KEY" ]; then
    SSH_CMD="$SSH_CMD -i $SSH_KEY"
fi
SSH_CMD="$SSH_CMD -p $SERVER_PORT $SERVER_USER@$SERVER_HOST"

# Проверяем подключение к серверу
echo -e "${YELLOW}Проверка подключения к серверу...${NC}"
if ssh -p $SERVER_PORT -o ConnectTimeout=5 $SERVER_USER@$SERVER_HOST "echo 'Connection OK'" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Подключение успешно${NC}"
else
    echo -e "${RED}✗ Не удалось подключиться к серверу${NC}"
    exit 1
fi

# Загружаем main.py на сервер
echo ""
echo -e "${YELLOW}Загрузка main.py на сервер...${NC}"
SCP_CMD="scp"
if [ ! -z "$SSH_KEY" ]; then
    SCP_CMD="$SCP_CMD -i $SSH_KEY"
fi
SCP_CMD="$SCP_CMD -P $SERVER_PORT main.py $SERVER_USER@$SERVER_HOST:$PROJECT_DIR/main.py"

if $SCP_CMD; then
    echo -e "${GREEN}✓ Файл успешно загружен${NC}"
else
    echo -e "${RED}✗ Ошибка при загрузке файла${NC}"
    exit 1
fi

# Выполняем команды на сервере
echo ""
echo -e "${YELLOW}Выполнение команд на сервере...${NC}"
echo ""

$SSH_CMD << ENDSSH
    # Переходим в директорию проекта
    cd ~/pancake-bot || cd ~/pancake-pools-bot || cd ~/pancake\ pools\ bot || {
        echo "❌ Директория проекта не найдена!"
        echo "Доступные директории:"
        ls -la ~ | grep -E "pancake|bot"
        exit 1
    }
    
    echo "✓ Перешли в директорию: \$(pwd)"
    echo ""
    
    # Останавливаем старый процесс основного бота
    echo "🛑 Остановка основного BSC бота..."
    MAIN_BOT_PID=\$(ps aux | grep "[p]ython.*main\.py" | grep -v "main_base.py" | awk '{print \$2}')
    
    if [ -z "\$MAIN_BOT_PID" ]; then
        echo "⚠️  Основной бот не запущен"
    else
        echo "Найден процесс основного бота (PID: \$MAIN_BOT_PID)"
        kill \$MAIN_BOT_PID
        sleep 2
        
        # Проверяем, что процесс остановлен
        if ps -p \$MAIN_BOT_PID > /dev/null 2>&1; then
            echo "⚠️  Процесс не остановился, принудительная остановка..."
            kill -9 \$MAIN_BOT_PID
            sleep 1
        fi
        echo "✓ Основной бот остановлен"
    fi
    
    echo ""
    
    # Запускаем обновленный бот
    echo "🚀 Запуск обновленного основного BSC бота..."
    nohup python3 main.py >> new_tokens_bot.log 2>&1 &
    NEW_PID=\$!
    sleep 2
    
    # Проверяем, что бот запустился
    if ps -p \$NEW_PID > /dev/null 2>&1; then
        echo "✓ Основной бот успешно запущен (PID: \$NEW_PID)"
    else
        echo "❌ Ошибка при запуске основного бота"
        echo "Проверьте логи: tail -50 new_tokens_bot.log"
        exit 1
    fi
    
    echo ""
    echo "✅ Обновление завершено успешно!"
    echo ""
    echo "📊 Статус процесса:"
    ps aux | grep "[p]ython.*main\.py" | grep -v "main_base.py" | head -1
    echo ""
    echo "📝 Последние строки лога:"
    tail -5 new_tokens_bot.log 2>/dev/null || echo "Лог файл не найден"
ENDSSH

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Готово!${NC}"
echo -e "${GREEN}========================================${NC}"

#!/bin/bash

# ============================================
# Скрипт для добавления APIFY_API_TOKEN в .env на сервере
# ============================================

# Настройки сервера
SERVER_USER="ubuntu"
SERVER_HOST="158.160.78.224"
SERVER_PORT="22"
PROJECT_DIR="~/pancake-bot"
SSH_KEY="$HOME/.ssh/id_rsa"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Добавление APIFY_API_TOKEN в .env${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Проверяем, передан ли токен как аргумент
if [ -z "$1" ]; then
    echo -e "${YELLOW}Использование: $0 <APIFY_API_TOKEN>${NC}"
    echo ""
    echo "Пример:"
    echo "  $0 apify_api_xxxxxxxxxxxxxxxxxxxxx"
    echo ""
    echo "Получить токен можно здесь:"
    echo "  https://console.apify.com/account/integrations"
    echo ""
    exit 1
fi

APIFY_TOKEN="$1"

# Формируем команду SSH
SSH_CMD="ssh"
if [ ! -z "$SSH_KEY" ] && [ -f "$SSH_KEY" ]; then
    SSH_CMD="$SSH_CMD -i $SSH_KEY"
fi
SSH_CMD="$SSH_CMD -p $SERVER_PORT $SERVER_USER@$SERVER_HOST"

# Проверяем подключение
echo -e "${YELLOW}Проверка подключения к серверу...${NC}"
if ssh -p $SERVER_PORT -o ConnectTimeout=5 $SERVER_USER@$SERVER_HOST "echo 'Connection OK'" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Подключение успешно${NC}"
else
    echo -e "${RED}✗ Не удалось подключиться к серверу${NC}"
    exit 1
fi

# Добавляем токен в .env
echo ""
echo -e "${YELLOW}Добавление APIFY_API_TOKEN в .env...${NC}"

$SSH_CMD << ENDSSH
    cd $PROJECT_DIR || exit 1
    
    # Проверяем, существует ли .env
    if [ ! -f .env ]; then
        echo "❌ Файл .env не найден!"
        exit 1
    fi
    
    # Удаляем старую запись APIFY_API_TOKEN, если есть
    sed -i '/^APIFY_API_TOKEN=/d' .env
    
    # Добавляем новую запись в конец файла
    echo "" >> .env
    echo "# Apify API Key (для GMGN данных)" >> .env
    echo "APIFY_API_TOKEN=$APIFY_TOKEN" >> .env
    
    echo "✅ APIFY_API_TOKEN добавлен в .env"
    
    # Показываем последние строки для проверки
    echo ""
    echo "📋 Последние 3 строки .env:"
    tail -3 .env
ENDSSH

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Токен успешно добавлен!${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  ВАЖНО: Перезапустите бота, чтобы изменения вступили в силу:${NC}"
    echo "  1. Остановите бота: ssh $SERVER_USER@$SERVER_HOST 'pkill -f \"python.*main.py\"'"
    echo "  2. Запустите бота: ssh $SERVER_USER@$SERVER_HOST 'cd $PROJECT_DIR && nohup python3 main.py >> new_tokens_bot.log 2>&1 &'"
    echo ""
    echo "Или используйте скрипт: ./update_main_bot.sh"
else
    echo ""
    echo -e "${RED}❌ Ошибка при добавлении токена${NC}"
    exit 1
fi

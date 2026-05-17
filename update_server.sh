#!/bin/bash

# ============================================
# Скрипт для обновления Base бота на сервере
# ============================================

# Настройки сервера (ИЗМЕНИТЕ ПОД ВАШ СЕРВЕР)
SERVER_USER="ubuntu"                 # Имя пользователя на сервере (попробуйте также: Administrator, admin, root)
SERVER_HOST="84.201.161.90"         # IP адрес или домен сервера
SERVER_PORT=""                      # SSH порт (оставьте пустым для автоматического определения, обычно 22)
PROJECT_DIR="~/pancake-bot"          # Путь к проекту на сервере
SSH_KEY=""                          # Путь к SSH ключу (если нужен, например: ~/.ssh/id_rsa)

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Обновление Base бота на сервере${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Автоматическое определение порта, если не указан
if [ -z "$SERVER_PORT" ]; then
    echo -e "${YELLOW}Порт не указан, пытаюсь определить автоматически...${NC}"
    
    # Пробуем стандартные порты
    for port in 22 2222; do
        echo -n "  Проверка порта $port... "
        # Проверяем доступность порта (работает на Linux и macOS)
        if (timeout 2 bash -c "echo > /dev/tcp/$SERVER_HOST/$port" 2>/dev/null) || \
           (command -v nc >/dev/null && nc -z -w2 $SERVER_HOST $port 2>/dev/null); then
            SERVER_PORT=$port
            echo -e "${GREEN}✓ Работает${NC}"
            break
        else
            echo -e "${RED}✗ Недоступен${NC}"
        fi
    done
    
    # Если не удалось определить автоматически, спрашиваем у пользователя
    if [ -z "$SERVER_PORT" ]; then
        echo -e "${YELLOW}Не удалось определить порт автоматически.${NC}"
        read -p "Введите SSH порт (обычно 22): " SERVER_PORT
        SERVER_PORT=${SERVER_PORT:-22}  # По умолчанию 22
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
SSH_ERROR=$(ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "echo 'Connection OK'" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Подключение успешно${NC}"
else
    echo -e "${RED}✗ Не удалось подключиться к серверу${NC}"
    echo ""
    echo -e "${YELLOW}Детали ошибки:${NC}"
    echo "$SSH_ERROR" | head -3
    echo ""
    
    # Пробуем альтернативные имена пользователей
    echo -e "${YELLOW}Пробую альтернативные имена пользователей...${NC}"
    for alt_user in ubuntu admin root; do
        if [ "$alt_user" != "$SERVER_USER" ]; then
            echo -n "  Проверка пользователя '$alt_user'... "
            if ssh -p $SERVER_PORT -o ConnectTimeout=3 -o BatchMode=yes $alt_user@$SERVER_HOST "echo OK" >/dev/null 2>&1; then
                echo -e "${GREEN}✓ Работает!${NC}"
                echo -e "${YELLOW}Используйте: SERVER_USER=\"$alt_user\"${NC}"
                break
            else
                echo -e "${RED}✗${NC}"
            fi
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Возможные решения:${NC}"
    echo "1. Проверьте правильность имени пользователя (SERVER_USER)"
    echo "2. Убедитесь, что SSH ключ настроен правильно"
    echo "3. Проверьте, что сервер доступен: ping $SERVER_HOST"
    echo "4. Попробуйте подключиться вручную:"
    echo ""
    if [ -z "$SSH_KEY" ]; then
        echo -e "   ${YELLOW}ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST${NC}"
        echo ""
        echo -e "   ${YELLOW}Или с SSH ключом:${NC}"
        echo -e "   ${YELLOW}ssh -p $SERVER_PORT -i ~/.ssh/id_rsa $SERVER_USER@$SERVER_HOST${NC}"
    else
        echo -e "   ${YELLOW}ssh -p $SERVER_PORT -i $SSH_KEY $SERVER_USER@$SERVER_HOST${NC}"
    fi
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
    
    # Настраиваем git config (если не настроено)
    if [ -z "\$(git config user.email)" ]; then
        echo "⚙️  Настройка git config..."
        git config user.email "bot@server.local"
        git config user.name "Server Bot"
    fi
    
    # Проверяем статус git
    echo "📊 Проверка статуса git..."
    git status --short
    echo ""
    
    # Сохраняем текущие изменения (если есть) - пропускаем интерактивный запрос
    if [ -n "\$(git status --porcelain)" ]; then
        echo "⚠️  Обнаружены незакоммиченные изменения"
        echo "💾 Автоматически сохраняю изменения..."
        git add -A
        git commit -m "Auto-save before update \$(date +%Y-%m-%d_%H:%M:%S)" || echo "⚠️  Не удалось сохранить (возможно, нет изменений для коммита)"
    fi
    
    # Получаем последние изменения
    echo "📥 Получение обновлений с GitHub..."
    git fetch origin
    
    # Показываем, что будет обновлено
    echo ""
    echo "📋 Изменения, которые будут применены:"
    git log HEAD..origin/main --oneline | head -10
    echo ""
    
    # Обновляем код
    echo "🔄 Обновление кода..."
    git pull origin main
    
    if [ $? -eq 0 ]; then
        echo "✓ Код успешно обновлен"
    else
        echo "❌ Ошибка при обновлении кода"
        exit 1
    fi
    
    echo ""
    
    # Останавливаем старый процесс Base бота
    echo "🛑 Остановка Base бота..."
    BASE_BOT_PID=\$(ps aux | grep "[p]ython.*main_base.py" | awk '{print \$2}')
    
    if [ -z "\$BASE_BOT_PID" ]; then
        echo "⚠️  Base бот не запущен"
    else
        echo "Найден процесс Base бота (PID: \$BASE_BOT_PID)"
        kill \$BASE_BOT_PID
        sleep 2
        
        # Проверяем, что процесс остановлен
        if ps -p \$BASE_BOT_PID > /dev/null 2>&1; then
            echo "⚠️  Процесс не остановился, принудительная остановка..."
            kill -9 \$BASE_BOT_PID
            sleep 1
        fi
        echo "✓ Base бот остановлен"
    fi
    
    echo ""
    
    # Запускаем обновленный бот
    echo "🚀 Запуск обновленного Base бота..."
    nohup python3 main_base.py > /dev/null 2>&1 &
    NEW_PID=\$!
    sleep 2
    
    # Проверяем, что бот запустился
    if ps -p \$NEW_PID > /dev/null 2>&1; then
        echo "✓ Base бот успешно запущен (PID: \$NEW_PID)"
    else
        echo "❌ Ошибка при запуске Base бота"
        echo "Проверьте логи: tail -50 new_tokens_bot.log"
        exit 1
    fi
    
    echo ""
    echo "✅ Обновление завершено успешно!"
    echo ""
    echo "📊 Статус процесса:"
    ps aux | grep "[p]ython.*main_base.py" | head -1
    echo ""
    echo "📝 Последние строки лога:"
    tail -5 new_tokens_bot.log 2>/dev/null || echo "Лог файл не найден"
ENDSSH

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Готово!${NC}"
echo -e "${GREEN}========================================${NC}"


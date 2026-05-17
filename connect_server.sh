#!/bin/bash

# ============================================
# Скрипт для подключения к серверу
# ============================================

# Настройки сервера (ИЗМЕНИТЕ ПОД ВАШ СЕРВЕР)
SERVER_USER="Administrator"          # Имя пользователя на сервере
SERVER_HOST="84.201.161.90"         # IP адрес или домен сервера
SERVER_PORT=""                      # SSH порт (оставьте пустым для автоматического определения, обычно 22)
PROJECT_DIR="~/pancake-pools-bot"    # Путь к проекту на сервере
SSH_KEY=""                          # Путь к SSH ключу (если нужен, например: ~/.ssh/id_rsa)

# Автоматическое определение порта, если не указан
if [ -z "$SERVER_PORT" ]; then
    echo "🔍 Порт не указан, пытаюсь определить автоматически..."
    
    # Пробуем стандартные порты
    for port in 22 2222; do
        echo -n "  Проверка порта $port... "
        if timeout 2 bash -c "echo > /dev/tcp/$SERVER_HOST/$port" 2>/dev/null || \
           (command -v nc >/dev/null && nc -z -w2 $SERVER_HOST $port 2>/dev/null); then
            SERVER_PORT=$port
            echo "✓ Работает"
            break
        else
            echo "✗ Недоступен"
        fi
    done
    
    # Если не удалось определить автоматически, спрашиваем у пользователя
    if [ -z "$SERVER_PORT" ]; then
        echo "Не удалось определить порт автоматически."
        read -p "Введите SSH порт (обычно 22): " SERVER_PORT
        SERVER_PORT=${SERVER_PORT:-22}  # По умолчанию 22
    fi
fi

# Формируем команду SSH
SSH_CMD="ssh"
if [ ! -z "$SSH_KEY" ]; then
    SSH_CMD="$SSH_CMD -i $SSH_KEY"
fi
SSH_CMD="$SSH_CMD -p $SERVER_PORT $SERVER_USER@$SERVER_HOST"

# Подключаемся к серверу и переходим в директорию проекта
echo "🔌 Подключение к серверу $SERVER_USER@$SERVER_HOST..."
echo "📁 Переход в директорию проекта..."
echo ""

$SSH_CMD -t "cd $PROJECT_DIR 2>/dev/null || cd ~/pancake-pools-bot 2>/dev/null || cd ~/pancake\ pools\ bot 2>/dev/null || { echo 'Директория не найдена. Доступные директории:'; ls -la ~ | grep -E 'pancake|bot'; bash; } && bash"


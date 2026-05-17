#!/bin/bash

# ============================================
# Скрипт для обновления BSC бота на сервере
# ============================================

SERVER_USER="ubuntu"
SERVER_HOST="84.201.161.90"
SERVER_PORT="22"
PROJECT_DIR="pancake-pools-bot"

echo "=========================================="
echo "🔄 Обновление BSC бота на сервере"
echo "=========================================="
echo ""

# Проверяем подключение
echo "🔌 Проверка подключения к серверу..."
if ! ssh -p $SERVER_PORT -o ConnectTimeout=5 $SERVER_USER@$SERVER_HOST "echo 'OK'" >/dev/null 2>&1; then
    echo "❌ Не удалось подключиться к серверу"
    echo ""
    echo "Возможные причины:"
    echo "1. SSH ключ не настроен"
    echo "2. Сервер недоступен"
    echo ""
    echo "Попробуйте подключиться вручную:"
    echo "  ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST"
    echo ""
    echo "После успешного подключения выполните команды:"
    echo "  cd $PROJECT_DIR"
    echo "  git pull"
    echo "  sudo systemctl restart pancake-bsc-bot.service"
    echo "  sudo systemctl status pancake-bsc-bot.service"
    exit 1
fi

echo "✅ Подключение успешно"
echo ""

# Выполняем обновление
echo "📥 Получение обновлений с GitHub..."
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST << 'ENDSSH'
    cd pancake-pools-bot || {
        echo "❌ Директория не найдена"
        exit 1
    }
    
    echo "📂 Текущая директория: $(pwd)"
    echo ""
    
    # Получаем обновления
    git fetch origin
    
    echo "📋 Изменения:"
    git log HEAD..origin/main --oneline | head -5
    echo ""
    
    # Обновляем код
    git pull origin main
    
    if [ $? -eq 0 ]; then
        echo "✅ Код успешно обновлен"
    else
        echo "❌ Ошибка при обновлении кода"
        exit 1
    fi
ENDSSH

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при обновлении кода"
    exit 1
fi

echo ""
echo "🔄 Перезапуск BSC бота через systemd..."

ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST << 'ENDSSH'
    # Перезапускаем через systemd
    sudo systemctl restart pancake-bsc-bot.service
    
    if [ $? -eq 0 ]; then
        echo "✅ Бот перезапущен"
    else
        echo "❌ Ошибка при перезапуске"
        exit 1
    fi
    
    # Ждем 3 секунды для запуска
    sleep 3
    
    # Показываем статус
    echo ""
    echo "📊 Статус бота:"
    sudo systemctl status pancake-bsc-bot.service --no-pager -l | head -20
    
    echo ""
    echo "📝 Последние строки лога:"
    tail -10 new_tokens_bot.log 2>/dev/null || echo "Лог файл не найден"
ENDSSH

echo ""
echo "=========================================="
echo "✅ Обновление завершено!"
echo "=========================================="
echo ""
echo "Проверить токен можно командой:"
echo "  python3 check_token_reason.py 0xАДРЕС_ТОКЕНА"

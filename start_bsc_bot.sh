#!/bin/bash
# Скрипт для безопасного запуска BSC бота
# Останавливает старые экземпляры перед запуском нового

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "🚀 Запуск BSC бота (Pancakeswap)"
echo "=========================================="

# Проверяем наличие других экземпляров (ищем main.py в команде, независимо от пути к Python)
EXISTING_PIDS=$(ps aux | grep -E "[P]ython.*main\.py|[p]ython3.*main\.py|main\.py" | grep -v grep | grep -v "main_base.py" | awk '{print $2}' | tr '\n' ' ')

if [ -n "$EXISTING_PIDS" ]; then
    echo "⚠️  Обнаружены запущенные экземпляры:"
    ps -p $EXISTING_PIDS -o pid,start,command 2>/dev/null || true
    echo ""
    echo "🛑 Останавливаю старые экземпляры..."
    # Останавливаем по PID для надежности
    for pid in $EXISTING_PIDS; do
        kill $pid 2>/dev/null || true
    done
    sleep 2
    
    # Проверяем, что все остановлены
    REMAINING=$(ps aux | grep -E "[P]ython.*main\.py|[p]ython3.*main\.py|main\.py" | grep -v grep | grep -v "main_base.py" | awk '{print $2}' | tr '\n' ' ')
    if [ -n "$REMAINING" ]; then
        echo "❌ Не удалось остановить все экземпляры. Принудительная остановка..."
        for pid in $REMAINING; do
            kill -9 $pid 2>/dev/null || true
        done
        sleep 1
    fi
    echo "✅ Старые экземпляры остановлены"
else
    echo "✅ Других экземпляров не обнаружено"
fi

echo ""
echo "🚀 Запускаю BSC бот..."
echo ""

# Запускаем бот в фоне с перенаправлением вывода в лог
nohup python3 main.py >> new_tokens_bot.log 2>&1 &

BOT_PID=$!
sleep 2

# Проверяем, что бот запустился
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✅ BSC бот успешно запущен (PID: $BOT_PID)"
    echo "📋 Просмотр логов: tail -f new_tokens_bot.log"
    echo "🛑 Остановка: kill $BOT_PID"
else
    echo "❌ Ошибка: бот не запустился. Проверьте логи: tail -20 new_tokens_bot.log"
    exit 1
fi

echo "=========================================="




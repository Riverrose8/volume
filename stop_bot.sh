#!/bin/bash
# Скрипт для остановки BSC бота
# Ищет и останавливает все процессы main.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "🛑 Остановка BSC бота"
echo "=========================================="

# Ищем все процессы main.py (исключая main_base.py)
EXISTING_PIDS=$(ps aux | grep -E "[P]ython.*main\.py|[p]ython3.*main\.py|main\.py" | grep -v grep | grep -v "main_base.py" | awk '{print $2}' | tr '\n' ' ')

if [ -n "$EXISTING_PIDS" ]; then
    echo "⚠️  Обнаружены запущенные экземпляры:"
    ps -p $EXISTING_PIDS -o pid,start,command 2>/dev/null || true
    echo ""
    echo "🛑 Останавливаю процессы..."
    
    # Останавливаем по PID
    for pid in $EXISTING_PIDS; do
        echo "   Останавливаю PID: $pid"
        kill $pid 2>/dev/null || true
    done
    
    sleep 3
    
    # Проверяем, что все остановлены
    REMAINING=$(ps aux | grep -E "[P]ython.*main\.py|[p]ython3.*main\.py|main\.py" | grep -v grep | grep -v "main_base.py" | awk '{print $2}' | tr '\n' ' ')
    
    if [ -n "$REMAINING" ]; then
        echo "❌ Некоторые процессы не остановились. Принудительная остановка..."
        for pid in $REMAINING; do
            echo "   Принудительно останавливаю PID: $pid"
            kill -9 $pid 2>/dev/null || true
        done
        sleep 1
    fi
    
    # Финальная проверка
    FINAL_CHECK=$(ps aux | grep -E "[P]ython.*main\.py|[p]ython3.*main\.py|main\.py" | grep -v grep | grep -v "main_base.py" | awk '{print $2}' | tr '\n' ' ')
    
    if [ -z "$FINAL_CHECK" ]; then
        echo "✅ Все процессы бота остановлены"
    else
        echo "⚠️  Предупреждение: некоторые процессы все еще работают: $FINAL_CHECK"
        echo "   Попробуйте остановить вручную: kill -9 $FINAL_CHECK"
    fi
else
    echo "ℹ️  Запущенных экземпляров main.py не обнаружено"
    echo ""
    echo "Проверяю другие возможные процессы..."
    
    # Проверяем процессы через nohup
    NOHUP_PIDS=$(ps aux | grep -E "[n]ohup.*main\.py" | grep -v grep | awk '{print $2}' | tr '\n' ' ')
    if [ -n "$NOHUP_PIDS" ]; then
        echo "⚠️  Найдены процессы через nohup: $NOHUP_PIDS"
        for pid in $NOHUP_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
        echo "✅ Процессы nohup остановлены"
    fi
fi

echo ""
echo "=========================================="
echo "📋 Для проверки запущенных процессов:"
echo "   ps aux | grep main.py | grep -v grep"
echo "=========================================="

#!/bin/bash
# Установка systemd-сервиса для BSC бота (main.py)
# Запускать на сервере: bash install-bsc-systemd.sh
# Или с локальной машины: scp deploy/* ubuntu@SERVER:~/pancake-bot/deploy/ && ssh ubuntu@SERVER 'cd ~/pancake-bot/deploy && bash install-bsc-systemd.sh'

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="pancake-bsc"
UNIT_FILE="$SCRIPT_DIR/pancake-bsc.service"

echo "=========================================="
echo "  Установка systemd: $SERVICE_NAME (BSC бот)"
echo "=========================================="

if [ ! -f "$UNIT_FILE" ]; then
    echo "❌ Файл не найден: $UNIT_FILE"
    exit 1
fi

# Останавливаем старые процессы main.py (только BSC, не main_base.py)
echo ""
echo "1️⃣ Останавливаю старые инстансы BSC (main.py)..."
if pkill -f ' main.py' 2>/dev/null; then
    echo "   Остановлены процессы main.py"
    sleep 2
else
    echo "   Запущенных main.py не было"
fi

# Копируем unit в systemd
echo ""
echo "2️⃣ Копирую unit в /etc/systemd/system/..."
sudo cp "$UNIT_FILE" /etc/systemd/system/$SERVICE_NAME.service
sudo chmod 644 /etc/systemd/system/$SERVICE_NAME.service

# Перезагружаем конфигурацию systemd
echo ""
echo "3️⃣ systemctl daemon-reload..."
sudo systemctl daemon-reload

# Включаем автозапуск
echo ""
echo "4️⃣ Включаю автозапуск (enable)..."
sudo systemctl enable $SERVICE_NAME

# Запускаем сервис
echo ""
echo "5️⃣ Запускаю сервис (start)..."
sudo systemctl start $SERVICE_NAME

echo ""
echo "=========================================="
echo "  ✅ Готово"
echo "=========================================="
echo ""
echo "Полезные команды:"
echo "  Статус:    sudo systemctl status $SERVICE_NAME"
echo "  Логи:      sudo journalctl -u $SERVICE_NAME -f"
echo "  Рестарт:   sudo systemctl restart $SERVICE_NAME"
echo "  Стоп:      sudo systemctl stop $SERVICE_NAME"
echo "  Лог бота:  tail -f ~/pancake-bot/new_tokens_bot.log"
echo ""

sudo systemctl status $SERVICE_NAME --no-pager

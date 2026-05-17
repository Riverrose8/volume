#!/bin/bash
# Загружает main.py на сервер и перезапускает BSC бота (systemd).
# Использование: ./deploy/update-and-restart-bsc.sh [SERVER]
# Пример:     ./deploy/update-and-restart-bsc.sh 84.201.165.100

SERVER="${1:-84.201.165.100}"
USER="ubuntu"
PROJECT_DIR="~/pancake-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "  Обновление BSC бота на $USER@$SERVER"
echo "=========================================="
echo ""

echo "1️⃣ Загружаю main.py..."
scp -o ConnectTimeout=10 "$REPO_ROOT/main.py" "$USER@$SERVER:$PROJECT_DIR/main.py" || { echo "❌ Ошибка scp"; exit 1; }

echo ""
echo "2️⃣ Перезапускаю pancake-bsc..."
ssh -o ConnectTimeout=10 -l "$USER" "$SERVER" "sudo systemctl restart pancake-bsc" || { echo "❌ Ошибка restart"; exit 1; }

echo ""
echo "3️⃣ Статус сервиса:"
ssh -o ConnectTimeout=10 -l "$USER" "$SERVER" "sudo systemctl status pancake-bsc --no-pager -l" || true

echo ""
echo "=========================================="
echo "  ✅ Готово"
echo "=========================================="
echo "Лог бота: ssh $USER@$SERVER 'tail -f $PROJECT_DIR/new_tokens_bot.log'"

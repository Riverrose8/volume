#!/bin/bash
# Скрипт для мониторинга логов Base бота с фильтрацией важных событий

LOG_FILE="new_tokens_bot.log"

echo "🔍 Мониторинг логов Base бота..."
echo "📋 Отслеживаемые паттерны:"
echo "   - tg_send_with_dedup (вызовы отправки с дедупликацией)"
echo "   - mark_alerted (пометка токенов)"
echo "   - BLOCKED (блокировка дубликатов)"
echo "   - SKIP (пропуск уже отправленных)"
echo "   - LOCKED (блокировка через Lock)"
echo ""
echo "Нажмите Ctrl+C для выхода"
echo "=========================================="
echo ""

tail -f "$LOG_FILE" 2>/dev/null | grep --line-buffered -E "tg_send_with_dedup|mark_alerted|BLOCKED|SKIP|LOCKED|🔍|🔒|⏳|✅.*alerted" || {
    echo "❌ Ошибка: файл $LOG_FILE не найден или недоступен"
    exit 1
}


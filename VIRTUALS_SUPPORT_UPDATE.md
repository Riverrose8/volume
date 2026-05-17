# 🚀 Base Bot Update - USDC + Virtuals Support

## 🎯 Что добавлено

### ✅ USDC Pairs Support
- **Функция**: `fetch_dexscreener_usdc_pairs()`
- **Источник**: `dexscreener_usdc`
- **Алерт**: "🚀 Launchpad: USDC Pair"

### ✅ Virtuals Pairs Support  
- **Функция**: `fetch_dexscreener_virtuals_pairs()`
- **Источник**: `dexscreener_virtuals`
- **Алерт**: "🚀 Launchpad: Virtuals"

## 🔧 Технические детали

### Новые функции:
1. `fetch_dexscreener_virtuals_pairs()` - получает Virtuals пары
2. Обновлен `parse_dexscreener_pair()` - поддерживает Virtuals пары
3. Обновлена логика сканирования - включает Virtuals пары

### Обновленные источники:
- `dexscreener` - обычные пары
- `dexscreener_usdc` - USDC пары  
- `dexscreener_virtuals` - Virtuals пары

## 📋 Инструкции по обновлению

### Вариант 1: Автоматическое обновление (если SSH работает)
```bash
python3 update_base_bot_vps.py
```

### Вариант 2: Ручное обновление
1. Загрузите `base_bot_update.zip` на VPS
2. Распакуйте: `unzip base_bot_update.zip`
3. Создайте резервную копию: `cp main_base.py main_base.py.backup`
4. Замените файл: `cp base_bot_update/main_base.py ./`
5. Проверьте синтаксис: `python3 -m py_compile main_base.py`
6. Перезапустите: `systemctl restart base-bot`

### Вариант 3: Прямой скрипт на VPS
```bash
# Запустите на VPS
bash update_base_bot_direct.sh
```

## 🎯 Ожидаемые результаты

После обновления Base бот будет ловить:

### USDC Pairs:
- Токены, торгующиеся в USDC парах
- Те же фильтры качества
- "🚀 Launchpad: USDC Pair" в алертах

### Virtuals Pairs:
- Токены, торгующиеся в Virtuals парах  
- Те же фильтры качества
- "🚀 Launchpad: Virtuals" в алертах

## 🔍 Примеры алертов

### USDC Pair Alert:
```
🔵 Base Volume Alert 🔵

$TOKEN_NAME

🔥 150K volume in last 5 minutes
📈 MC (FDV): $500,000
💧 Liquidity: $50K
⌛️ Age: 2h 15m

🚀 Launchpad: USDC Pair

🔗 CA: 0x1234...
```

### Virtuals Pair Alert:
```
🔵 Base Volume Alert 🔵

$TOKEN_NAME

🔥 200K volume in last 5 minutes
📈 MC (FDV): $750,000
💧 Liquidity: $75K
⌛️ Age: 1h 30m

🚀 Launchpad: Virtuals

🔗 CA: 0x5678...
```

## 🚨 Troubleshooting

### Если бот не запускается:
```bash
# Восстановите резервную копию
cp main_base.py.backup main_base.py
systemctl restart base-bot
```

### Если Virtuals пары не обнаруживаются:
- Проверьте, что токены действительно торгуются в Virtuals парах
- Убедитесь, что DexScreener API работает
- Проверьте логи: `journalctl -u base-bot -f`

## 🎉 Готово!

Base бот теперь поддерживает:
- ✅ **USDC пары** (как CGN токен)
- ✅ **Virtuals пары** (новые возможности)
- ✅ **Те же фильтры качества** для всех типов пар
- ✅ **Правильные источники** в алертах

**Готов ловить токены, которые раньше пропускал!** 🚀

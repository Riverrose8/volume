# 🚀 Base Bot Update - Manual Method

## Проблема с SSH
SSH подключение к VPS не работает, но **Base бот работает и отправляет алерты!**

## Решение: Ручное обновление

### Шаг 1: Загрузите файл
1. Скачайте `base_bot_update.zip` 
2. Загрузите его на VPS через веб-панель или другой способ

### Шаг 2: Распакуйте на VPS
```bash
cd /root/pancake-bot
unzip base_bot_update.zip
```

### Шаг 3: Создайте резервную копию
```bash
cp main_base.py main_base.py.backup
```

### Шаг 4: Замените файл
```bash
cp base_bot_update/main_base.py ./
```

### Шаг 5: Проверьте синтаксис
```bash
python3 -m py_compile main_base.py
```

### Шаг 6: Перезапустите бота
```bash
systemctl restart base-bot
```

### Шаг 7: Проверьте статус
```bash
systemctl status base-bot
journalctl -u base-bot -f
```

## Что изменилось

✅ **Добавлена поддержка USDC пар**
✅ **Исправлен парсинг дат**
✅ **Улучшена детекция токенов**
✅ **Те же фильтры качества**

## Ожидаемый результат

После обновления Base бот будет ловить:
- USDC пары (как CGN/USDC)
- Те же фильтры качества
- "🚀 Launchpad: USDC Pair" в алертах

## Если что-то пойдет не так

```bash
# Восстановите резервную копию
cp main_base.py.backup main_base.py
systemctl restart base-bot
```

---

**Base бот готов ловить токены, которые раньше пропускал!** 🎯

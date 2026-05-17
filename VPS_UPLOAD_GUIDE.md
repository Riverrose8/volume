# 📤 Альтернативные способы загрузки base_bot_update.zip на VPS

## 🎯 Способ 1: Через локальный HTTP сервер (РЕКОМЕНДУЕТСЯ)

### На твоем компьютере:
1. **Запусти локальный сервер** (уже запущен на порту 8080)
2. **Открой браузер** и перейди на `http://localhost:8080`
3. **Убедись**, что видишь файл `base_bot_update.zip`

### На VPS:
```bash
cd /root/pancake-bot
wget http://31.173.87.187:8080/base_bot_update.zip
unzip base_bot_update.zip
cp main_base.py main_base.py.backup
cp base_bot_update/main_base.py ./
python3 -m py_compile main_base.py
systemctl restart base-bot
systemctl status base-bot
```

## 🎯 Способ 2: Через файлообменник

### Шаг 1: Загрузи файл на файлообменник
1. Перейди на **Google Drive**, **Dropbox** или **WeTransfer**
2. Загрузи файл `base_bot_update.zip`
3. Получи **прямую ссылку** на скачивание

### Шаг 2: Скачай на VPS
```bash
cd /root/pancake-bot
wget "ПРЯМАЯ_ССЫЛКА_НА_ФАЙЛ"
unzip base_bot_update.zip
cp main_base.py main_base.py.backup
cp base_bot_update/main_base.py ./
python3 -m py_compile main_base.py
systemctl restart base-bot
```

## 🎯 Способ 3: Через веб-панель VPS

### Если у тебя есть доступ к веб-панели:
1. **Зайди в панель управления VPS**
2. **Найди "Файловый менеджер"** или "File Manager"
3. **Перейди в папку** `/root/pancake-bot/`
4. **Загрузи файл** `base_bot_update.zip`
5. **Выполни команды** из способа 1

## 🎯 Способ 4: Через SFTP клиент

### Если у тебя есть SFTP клиент (FileZilla, WinSCP):
1. **Подключись к VPS** через SFTP
2. **Перейди в папку** `/root/pancake-bot/`
3. **Загрузи файл** `base_bot_update.zip`
4. **Выполни команды** из способа 1

## ⚠️ Важные моменты:

1. **Останови локальный сервер** после загрузки (Ctrl+C)
2. **Создай резервную копию** перед обновлением
3. **Проверь синтаксис** перед перезапуском
4. **Если что-то пойдет не так** - восстанови резервную копию

## 🔍 Проверка после обновления:

```bash
# Проверь логи
journalctl -u base-bot -f

# Ищи в логах:
# "DexScreener USDC: fetched X USDC Base pairs"
# "DexScreener Virtuals: fetched X Virtuals Base pairs"
```

---

**Выбери наиболее удобный для тебя способ!** 🚀

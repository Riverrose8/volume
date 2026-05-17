# Systemd для BSC бота (main.py)

Сервис **pancake-bsc** управляет одним инстансом BSC Pancake бота (`main.py`). BASE бот (main_base.py) не затрагивается.

## Установка на сервер

### Вариант 1: с локальной машины (рекомендуется)

Загрузить deploy и установить сервис (копировать по одной строке или блоком без строк с `#`):

```bash
scp deploy/pancake-bsc.service deploy/install-bsc-systemd.sh ubuntu@84.201.165.100:~/pancake-bot/deploy/
ssh -l ubuntu 84.201.165.100 "cd ~/pancake-bot/deploy && bash install-bsc-systemd.sh"
```

Для другого сервера замените `84.201.165.100` на свой хост.

### Вариант 2: уже на сервере

Если папка `deploy/` уже есть в `~/pancake-bot/`:

```bash
cd ~/pancake-bot/deploy
bash install-bsc-systemd.sh
```

## После установки

| Действие        | Команда |
|-----------------|--------|
| Статус          | `sudo systemctl status pancake-bsc` |
| Логи systemd    | `sudo journalctl -u pancake-bsc -f` |
| Лог бота (файл) | `tail -f ~/pancake-bot/new_tokens_bot.log` |
| Перезапуск      | `sudo systemctl restart pancake-bsc` |
| Остановка       | `sudo systemctl stop pancake-bsc` |
| Включить при загрузке | уже включён после `install-bsc-systemd.sh` |

## Обновление main.py и перезапуск

1. Загрузить новый `main.py` на сервер:
   ```bash
   scp main.py ubuntu@84.201.165.100:~/pancake-bot/main.py
   ```

2. Перезапустить только BSC бота:
   ```bash
   ssh -l ubuntu 84.201.165.100 "sudo systemctl restart pancake-bsc"
   ```

BASE бот при этом не перезапускается.

## Пути в unit

- Рабочая директория: `/home/ubuntu/pancake-bot`
- Python: `/home/ubuntu/pancake-bot/.venv/bin/python`
- Скрипт: `main.py` (из WorkingDirectory)
- Лог бота: `~/pancake-bot/new_tokens_bot.log` (пишет сам main.py)

Если на сервере другой пользователь или путь (например, не `ubuntu`), отредактируйте `deploy/pancake-bsc.service` перед установкой (User= и пути).

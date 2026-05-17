#!/usr/bin/env python3
"""
Скрипт для обновления Base бота на VPS
Добавляет поддержку USDC пар
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Выполняет команду и выводит результат"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        print(f"✅ {description} - успешно")
        if result.stdout:
            print(f"📤 Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ошибка")
        print(f"📤 Error: {e.stderr.strip()}")
        return False

def update_base_bot_vps():
    """Обновляет Base бот на VPS"""
    print("🚀 Обновление Base бота на VPS")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 Обновляем VPS: {vps_ip}")
    
    # Проверяем подключение
    if not run_command(f"ssh root@{vps_ip} 'echo test'", "Проверка SSH подключения"):
        print("❌ Не удается подключиться к VPS")
        return False
    
    # Проверяем, что Base бот существует
    if not run_command(f"ssh root@{vps_ip} 'test -f /root/pancake-bot/main_base.py'", "Проверка существования Base бота"):
        print("❌ Base бот не найден на VPS")
        return False
    
    # Создаем резервную копию
    if not run_command(f"ssh root@{vps_ip} 'cp /root/pancake-bot/main_base.py /root/pancake-bot/main_base.py.backup'", "Создание резервной копии"):
        print("❌ Не удалось создать резервную копию")
        return False
    
    # Останавливаем сервис
    run_command(f"ssh root@{vps_ip} 'systemctl stop base-bot'", "Остановка Base бота")
    
    # Копируем обновленный файл
    if not run_command(f"scp main_base.py root@{vps_ip}:/root/pancake-bot/", "Копирование обновленного файла"):
        print("❌ Не удалось скопировать файл")
        return False
    
    # Проверяем синтаксис Python
    if not run_command(f"ssh root@{vps_ip} 'cd /root/pancake-bot && python3 -m py_compile main_base.py'", "Проверка синтаксиса"):
        print("❌ Ошибка синтаксиса в обновленном файле")
        # Восстанавливаем резервную копию
        run_command(f"ssh root@{vps_ip} 'cp /root/pancake-bot/main_base.py.backup /root/pancake-bot/main_base.py'", "Восстановление резервной копии")
        return False
    
    # Запускаем сервис
    if not run_command(f"ssh root@{vps_ip} 'systemctl start base-bot'", "Запуск Base бота"):
        print("❌ Не удалось запустить Base бота")
        return False
    
    # Проверяем статус
    if not run_command(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", "Проверка статуса сервиса"):
        print("❌ Base бот не запустился")
        return False
    
    print("\n🎉 Обновление завершено успешно!")
    print("📊 Base бот теперь поддерживает USDC пары")
    print("🔍 Проверьте логи: ssh root@{vps_ip} 'journalctl -u base-bot -f'")
    
    return True

if __name__ == "__main__":
    try:
        success = update_base_bot_vps()
        if success:
            print("\n✅ Обновление Base бота завершено успешно!")
        else:
            print("\n❌ Обновление Base бота завершилось с ошибками")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Обновление прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)
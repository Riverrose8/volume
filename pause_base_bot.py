#!/usr/bin/env python3
"""
Скрипт для приостановки Base бота на 6 часов
"""

import subprocess
import sys
import time
from datetime import datetime, timedelta

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

def pause_base_bot():
    """Приостанавливает Base бот на 6 часов"""
    print("⏸️ Приостановка Base бота на 6 часов")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 VPS: {vps_ip}")
    
    # Проверяем подключение
    if not run_command(f"ssh root@{vps_ip} 'echo test'", "Проверка SSH подключения"):
        print("❌ Не удается подключиться к VPS")
        return False
    
    # Проверяем существование Base бота
    if not run_command(f"ssh root@{vps_ip} 'test -f /root/pancake-bot/main_base.py'", "Проверка существования Base бота"):
        print("❌ Base бот не найден на VPS")
        return False
    
    # Останавливаем сервис
    if not run_command(f"ssh root@{vps_ip} 'systemctl stop base-bot'", "Остановка Base бота"):
        print("❌ Не удалось остановить Base бота")
        return False
    
    # Создаем файл с временем возобновления
    resume_time = datetime.now() + timedelta(hours=6)
    resume_timestamp = int(resume_time.timestamp())
    
    print(f"⏰ Base бот будет возобновлен в: {resume_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Создаем скрипт для автоматического возобновления
    resume_script = f"""#!/bin/bash
# Скрипт автоматического возобновления Base бота
RESUME_TIME={resume_timestamp}

while true; do
    CURRENT_TIME=$(date +%s)
    if [ $CURRENT_TIME -ge $RESUME_TIME ]; then
        echo "$(date): Возобновление Base бота..."
        systemctl start base-bot
        echo "$(date): Base бот возобновлен"
        exit 0
    fi
    sleep 60  # Проверяем каждую минуту
done
"""
    
    # Загружаем скрипт на VPS
    print("📤 Загружаем скрипт возобновления...")
    try:
        with open("/tmp/resume_base_bot.sh", "w") as f:
            f.write(resume_script)
        
        # Копируем скрипт на VPS
        if not run_command(f"scp /tmp/resume_base_bot.sh root@{vps_ip}:/root/", "Копирование скрипта возобновления"):
            print("❌ Не удалось скопировать скрипт")
            return False
        
        # Делаем скрипт исполняемым
        if not run_command(f"ssh root@{vps_ip} 'chmod +x /root/resume_base_bot.sh'", "Установка прав на выполнение"):
            print("❌ Не удалось установить права")
            return False
        
        # Запускаем скрипт в фоне
        if not run_command(f"ssh root@{vps_ip} 'nohup /root/resume_base_bot.sh > /root/resume_bot.log 2>&1 &'", "Запуск скрипта возобновления"):
            print("❌ Не удалось запустить скрипт возобновления")
            return False
        
        # Очищаем временный файл
        import os
        os.remove("/tmp/resume_base_bot.sh")
        
    except Exception as e:
        print(f"❌ Ошибка при создании скрипта: {e}")
        return False
    
    # Проверяем статус
    run_command(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", "Проверка статуса сервиса")
    
    print("\n🎉 Base бот успешно приостановлен на 6 часов!")
    print(f"⏰ Автоматическое возобновление: {resume_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 Для ручного возобновления:")
    print(f"   ssh root@{vps_ip} 'systemctl start base-bot'")
    print("📋 Для проверки логов возобновления:")
    print(f"   ssh root@{vps_ip} 'tail -f /root/resume_bot.log'")
    
    return True

def resume_base_bot():
    """Возобновляет Base бот немедленно"""
    print("▶️ Немедленное возобновление Base бота")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 VPS: {vps_ip}")
    
    # Проверяем подключение
    if not run_command(f"ssh root@{vps_ip} 'echo test'", "Проверка SSH подключения"):
        print("❌ Не удается подключиться к VPS")
        return False
    
    # Останавливаем скрипт возобновления
    run_command(f"ssh root@{vps_ip} 'pkill -f resume_base_bot.sh'", "Остановка скрипта возобновления")
    
    # Запускаем Base бот
    if not run_command(f"ssh root@{vps_ip} 'systemctl start base-bot'", "Запуск Base бота"):
        print("❌ Не удалось запустить Base бота")
        return False
    
    # Проверяем статус
    run_command(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", "Проверка статуса сервиса")
    
    print("\n🎉 Base бот успешно возобновлен!")
    return True

def main():
    """Главная функция"""
    print("⏸️ Управление Base ботом")
    print("=" * 30)
    print("1. Приостановить на 6 часов")
    print("2. Возобновить немедленно")
    print("3. Выход")
    
    choice = input("\nВыберите действие (1-3): ").strip()
    
    if choice == "1":
        success = pause_base_bot()
        if success:
            print("\n✅ Base бот приостановлен на 6 часов!")
        else:
            print("\n❌ Не удалось приостановить Base бота")
            sys.exit(1)
    elif choice == "2":
        success = resume_base_bot()
        if success:
            print("\n✅ Base бот возобновлен!")
        else:
            print("\n❌ Не удалось возобновить Base бота")
            sys.exit(1)
    elif choice == "3":
        print("👋 До свидания!")
        return
    else:
        print("❌ Неверный выбор")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)









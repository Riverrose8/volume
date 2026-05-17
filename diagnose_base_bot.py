#!/usr/bin/env python3
"""
Диагностика проблем с Base ботом на VPS
"""

import subprocess
import sys

def run_command(cmd, description):
    """Выполняет команду и выводит результат"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        print(f"✅ {description} - успешно")
        if result.stdout:
            print(f"📤 Output: {result.stdout.strip()}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ошибка")
        print(f"📤 Error: {e.stderr.strip()}")
        return False, e.stderr

def diagnose_base_bot():
    """Диагностирует проблемы с Base ботом"""
    print("🔍 Диагностика Base бота на VPS")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 VPS: {vps_ip}")
    
    # 1. Проверяем SSH подключение
    print("\n1️⃣ Проверка SSH подключения...")
    success, output = run_command(f"ssh root@{vps_ip} 'echo SSH_OK'", "SSH подключение")
    if not success:
        print("❌ Не удается подключиться к VPS")
        return False
    
    # 2. Проверяем существование Base бота
    print("\n2️⃣ Проверка существования Base бота...")
    success, output = run_command(f"ssh root@{vps_ip} 'test -f /root/pancake-bot/main_base.py && echo FILE_EXISTS'", "Проверка файла")
    if not success:
        print("❌ Base бот не найден на VPS")
        return False
    
    # 3. Проверяем статус сервиса
    print("\n3️⃣ Проверка статуса сервиса...")
    success, output = run_command(f"ssh root@{vps_ip} 'systemctl status base-bot --no-pager'", "Статус сервиса")
    if not success:
        print("❌ Проблема с сервисом base-bot")
    
    # 4. Проверяем, запущен ли сервис
    print("\n4️⃣ Проверка активности сервиса...")
    success, output = run_command(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", "Активность сервиса")
    if success and "active" in output:
        print("✅ Base бот запущен")
        
        # Пробуем остановить
        print("\n5️⃣ Попытка остановки...")
        success, output = run_command(f"ssh root@{vps_ip} 'systemctl stop base-bot'", "Остановка сервиса")
        if success:
            print("✅ Base бот успешно остановлен")
        else:
            print("❌ Не удалось остановить Base бот")
            # Проверяем логи для диагностики
            print("\n6️⃣ Проверка логов сервиса...")
            run_command(f"ssh root@{vps_ip} 'journalctl -u base-bot --no-pager -n 20'", "Последние логи")
    else:
        print("ℹ️ Base бот не запущен")
    
    # 5. Проверяем права доступа
    print("\n7️⃣ Проверка прав доступа...")
    run_command(f"ssh root@{vps_ip} 'ls -la /root/pancake-bot/main_base.py'", "Права на файл")
    
    # 6. Проверяем синтаксис Python файла
    print("\n8️⃣ Проверка синтаксиса Python...")
    success, output = run_command(f"ssh root@{vps_ip} 'cd /root/pancake-bot && python3 -m py_compile main_base.py'", "Синтаксис Python")
    if not success:
        print("❌ Ошибка синтаксиса в main_base.py")
    
    # 7. Проверяем зависимости
    print("\n9️⃣ Проверка зависимостей...")
    run_command(f"ssh root@{vps_ip} 'cd /root/pancake-bot && python3 -c \"import aiohttp, asyncio; print(\'Dependencies OK\')\"'", "Проверка зависимостей")
    
    print("\n🎯 Диагностика завершена!")
    return True

def fix_base_bot():
    """Пытается исправить проблемы с Base ботом"""
    print("\n🔧 Попытка исправления проблем...")
    
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    # 1. Перезагружаем systemd
    print("\n1️⃣ Перезагрузка systemd...")
    run_command(f"ssh root@{vps_ip} 'systemctl daemon-reload'", "Перезагрузка systemd")
    
    # 2. Проверяем конфигурацию сервиса
    print("\n2️⃣ Проверка конфигурации сервиса...")
    run_command(f"ssh root@{vps_ip} 'systemctl cat base-bot'", "Конфигурация сервиса")
    
    # 3. Пробуем запустить сервис
    print("\n3️⃣ Попытка запуска сервиса...")
    success, output = run_command(f"ssh root@{vps_ip} 'systemctl start base-bot'", "Запуск сервиса")
    if success:
        print("✅ Base бот успешно запущен")
        
        # Проверяем статус
        run_command(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", "Проверка статуса")
    else:
        print("❌ Не удалось запустить Base бот")
    
    return True

def main():
    """Главная функция"""
    print("🔍 Диагностика и исправление Base бота")
    print("=" * 40)
    print("1. Диагностика проблем")
    print("2. Попытка исправления")
    print("3. Выход")
    
    choice = input("\nВыберите действие (1-3): ").strip()
    
    if choice == "1":
        success = diagnose_base_bot()
        if success:
            print("\n✅ Диагностика завершена!")
        else:
            print("\n❌ Диагностика завершилась с ошибками")
            sys.exit(1)
    elif choice == "2":
        success = fix_base_bot()
        if success:
            print("\n✅ Попытка исправления завершена!")
        else:
            print("\n❌ Исправление завершилось с ошибками")
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









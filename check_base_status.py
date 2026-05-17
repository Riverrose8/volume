#!/usr/bin/env python3
"""
Быстрая проверка статуса Base бота
"""

import subprocess
import sys

def check_base_bot_status():
    """Проверяет статус Base бота"""
    print("🔍 Проверка статуса Base бота")
    print("=" * 40)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 VPS: {vps_ip}")
    
    # Проверяем SSH подключение
    print("\n🔄 Проверка SSH подключения...")
    
    # Пробуем разные пользователи
    users_to_try = ['ubuntu', 'root']
    ssh_user = None
    
    for user in users_to_try:
        try:
            result = subprocess.run(f"ssh {user}@{vps_ip} 'echo SSH_OK'", 
                                  shell=True, capture_output=True, text=True, check=True)
            print(f"✅ SSH подключение работает (пользователь: {user})")
            ssh_user = user
            break
        except subprocess.CalledProcessError as e:
            print(f"❌ Не удается подключиться как {user}: {e.stderr.strip()}")
            continue
    
    if not ssh_user:
        print("❌ Не удается подключиться к VPS ни с одним пользователем")
        return False
    
    # Проверяем статус сервиса
    print("\n🔄 Проверка статуса сервиса...")
    try:
        result = subprocess.run(f"ssh {ssh_user}@{vps_ip} 'systemctl is-active base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        status = result.stdout.strip()
        if status == "active":
            print("✅ Base бот ЗАПУЩЕН (active)")
            bot_running = True
        elif status == "inactive":
            print("⏸️ Base бот ОСТАНОВЛЕН (inactive)")
            bot_running = False
        else:
            print(f"⚠️ Неизвестный статус: {status}")
            bot_running = False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка проверки статуса: {e.stderr.strip()}")
        bot_running = False
    
    # Проверяем процессы
    print("\n🔄 Проверка процессов Base бота...")
    try:
        result = subprocess.run(f"ssh {ssh_user}@{vps_ip} 'ps aux | grep main_base.py | grep -v grep'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            print("✅ Процессы Base бота запущены:")
            print(f"   {result.stdout.strip()}")
            processes_running = True
        else:
            print("⏸️ Процессы Base бота не найдены")
            processes_running = False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка проверки процессов: {e.stderr.strip()}")
        processes_running = False
    
    # Проверяем последние логи
    print("\n🔄 Проверка последних логов...")
    try:
        result = subprocess.run(f"ssh {ssh_user}@{vps_ip} 'journalctl -u base-bot --no-pager -n 5'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            print("📋 Последние логи:")
            for line in result.stdout.strip().split('\n')[-3:]:  # Последние 3 строки
                print(f"   {line}")
        else:
            print("ℹ️ Логи не найдены")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка получения логов: {e.stderr.strip()}")
    
    # Итоговый статус
    print(f"\n🎯 ИТОГОВЫЙ СТАТУС:")
    if bot_running and processes_running:
        print("✅ Base бот ПОЛНОСТЬЮ ЗАПУЩЕН")
        print("   - Сервис активен")
        print("   - Процессы работают")
        print("   - Бот сканирует токены")
    elif bot_running and not processes_running:
        print("⚠️ Base бот ЧАСТИЧНО ЗАПУЩЕН")
        print("   - Сервис активен")
        print("   - Процессы не найдены")
        print("   - Возможны проблемы")
    elif not bot_running and processes_running:
        print("⚠️ Base бот ЧАСТИЧНО ОСТАНОВЛЕН")
        print("   - Сервис неактивен")
        print("   - Процессы все еще работают")
        print("   - Нужна принудительная остановка")
    else:
        print("⏸️ Base бот ПОЛНОСТЬЮ ОСТАНОВЛЕН")
        print("   - Сервис неактивен")
        print("   - Процессы не работают")
        print("   - Бот не сканирует токены")
    
    return bot_running

if __name__ == "__main__":
    try:
        check_base_bot_status()
    except KeyboardInterrupt:
        print("\n⏹️ Проверка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)

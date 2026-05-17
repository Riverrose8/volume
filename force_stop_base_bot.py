#!/usr/bin/env python3
"""
Принудительная остановка Base бота
"""

import subprocess
import sys

def force_stop_base_bot():
    """Принудительно останавливает Base бот"""
    print("🛑 Принудительная остановка Base бота")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 VPS: {vps_ip}")
    
    # Проверяем подключение
    print("🔄 Проверка SSH подключения...")
    try:
        result = subprocess.run(f"ssh root@{vps_ip} 'echo test'", 
                              shell=True, capture_output=True, text=True, check=True)
        print("✅ SSH подключение работает")
    except subprocess.CalledProcessError as e:
        print(f"❌ Не удается подключиться к VPS: {e.stderr.strip()}")
        return False
    
    # Метод 1: Обычная остановка сервиса
    print("\n1️⃣ Попытка обычной остановки сервиса...")
    try:
        result = subprocess.run(f"ssh root@{vps_ip} 'systemctl stop base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        print("✅ Сервис остановлен через systemctl")
        
        # Проверяем статус
        result = subprocess.run(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        if "inactive" in result.stdout:
            print("✅ Base бот успешно остановлен!")
            return True
        else:
            print(f"⚠️ Статус: {result.stdout.strip()}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка остановки сервиса: {e.stderr.strip()}")
    
    # Метод 2: Принудительное завершение процессов
    print("\n2️⃣ Поиск и завершение процессов Base бота...")
    try:
        # Ищем процессы Python с main_base.py
        result = subprocess.run(f"ssh root@{vps_ip} 'ps aux | grep main_base.py | grep -v grep'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            print(f"🔍 Найдены процессы: {result.stdout.strip()}")
            
            # Завершаем процессы
            result = subprocess.run(f"ssh root@{vps_ip} 'pkill -f main_base.py'", 
                                  shell=True, capture_output=True, text=True, check=True)
            print("✅ Процессы Base бота завершены")
        else:
            print("ℹ️ Процессы Base бота не найдены")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка завершения процессов: {e.stderr.strip()}")
    
    # Метод 3: Проверка и отключение сервиса
    print("\n3️⃣ Отключение сервиса...")
    try:
        result = subprocess.run(f"ssh root@{vps_ip} 'systemctl disable base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        print("✅ Сервис отключен")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка отключения сервиса: {e.stderr.strip()}")
    
    # Финальная проверка
    print("\n4️⃣ Финальная проверка...")
    try:
        result = subprocess.run(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        if "inactive" in result.stdout:
            print("✅ Base бот полностью остановлен!")
            return True
        else:
            print(f"⚠️ Статус сервиса: {result.stdout.strip()}")
            
        # Проверяем процессы
        result = subprocess.run(f"ssh root@{vps_ip} 'ps aux | grep main_base.py | grep -v grep'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        if not result.stdout.strip():
            print("✅ Процессы Base бота не запущены!")
            return True
        else:
            print(f"⚠️ Процессы все еще запущены: {result.stdout.strip()}")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка финальной проверки: {e.stderr.strip()}")
    
    print("\n🎯 Принудительная остановка завершена!")
    print("📋 Для возобновления используйте:")
    print(f"   ssh root@{vps_ip} 'systemctl start base-bot'")
    
    return True

if __name__ == "__main__":
    try:
        success = force_stop_base_bot()
        if success:
            print("\n✅ Base бот принудительно остановлен!")
        else:
            print("\n❌ Не удалось полностью остановить Base бот")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)









#!/usr/bin/env python3
"""
Быстрая проверка статуса Base бота (упрощенная версия)
"""

import subprocess
import sys

def quick_status_check():
    """Быстрая проверка статуса Base бота"""
    print("🔍 Быстрая проверка статуса Base бота")
    print("=" * 40)
    
    vps_ip = "84.201.161.90"  # Ваш IP
    print(f"🎯 VPS: {vps_ip}")
    
    # Пробуем подключиться как ubuntu (как вы делали вручную)
    print("\n🔄 Проверка SSH подключения как ubuntu...")
    try:
        result = subprocess.run(f"ssh ubuntu@{vps_ip} 'echo SSH_OK'", 
                              shell=True, capture_output=True, text=True, check=True)
        print("✅ SSH подключение работает (ubuntu)")
        ssh_user = "ubuntu"
    except subprocess.CalledProcessError as e:
        print(f"❌ Не удается подключиться как ubuntu: {e.stderr.strip()}")
        return False
    
    # Проверяем статус сервиса
    print("\n🔄 Проверка статуса сервиса base-bot...")
    try:
        result = subprocess.run(f"ssh {ssh_user}@{vps_ip} 'systemctl is-active base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        
        status = result.stdout.strip()
        if status == "active":
            print("✅ Base бот ЗАПУЩЕН!")
            return True
        elif status == "inactive":
            print("⏸️ Base бот ОСТАНОВЛЕН!")
            return False
        else:
            print(f"⚠️ Неизвестный статус: {status}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка проверки статуса: {e.stderr.strip()}")
        
        # Возможно, сервис не существует или нет прав
        print("\n🔄 Проверка существования сервиса...")
        try:
            result = subprocess.run(f"ssh {ssh_user}@{vps_ip} 'systemctl list-units --type=service | grep base-bot'", 
                                  shell=True, capture_output=True, text=True, check=True)
            if result.stdout.strip():
                print("✅ Сервис base-bot существует")
            else:
                print("❌ Сервис base-bot не найден")
        except subprocess.CalledProcessError:
            print("❌ Не удается проверить существование сервиса")
        
        return False

if __name__ == "__main__":
    try:
        is_running = quick_status_check()
        if is_running:
            print("\n🎉 Base бот работает!")
        else:
            print("\n⏸️ Base бот остановлен!")
    except KeyboardInterrupt:
        print("\n⏹️ Проверка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)









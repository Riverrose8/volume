#!/usr/bin/env python3
"""
Быстрая приостановка Base бота на 6 часов
"""

import subprocess
import sys
from datetime import datetime, timedelta

def pause_base_bot_quick():
    """Быстрая приостановка Base бота на 6 часов"""
    print("⏸️ Быстрая приостановка Base бота на 6 часов")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 VPS: {vps_ip}")
    
    # Останавливаем Base бот
    print("🔄 Остановка Base бота...")
    try:
        result = subprocess.run(f"ssh root@{vps_ip} 'systemctl stop base-bot'", 
                              shell=True, capture_output=True, text=True, check=True)
        print("✅ Base бот остановлен")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка остановки: {e.stderr.strip()}")
        return False
    
    # Создаем задачу на возобновление через 6 часов
    resume_time = datetime.now() + timedelta(hours=6)
    print(f"⏰ Base бот будет возобновлен в: {resume_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Создаем команду для возобновления
    resume_cmd = f"ssh root@{vps_ip} 'systemctl start base-bot'"
    
    print(f"\n📋 Для ручного возобновления выполните:")
    print(f"   {resume_cmd}")
    
    print(f"\n📋 Или используйте скрипт:")
    print(f"   python3 pause_base_bot.py")
    print(f"   (выберите опцию 2)")
    
    print(f"\n🎉 Base бот приостановлен на 6 часов!")
    return True

if __name__ == "__main__":
    try:
        success = pause_base_bot_quick()
        if success:
            print("\n✅ Операция завершена успешно!")
        else:
            print("\n❌ Операция завершилась с ошибками")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Операция прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)









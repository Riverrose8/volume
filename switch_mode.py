#!/usr/bin/env python3
"""
Скрипт для переключения между продакшн и тестовым режимом бота
"""

import os
import sys
from dotenv import load_dotenv

def switch_mode(mode):
    """Переключает режим бота"""
    load_dotenv()
    
    if mode == "test":
        # Включаем тестовый режим
        os.environ["TEST_MODE"] = "true"
        print("🧪 Включен ТЕСТОВЫЙ режим")
        print("📱 Алерты будут отправляться в тестовый канал: @pancakeswapvolume")
        
    elif mode == "prod":
        # Включаем продакшн режим
        os.environ["TEST_MODE"] = "false"
        print("🚀 Включен ПРОДАКШН режим")
        print("📱 Алерты будут отправляться в основной канал")
        
    else:
        print("❌ Неверный режим. Используйте: test или prod")
        return False
    
    # Обновляем .env файл
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Обновляем или добавляем TEST_MODE
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("TEST_MODE="):
                lines[i] = f"TEST_MODE={mode == 'test'}\n"
                updated = True
                break
        
        if not updated:
            lines.append(f"TEST_MODE={mode == 'test'}\n")
        
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        print(f"✅ Обновлен файл .env")
        return True
    else:
        print("❌ Файл .env не найден")
        return False

def show_status():
    """Показывает текущий статус"""
    load_dotenv()
    
    test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
    test_chat = os.getenv("TELEGRAM_TEST_CHAT_ID", "")
    prod_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    
    print("📊 Текущий статус бота:")
    print(f"🧪 Тестовый режим: {'ВКЛЮЧЕН' if test_mode else 'ВЫКЛЮЧЕН'}")
    print(f"📱 Основной канал: {prod_chat}")
    print(f"🧪 Тестовый канал: {test_chat}")
    
    if test_mode:
        print("⚠️  ВНИМАНИЕ: Бот работает в тестовом режиме!")
    else:
        print("✅ Бот работает в продакшн режиме")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 switch_mode.py test   - включить тестовый режим")
        print("  python3 switch_mode.py prod    - включить продакшн режим")
        print("  python3 switch_mode.py status  - показать текущий статус")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "status":
        show_status()
    elif command in ["test", "prod"]:
        if switch_mode(command):
            print(f"\n🔄 Перезапустите бота для применения изменений:")
            print("   sudo systemctl restart pancake-bot")
    else:
        print("❌ Неверная команда. Используйте: test, prod или status")


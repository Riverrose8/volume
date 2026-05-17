#!/usr/bin/env python3
"""
Быстрая проверка статуса Base бота на VPS
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
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ошибка")
        print(f"📤 Error: {e.stderr.strip()}")
        return False

def check_vps_status():
    """Проверяет статус VPS"""
    print("🔍 Проверка статуса Base бота на VPS")
    print("=" * 50)
    
    # Получаем IP VPS
    vps_ip = input("Введите IP адрес VPS: ").strip()
    if not vps_ip:
        print("❌ IP адрес не может быть пустым")
        return False
    
    print(f"🎯 Проверяем VPS: {vps_ip}")
    
    # Проверяем подключение
    if not run_command(f"ssh root@{vps_ip} 'echo test'", "Проверка SSH подключения"):
        print("❌ Не удается подключиться к VPS")
        return False
    
    # Проверяем существование Base бота
    if not run_command(f"ssh root@{vps_ip} 'test -f /root/pancake-bot/main_base.py'", "Проверка существования Base бота"):
        print("❌ Base бот не найден на VPS")
        return False
    
    # Проверяем статус сервиса
    if not run_command(f"ssh root@{vps_ip} 'systemctl is-active base-bot'", "Проверка статуса сервиса"):
        print("❌ Base бот не запущен")
        return False
    
    # Проверяем логи
    print("\n📊 Последние логи Base бота:")
    run_command(f"ssh root@{vps_ip} 'journalctl -u base-bot -n 10 --no-pager'", "Получение последних логов")
    
    # Проверяем поддержку USDC
    print("\n🔍 Проверка поддержки USDC пар:")
    run_command(f"ssh root@{vps_ip} 'grep -n \"fetch_dexscreener_usdc_pairs\" /root/pancake-bot/main_base.py'", "Проверка функции USDC пар")
    
    print("\n✅ Проверка завершена!")
    return True

if __name__ == "__main__":
    try:
        success = check_vps_status()
        if success:
            print("\n✅ VPS статус проверен успешно!")
        else:
            print("\n❌ Проверка VPS завершилась с ошибками")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Проверка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)
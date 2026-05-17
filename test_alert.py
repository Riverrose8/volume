#!/usr/bin/env python3
"""
Тестовый алерт для проверки Telegram бота
"""
import asyncio
import aiohttp
import os
import sys

# Добавляем текущую директорию в путь
sys.path.append('.')

from main import tg_send

async def send_test_alert():
    """Отправляем тестовый алерт"""
    print("🚀 Отправляем тестовый алерт...")
    
    # Тестовое сообщение
    test_message = """
🚀 **ТЕСТОВЫЙ АЛЕРТ** 🚀

**Токен:** TEST (Test Token)
**Адрес:** `0x1234...5678`
**Объем 5м:** $500,000
**Возраст:** 0.5 часа
**Источник:** Test

📊 **Данные DexTools:**
• **Holders:** 150
• **Market Cap:** $2.5M
• **Liquidity:** $800K
• **DEXT Score:** 85/100
• **Top 10:** 12.5%
• **Tax:** 1.5%/2.0%
• **Honeypot:** ❌ Нет

🔗 **Ссылки:**
• Website: https://testtoken.com
• Telegram: https://t.me/testtoken
• Twitter: https://twitter.com/testtoken

---
*Это тестовое сообщение для проверки работы бота*
    """
    
    try:
        async with aiohttp.ClientSession() as session:
            # Отправляем тестовый алерт
            success = await tg_send(session, test_message)
            if success:
                print("✅ Тестовый алерт отправлен успешно!")
            else:
                print("❌ Ошибка отправки алерта")
                
    except Exception as e:
        print(f"❌ Ошибка отправки алерта: {e}")

if __name__ == "__main__":
    asyncio.run(send_test_alert())

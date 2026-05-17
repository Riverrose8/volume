#!/usr/bin/env python3
"""
Тест Apify GMGN Token Stat Scraper
Проверяет, какие данные возвращает актор для BSC токена
Особенно интересуют: bundler %, total fees
"""

import asyncio
import aiohttp
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Apify API credentials
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_ID = "muhammetakkurtt~gmgn-token-stat-scraper"  # ВАЖНО: используем ~ вместо / в URL

async def test_apify_gmgn_token_stat(token_address: str):
    """Тестирует GMGN Token Stat Scraper через Apify API"""
    
    if not APIFY_API_TOKEN:
        print("❌ APIFY_API_TOKEN not set in .env")
        print("   Get your token from: https://console.apify.com/account/integrations")
        print("   Set it with: export APIFY_API_TOKEN=your_token_here")
        return None
    
    print(f"🧪 Тестирование Apify GMGN Token Stat Scraper")
    print(f"   Token: {token_address}")
    print(f"   Actor: {ACTOR_ID}")
    print("=" * 60)
    
    # Apify API endpoints
    base_url = "https://api.apify.com/v2"
    headers = {
        "Authorization": f"Bearer {APIFY_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Input для актора
    input_data = {
        "tokenAddresses": [token_address],
        "chain": "bsc",
        "proxyConfiguration": {
            "useApifyProxy": True
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Запускаем актор
            print("\n1️⃣ Запуск актора...")
            run_url = f"{base_url}/acts/{ACTOR_ID}/runs"
            
            async with session.post(run_url, headers=headers, json=input_data, timeout=30) as resp:
                if resp.status != 201:
                    error_text = await resp.text()
                    print(f"   ❌ Ошибка запуска: HTTP {resp.status}")
                    print(f"   Ответ: {error_text[:500]}")
                    return None
                
                run_data = await resp.json()
                run_id = run_data["data"]["id"]
                print(f"   ✅ Актор запущен (Run ID: {run_id})")
            
            # Ждем завершения (максимум 5 минут)
            print("\n2️⃣ Ожидание завершения...")
            status_url = f"{base_url}/actor-runs/{run_id}"
            max_wait = 300  # 5 минут
            waited = 0
            
            while waited < max_wait:
                await asyncio.sleep(5)
                waited += 5
                
                async with session.get(status_url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        status_data = await resp.json()
                        status = status_data["data"]["status"]
                        print(f"   Статус: {status} (ждем {waited}s)")
                        
                        if status == "SUCCEEDED":
                            print("   ✅ Актор завершился успешно!")
                            break
                        elif status == "FAILED":
                            print("   ❌ Актор завершился с ошибкой")
                            return None
                        elif status == "ABORTED":
                            print("   ⚠️ Актор был прерван")
                            return None
                    else:
                        print(f"   ⚠️ Ошибка проверки статуса: HTTP {resp.status}")
            
            if waited >= max_wait:
                print("   ⚠️ Таймаут ожидания")
                return None
            
            # Получаем результаты
            print("\n3️⃣ Получение результатов...")
            dataset_url = f"{base_url}/actor-runs/{run_id}/dataset/items"
            
            async with session.get(dataset_url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    print(f"   ❌ Ошибка получения данных: HTTP {resp.status}")
                    return None
                
                results = await resp.json()
                
                if not results:
                    print("   ⚠️ Нет результатов")
                    return None
                
                print(f"   ✅ Получено {len(results)} записей")
                
                # Анализируем первую запись
                token_data = results[0]
                
                print("\n" + "=" * 60)
                print("📊 АНАЛИЗ ДАННЫХ:")
                print("=" * 60)
                
                # Основная информация
                print(f"\n✅ Основная информация:")
                print(f"   Address: {token_data.get('address', 'N/A')}")
                print(f"   Symbol: {token_data.get('symbol', 'N/A')}")
                print(f"   Name: {token_data.get('name', 'N/A')}")
                
                # Проверяем наличие bundler и total fees
                print(f"\n🔍 Поиск bundler % и total fees:")
                
                # Ищем bundler в разных местах
                bundler_found = False
                if 'bundler' in str(token_data).lower():
                    print("   ⚠️ Найдено упоминание 'bundler' в данных!")
                    # Пробуем найти точное значение
                    for key, value in token_data.items():
                        if 'bundler' in str(key).lower():
                            print(f"   ✅ Найдено поле: {key} = {value}")
                            bundler_found = True
                
                # Ищем total fees
                fees_found = False
                if 'fee' in str(token_data).lower() or 'cost' in str(token_data).lower():
                    print("   ⚠️ Найдено упоминание 'fee' или 'cost' в данных!")
                    for key, value in token_data.items():
                        if 'fee' in str(key).lower() or 'cost' in str(key).lower():
                            print(f"   ✅ Найдено поле: {key} = {value}")
                            fees_found = True
                
                if not bundler_found:
                    print("   ❌ Bundler % не найден в данных")
                if not fees_found:
                    print("   ❌ Total fees не найден в данных")
                
                # Показываем все доступные поля
                print(f"\n📋 Все доступные поля (первые 30):")
                fields = list(token_data.keys())[:30]
                for field in fields:
                    value = token_data.get(field)
                    if isinstance(value, (dict, list)):
                        print(f"   • {field}: {type(value).__name__} ({len(value) if hasattr(value, '__len__') else 'N/A'})")
                    else:
                        value_str = str(value)[:50] if value else "None"
                        print(f"   • {field}: {value_str}")
                
                if len(token_data.keys()) > 30:
                    print(f"   ... и еще {len(token_data.keys()) - 30} полей")
                
                # Сохраняем полный результат в файл
                output_file = f"apify_test_result_{token_address[:10]}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(token_data, f, indent=2, ensure_ascii=False)
                print(f"\n💾 Полные данные сохранены в: {output_file}")
                
                return token_data
                
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    # Тестируем на реальном токене (из вашего примера)
    test_token = "0x3f4604fcfea5ab65aa86f3640e647bbbd55fcce0"
    
    print("=" * 60)
    print("ТЕСТ APIFY GMGN TOKEN STAT SCRAPER")
    print("=" * 60)
    print(f"\nТестируем токен: {test_token}")
    print("Этот токен был в вашем примере со скриншота\n")
    
    result = asyncio.run(test_apify_gmgn_token_stat(test_token))
    
    if result:
        print("\n" + "=" * 60)
        print("✅ ТЕСТ ЗАВЕРШЕН")
        print("=" * 60)
        print("\nПроверьте файл с результатами для детального анализа.")
    else:
        print("\n" + "=" * 60)
        print("❌ ТЕСТ НЕ УДАЛСЯ")
        print("=" * 60)

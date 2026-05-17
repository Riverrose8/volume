#!/usr/bin/env python3
"""
Диагностика Apify GMGN с сервера: пошагово показывает, где падает запрос.
Запуск на сервере: cd ~/pancake-bot && .venv/bin/python test_apify_from_server.py
"""
import asyncio
import aiohttp
import os
import sys
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_ID = "muhammetakkurtt~gmgn-token-stat-scraper"
BASE_URL = "https://api.apify.com/v2"
TEST_TOKEN = "0x3f4604fcfea5ab65aa86f3640e647bbbd55fcce0"


async def main():
    print("=== Apify GMGN диагностика (с сервера) ===\n")
    if not APIFY_TOKEN:
        print("❌ APIFY_API_TOKEN не задан в .env")
        sys.exit(1)
    print(f"✅ APIFY_API_TOKEN задан (длина {len(APIFY_TOKEN)})")
    print(f"   Токен для проверки: {TEST_TOKEN}\n")

    headers = {
        "Authorization": f"Bearer {APIFY_TOKEN}",
        "Content-Type": "application/json",
    }
    input_data = {
        "tokenAddresses": [TEST_TOKEN],
        "chain": "bsc",
        "proxyConfiguration": {"useApifyProxy": True},
    }

    async with aiohttp.ClientSession() as session:
        # 1. Запуск актора
        print("1️⃣ POST /acts/.../runs ...")
        run_url = f"{BASE_URL}/acts/{ACTOR_ID}/runs"
        try:
            async with session.post(run_url, headers=headers, json=input_data, timeout=30) as resp:
                print(f"   HTTP {resp.status}")
                body = await resp.text()
                if resp.status != 201:
                    print(f"   ❌ Ошибка: {body[:400]}")
                    return
                import json
                data = json.loads(body)
                run_id = data["data"]["id"]
                print(f"   ✅ Run создан: run_id={run_id}\n")
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
            return

        # 2. Ожидание завершения
        print("2️⃣ Ожидание завершения run (poll каждые 3s, макс 120s) ...")
        status_url = f"{BASE_URL}/actor-runs/{run_id}"
        for step in range(40):
            await asyncio.sleep(3)
            try:
                async with session.get(status_url, headers=headers, timeout=10) as resp:
                    if resp.status != 200:
                        print(f"   HTTP {resp.status}")
                        continue
                    data = await resp.json()
                    status = data["data"]["status"]
                    print(f"   [{step*3}s] status={status}")
                    if status == "SUCCEEDED":
                        print("   ✅ Run успешен\n")
                        break
                    if status in ("FAILED", "ABORTED"):
                        print(f"   ❌ Run завершился с {status}")
                        if "data" in data and "statusMessage" in data.get("data", {}):
                            print(f"   Сообщение: {data['data'].get('statusMessage', '')[:200]}")
                        return
            except Exception as e:
                print(f"   Исключение при poll: {e}")
                continue
        else:
            print("   ❌ Таймаут 120s")
            return

        # 3. Получение dataset
        print("3️⃣ GET dataset/items ...")
        dataset_url = f"{BASE_URL}/actor-runs/{run_id}/dataset/items"
        try:
            async with session.get(dataset_url, headers=headers, timeout=10) as resp:
                print(f"   HTTP {resp.status}")
                if resp.status != 200:
                    print(f"   ❌ Тело: {(await resp.text())[:300]}")
                    return
                results = await resp.json()
                n = len(results) if isinstance(results, list) else 0
                print(f"   ✅ Записей в dataset: {n}")
                if n > 0:
                    first = results[0]
                    print(f"   Ключи первой записи: {list(first.keys())[:20]}")
                    print(f"   total_fee = {first.get('total_fee')}, totalFee = {first.get('totalFee')}")
                else:
                    print("   ❌ Dataset пустой — актор не вернул ни одной записи для этого токена.")
        except Exception as e:
            print(f"   ❌ Исключение: {e}")

    print("\n=== Конец диагностики ===")


if __name__ == "__main__":
    asyncio.run(main())

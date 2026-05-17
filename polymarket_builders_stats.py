#!/usr/bin/env python3
"""
Скрипт для сбора статистики по всем проектам экосистемы Polymarket Builders
Использует официальные API endpoints Polymarket
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
import csv

# API Endpoints
DATA_API_BASE = "https://data-api.polymarket.com/v1"
BUILDERS_LEADERBOARD_URL = f"{DATA_API_BASE}/builders/leaderboard"
BUILDERS_VOLUME_URL = f"{DATA_API_BASE}/builders/volume"

# Time periods для анализа
TIME_PERIODS = ["DAY", "WEEK", "MONTH", "ALL"]


class PolymarketBuildersStats:
    """Класс для сбора статистики по Polymarket Builders"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.all_builders_data = defaultdict(dict)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_builder_leaderboard(
        self, 
        time_period: str = "WEEK",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Получает агрегированный рейтинг builders
        
        Args:
            time_period: DAY, WEEK, MONTH, ALL
            limit: Максимальное количество результатов (0-50)
            offset: Смещение для пагинации (0-1000)
        """
        params = {
            "timePeriod": time_period,
            "limit": limit,
            "offset": offset
        }
        
        try:
            async with self.session.get(
                BUILDERS_LEADERBOARD_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"❌ Ошибка получения leaderboard: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ Исключение при получении leaderboard: {e}")
            return []
    
    async def fetch_all_builders_leaderboard(self, time_period: str = "WEEK") -> List[Dict]:
        """Получает всех builders с пагинацией"""
        all_builders = []
        offset = 0
        limit = 50
        
        while True:
            builders = await self.fetch_builder_leaderboard(
                time_period=time_period,
                limit=limit,
                offset=offset
            )
            
            if not builders:
                break
                
            all_builders.extend(builders)
            
            if len(builders) < limit:
                break
                
            offset += limit
            
            # Небольшая задержка для избежания rate limits
            await asyncio.sleep(0.5)
        
        return all_builders
    
    async def fetch_builder_volume_timeseries(
        self,
        time_period: str = "WEEK"
    ) -> List[Dict]:
        """
        Получает временные ряды объема для всех builders
        
        Args:
            time_period: DAY, WEEK, MONTH, ALL
        """
        params = {
            "timePeriod": time_period
        }
        
        try:
            async with self.session.get(
                BUILDERS_VOLUME_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"❌ Ошибка получения volume timeseries: {response.status}")
                    return []
        except Exception as e:
            print(f"❌ Исключение при получении volume timeseries: {e}")
            return []
    
    def aggregate_builder_stats(
        self,
        leaderboard_data: List[Dict],
        volume_timeseries: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Агрегирует статистику по каждому builder'у
        
        Returns:
            Dict с ключами - именами builders, значениями - статистикой
        """
        stats = {}
        
        # Обрабатываем leaderboard данные
        for builder in leaderboard_data:
            builder_name = builder.get("builder", "unknown")
            stats[builder_name] = {
                "name": builder_name,
                "rank": builder.get("rank", "N/A"),
                "volume": builder.get("volume", 0),
                "activeUsers": builder.get("activeUsers", 0),
                "verified": builder.get("verified", False),
                "builderLogo": builder.get("builderLogo", ""),
                "daily_volume": [],
                "daily_active_users": [],
                "volume_growth": 0,
                "total_volume_all_time": 0,
                "avg_daily_volume": 0,
                "max_daily_volume": 0,
                "days_active": 0
            }
        
        # Обрабатываем временные ряды
        builder_volumes = defaultdict(list)
        builder_users = defaultdict(list)
        
        for entry in volume_timeseries:
            builder_name = entry.get("builder", "unknown")
            dt = entry.get("dt", "")
            volume = entry.get("volume", 0)
            active_users = entry.get("activeUsers", 0)
            
            builder_volumes[builder_name].append({
                "date": dt,
                "volume": volume
            })
            builder_users[builder_name].append({
                "date": dt,
                "activeUsers": active_users
            })
        
        # Агрегируем метрики для каждого builder'а
        for builder_name in stats.keys():
            volumes = builder_volumes.get(builder_name, [])
            users = builder_users.get(builder_name, [])
            
            if volumes:
                # Сортируем по дате
                volumes.sort(key=lambda x: x["date"])
                users.sort(key=lambda x: x["date"])
                
                stats[builder_name]["daily_volume"] = volumes
                stats[builder_name]["daily_active_users"] = users
                
                # Вычисляем метрики
                total_volume = sum(v["volume"] for v in volumes)
                stats[builder_name]["total_volume_all_time"] = total_volume
                
                if len(volumes) > 0:
                    stats[builder_name]["avg_daily_volume"] = total_volume / len(volumes)
                    stats[builder_name]["max_daily_volume"] = max(v["volume"] for v in volumes)
                    stats[builder_name]["days_active"] = len(volumes)
                
                # Рост объема (сравниваем первую и последнюю неделю)
                if len(volumes) >= 7:
                    first_week_volume = sum(v["volume"] for v in volumes[:7])
                    last_week_volume = sum(v["volume"] for v in volumes[-7:])
                    if first_week_volume > 0:
                        stats[builder_name]["volume_growth"] = (
                            (last_week_volume - first_week_volume) / first_week_volume * 100
                        )
        
        return stats
    
    def save_to_json(self, data: Dict, filename: str = "polymarket_builders_stats.json"):
        """Сохраняет данные в JSON файл"""
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Данные сохранены в {filename}")
    
    def save_to_csv(self, stats: Dict[str, Dict], filename: str = "polymarket_builders_stats.csv"):
        """Сохраняет агрегированную статистику в CSV"""
        rows = []
        
        for builder_name, data in sorted(
            stats.items(),
            key=lambda x: x[1].get("volume", 0),
            reverse=True
        ):
            rows.append({
                "Rank": data.get("rank", "N/A"),
                "Builder Name": builder_name,
                "Verified": "Yes" if data.get("verified") else "No",
                "Current Volume": data.get("volume", 0),
                "Active Users": data.get("activeUsers", 0),
                "Total Volume (All Time)": data.get("total_volume_all_time", 0),
                "Avg Daily Volume": round(data.get("avg_daily_volume", 0), 2),
                "Max Daily Volume": data.get("max_daily_volume", 0),
                "Days Active": data.get("days_active", 0),
                "Volume Growth %": round(data.get("volume_growth", 0), 2),
                "Logo URL": data.get("builderLogo", "")
            })
        
        if rows:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            print(f"✅ CSV файл сохранен: {filename}")
    
    async def collect_all_stats(self, time_period: str = "WEEK"):
        """Собирает всю статистику по builders"""
        print(f"📊 Начинаю сбор статистики для периода: {time_period}")
        print("=" * 60)
        
        # Получаем leaderboard
        print("1️⃣ Получаю данные leaderboard...")
        leaderboard_data = await self.fetch_all_builders_leaderboard(time_period=time_period)
        print(f"   ✅ Найдено builders: {len(leaderboard_data)}")
        
        # Получаем временные ряды объема
        print("2️⃣ Получаю временные ряды объема...")
        volume_timeseries = await self.fetch_builder_volume_timeseries(time_period=time_period)
        print(f"   ✅ Получено записей: {len(volume_timeseries)}")
        
        # Агрегируем статистику
        print("3️⃣ Агрегирую статистику...")
        stats = self.aggregate_builder_stats(leaderboard_data, volume_timeseries)
        print(f"   ✅ Обработано builders: {len(stats)}")
        
        # Сохраняем результаты
        print("4️⃣ Сохраняю результаты...")
        self.save_to_json({
            "time_period": time_period,
            "collected_at": datetime.now().isoformat(),
            "total_builders": len(stats),
            "leaderboard": leaderboard_data,
            "volume_timeseries": volume_timeseries,
            "aggregated_stats": stats
        })
        
        self.save_to_csv(stats)
        
        # Выводим топ-10
        print("\n" + "=" * 60)
        print("🏆 ТОП-10 Builders по объему:")
        print("=" * 60)
        
        sorted_builders = sorted(
            stats.items(),
            key=lambda x: x[1].get("volume", 0),
            reverse=True
        )[:10]
        
        for i, (name, data) in enumerate(sorted_builders, 1):
            verified = "✓" if data.get("verified") else ""
            print(f"{i:2d}. {name:30s} {verified:2s} | "
                  f"Volume: ${data.get('volume', 0):>12,.0f} | "
                  f"Users: {data.get('activeUsers', 0):>6} | "
                  f"Rank: {data.get('rank', 'N/A')}")
        
        return stats


async def main():
    """Главная функция"""
    print("🚀 Polymarket Builders Statistics Collector")
    print("=" * 60)
    
    async with PolymarketBuildersStats() as collector:
        # Собираем статистику за неделю (можно изменить на DAY, MONTH, ALL)
        stats = await collector.collect_all_stats(time_period="WEEK")
        
        print("\n" + "=" * 60)
        print("✅ Сбор статистики завершен!")
        print("=" * 60)
        print("\nФайлы:")
        print("  📄 polymarket_builders_stats.json - Полные данные")
        print("  📊 polymarket_builders_stats.csv - Агрегированная статистика")


if __name__ == "__main__":
    asyncio.run(main())

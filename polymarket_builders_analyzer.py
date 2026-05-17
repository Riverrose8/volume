#!/usr/bin/env python3
"""
Расширенный анализатор статистики Polymarket Builders
Создает детальные отчеты и визуализации
"""

import json
import csv
from datetime import datetime
from typing import Dict, List
from collections import defaultdict
import statistics


class BuildersAnalyzer:
    """Анализатор статистики builders"""
    
    def __init__(self, json_file: str = "polymarket_builders_stats.json"):
        self.data = self.load_data(json_file)
        self.stats = self.data.get("aggregated_stats", {})
    
    def load_data(self, filename: str) -> Dict:
        """Загружает данные из JSON файла"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Файл {filename} не найден. Сначала запустите polymarket_builders_stats.py")
            return {}
    
    def generate_detailed_report(self) -> str:
        """Генерирует детальный текстовый отчет"""
        if not self.stats:
            return "Нет данных для анализа"
        
        report = []
        report.append("=" * 80)
        report.append("📊 ДЕТАЛЬНЫЙ ОТЧЕТ ПО POLYMARKET BUILDERS")
        report.append("=" * 80)
        report.append(f"\nПериод анализа: {self.data.get('time_period', 'N/A')}")
        report.append(f"Дата сбора: {self.data.get('collected_at', 'N/A')}")
        report.append(f"Всего builders: {len(self.stats)}")
        report.append("\n" + "=" * 80)
        
        # Общая статистика
        report.append("\n📈 ОБЩАЯ СТАТИСТИКА:")
        report.append("-" * 80)
        
        total_volume = sum(s.get("volume", 0) for s in self.stats.values())
        total_users = sum(s.get("activeUsers", 0) for s in self.stats.values())
        verified_count = sum(1 for s in self.stats.values() if s.get("verified"))
        
        report.append(f"Общий объем: ${total_volume:,.0f}")
        report.append(f"Общее количество активных пользователей: {total_users:,}")
        report.append(f"Верифицированных builders: {verified_count} ({verified_count/len(self.stats)*100:.1f}%)")
        
        # Топ builders по различным метрикам
        report.append("\n" + "=" * 80)
        report.append("🏆 ТОП-10 ПО ОБЪЕМУ:")
        report.append("-" * 80)
        
        top_volume = sorted(
            self.stats.items(),
            key=lambda x: x[1].get("volume", 0),
            reverse=True
        )[:10]
        
        for i, (name, data) in enumerate(top_volume, 1):
            verified = "✓" if data.get("verified") else ""
            report.append(
                f"{i:2d}. {name:30s} {verified:2s} | "
                f"${data.get('volume', 0):>15,.0f} | "
                f"Users: {data.get('activeUsers', 0):>6}"
            )
        
        # Топ по активным пользователям
        report.append("\n" + "=" * 80)
        report.append("👥 ТОП-10 ПО АКТИВНЫМ ПОЛЬЗОВАТЕЛЯМ:")
        report.append("-" * 80)
        
        top_users = sorted(
            self.stats.items(),
            key=lambda x: x[1].get("activeUsers", 0),
            reverse=True
        )[:10]
        
        for i, (name, data) in enumerate(top_users, 1):
            verified = "✓" if data.get("verified") else ""
            report.append(
                f"{i:2d}. {name:30s} {verified:2s} | "
                f"Users: {data.get('activeUsers', 0):>6} | "
                f"Volume: ${data.get('volume', 0):>12,.0f}"
            )
        
        # Топ по росту объема
        report.append("\n" + "=" * 80)
        report.append("📈 ТОП-10 ПО РОСТУ ОБЪЕМА:")
        report.append("-" * 80)
        
        growth_builders = [
            (name, data) for name, data in self.stats.items()
            if data.get("volume_growth", 0) != 0 and data.get("days_active", 0) >= 7
        ]
        top_growth = sorted(
            growth_builders,
            key=lambda x: x[1].get("volume_growth", 0),
            reverse=True
        )[:10]
        
        for i, (name, data) in enumerate(top_growth, 1):
            verified = "✓" if data.get("verified") else ""
            growth = data.get("volume_growth", 0)
            growth_sign = "+" if growth > 0 else ""
            report.append(
                f"{i:2d}. {name:30s} {verified:2s} | "
                f"Growth: {growth_sign}{growth:>6.1f}% | "
                f"Volume: ${data.get('volume', 0):>12,.0f}"
            )
        
        # Статистика по верифицированным vs неверифицированным
        report.append("\n" + "=" * 80)
        report.append("🔍 СРАВНЕНИЕ ВЕРИФИЦИРОВАННЫХ И НЕВЕРИФИЦИРОВАННЫХ:")
        report.append("-" * 80)
        
        verified_stats = [s for s in self.stats.values() if s.get("verified")]
        unverified_stats = [s for s in self.stats.values() if not s.get("verified")]
        
        if verified_stats:
            verified_avg_volume = statistics.mean([s.get("volume", 0) for s in verified_stats])
            verified_avg_users = statistics.mean([s.get("activeUsers", 0) for s in verified_stats])
            report.append(f"Верифицированные ({len(verified_stats)}):")
            report.append(f"  Средний объем: ${verified_avg_volume:,.0f}")
            report.append(f"  Среднее количество пользователей: {verified_avg_users:.1f}")
        
        if unverified_stats:
            unverified_avg_volume = statistics.mean([s.get("volume", 0) for s in unverified_stats])
            unverified_avg_users = statistics.mean([s.get("activeUsers", 0) for s in unverified_stats])
            report.append(f"\nНеверифицированные ({len(unverified_stats)}):")
            report.append(f"  Средний объем: ${unverified_avg_volume:,.0f}")
            report.append(f"  Среднее количество пользователей: {unverified_avg_users:.1f}")
        
        # Распределение по категориям объема
        report.append("\n" + "=" * 80)
        report.append("📊 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ ОБЪЕМА:")
        report.append("-" * 80)
        
        categories = {
            "Монополисты (>$10M)": 0,
            "Крупные ($1M-$10M)": 0,
            "Средние ($100K-$1M)": 0,
            "Малые ($10K-$100K)": 0,
            "Начинающие (<$10K)": 0
        }
        
        for data in self.stats.values():
            volume = data.get("volume", 0)
            if volume >= 10_000_000:
                categories["Монополисты (>$10M)"] += 1
            elif volume >= 1_000_000:
                categories["Крупные ($1M-$10M)"] += 1
            elif volume >= 100_000:
                categories["Средние ($100K-$1M)"] += 1
            elif volume >= 10_000:
                categories["Малые ($10K-$100K)"] += 1
            else:
                categories["Начинающие (<$10K)"] += 1
        
        for category, count in categories.items():
            percentage = (count / len(self.stats)) * 100 if self.stats else 0
            report.append(f"{category:30s}: {count:3d} ({percentage:5.1f}%)")
        
        report.append("\n" + "=" * 80)
        report.append(f"Отчет сгенерирован: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def export_detailed_csv(self, filename: str = "polymarket_builders_detailed.csv"):
        """Экспортирует детальную статистику в CSV"""
        rows = []
        
        for builder_name, data in sorted(
            self.stats.items(),
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
                "Volume per User": round(
                    data.get("volume", 0) / data.get("activeUsers", 1) if data.get("activeUsers", 0) > 0 else 0,
                    2
                ),
                "Logo URL": data.get("builderLogo", "")
            })
        
        if rows:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            print(f"✅ Детальный CSV файл сохранен: {filename}")


def main():
    """Главная функция"""
    print("🔍 Polymarket Builders Analyzer")
    print("=" * 60)
    
    analyzer = BuildersAnalyzer()
    
    if not analyzer.stats:
        print("❌ Нет данных для анализа. Сначала запустите polymarket_builders_stats.py")
        return
    
    # Генерируем отчет
    print("📝 Генерирую детальный отчет...")
    report = analyzer.generate_detailed_report()
    
    # Сохраняем отчет
    report_filename = f"polymarket_builders_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"✅ Отчет сохранен: {report_filename}")
    
    # Выводим отчет в консоль
    print("\n" + report)
    
    # Экспортируем детальный CSV
    print("\n📊 Экспортирую детальную статистику...")
    analyzer.export_detailed_csv()


if __name__ == "__main__":
    main()

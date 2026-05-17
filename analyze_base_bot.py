#!/usr/bin/env python3
"""
Анализ Base бота для выявления проблем с дубликатами и отсутствием Sigma кнопки
"""

import re

def analyze_bot():
    with open('main_base.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("=" * 80)
    print("АНАЛИЗ BASE БОТА: Поиск проблем с дубликатами и Sigma кнопкой")
    print("=" * 80)
    
    # Находим все вызовы tg_send_with_dedup
    print("\n1. ВСЕ ВЫЗОВЫ tg_send_with_dedup:")
    print("-" * 80)
    
    pattern = r'tg_send_with_dedup\([^)]+\)'
    matches = list(re.finditer(pattern, content))
    
    for i, match in enumerate(matches, 1):
        start = match.start()
        # Находим номер строки
        line_num = content[:start].count('\n') + 1
        # Находим контекст (5 строк до и после)
        lines = content[:start].split('\n')
        context_start = max(0, len(lines) - 5)
        context_lines = content.split('\n')[context_start:line_num+5]
        
        print(f"\n{i}. Строка {line_num}:")
        print(f"   Вызов: {match.group()[:100]}...")
        
        # Проверяем, есть ли continue после
        after_match = content[match.end():match.end()+200]
        has_continue = 'continue' in after_match.split('\n')[0:3]
        print(f"   ✅ continue после: {has_continue}")
        
        # Проверяем, создается ли keyboard
        before_match = content[max(0, match.start()-500):match.start()]
        has_keyboard = 'build_trade_bot_keyboard' in before_match[-500:]
        print(f"   ✅ keyboard создается: {has_keyboard}")
        
        # Проверяем условие для keyboard
        if 'if target_chat == TELEGRAM_CHAT_ID' in before_match[-500:]:
            print(f"   ⚠️  ПРОБЛЕМА: Условие для keyboard (может пропустить Sigma)")
    
    # Находим все пути обработки токенов
    print("\n\n2. ВСЕ ПУТИ ОБРАБОТКИ ТОКЕНОВ:")
    print("-" * 80)
    
    paths = [
        ("Established volume spike", r'ESTABLISHED VOLUME SPIKE ALERT'),
        ("Established token", r'INSTANT ALERT.*established'),
        ("New high-volume", r'INSTANT ALERT.*new high-volume'),
        ("Volume spike", r'Volume spike alert'),
        ("Stable token", r'is stable'),
    ]
    
    for path_name, pattern in paths:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                print(f"\n   {path_name} (строка {line_num}):")
                
                # Ищем следующий tg_send_with_dedup после этого пути
                after_content = content[match.end():match.end()+1000]
                send_match = re.search(r'tg_send_with_dedup', after_content)
                if send_match:
                    send_line = line_num + after_content[:send_match.start()].count('\n')
                    print(f"      → tg_send_with_dedup на строке {send_line}")
                    
                    # Проверяем keyboard
                    if 'build_trade_bot_keyboard' in after_content[:send_match.start()]:
                        print(f"      ✅ Keyboard создается")
                    else:
                        print(f"      ❌ Keyboard НЕ создается!")
                    
                    # Проверяем continue
                    after_send = after_content[send_match.end():send_match.end()+200]
                    if 'continue' in after_send.split('\n')[0:5]:
                        print(f"      ✅ continue есть")
                    else:
                        print(f"      ⚠️  continue может отсутствовать")
    
    # Проверяем условия для Sigma
    print("\n\n3. ПРОВЕРКА SIGMA КНОПКИ:")
    print("-" * 80)
    
    sigma_patterns = [
        (r'if target_chat == TELEGRAM_CHAT_ID.*?build_trade_bot_keyboard', 'Условие для keyboard'),
        (r'if.*?target_chat.*?TELEGRAM_CHAT_ID', 'Условие для target_chat'),
    ]
    
    for pattern, desc in sigma_patterns:
        matches = list(re.finditer(pattern, content, re.DOTALL))
        if matches:
            print(f"\n   ⚠️  Найдено условие '{desc}':")
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                print(f"      Строка {line_num}: {match.group()[:100]}...")
    
    # Проверяем нормализацию адресов
    print("\n\n4. ПРОВЕРКА НОРМАЛИЗАЦИИ АДРЕСОВ:")
    print("-" * 80)
    
    if 'normalized_tokens' in content:
        print("   ✅ Нормализация токенов есть")
    else:
        print("   ❌ Нормализация токенов ОТСУТСТВУЕТ!")
    
    # Проверяем атомарные проверки
    print("\n\n5. ПРОВЕРКА АТОМАРНЫХ ПРОВЕРОК:")
    print("-" * 80)
    
    atomic_checks = [
        (r'async with _alert_lock:.*?if.*?in tracker.alerted', 'Атомарная проверка в цикле'),
        (r'tg_send_with_dedup.*?async with _alert_lock', 'Атомарная проверка в tg_send_with_dedup'),
    ]
    
    for pattern, desc in atomic_checks:
        matches = list(re.finditer(pattern, content, re.DOTALL))
        if matches:
            print(f"   ✅ {desc}: найдено {len(matches)} раз")
        else:
            print(f"   ❌ {desc}: НЕ найдено!")
    
    print("\n" + "=" * 80)
    print("АНАЛИЗ ЗАВЕРШЕН")
    print("=" * 80)

if __name__ == '__main__':
    analyze_bot()


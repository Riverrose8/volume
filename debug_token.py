#!/usr/bin/env python3
"""
Детальная проверка токена
"""
import asyncio
import aiohttp
import sys
import os
from datetime import datetime

sys.path.append('.')

from main import (
    fetch_dextools_token_data, 
    fetch_geckoterminal_new_pools,
    fetch_fourmeme_tokens,
    parse_geckoterminal_pool,
    parse_fourmeme_token,
    MIN_5M_VOLUME_USD_NEW,
    MIN_5M_VOLUME_USD_ESTABLISHED,
    MIN_MARKET_CAP_USD,
    MAX_BUY_TAX,
    MAX_SELL_TAX,
    MIN_HOLDERS,
    EXCLUDE_HONEYPOTS,
    MIN_VOLUME_SKIP_HOLDERS
)

async def check_token(token_address):
    """Проверяем токен по всем фильтрам"""
    print(f"🔍 Проверяем токен: {token_address}")
    print("=" * 80)
    
    # Получаем данные из всех источников
    async with aiohttp.ClientSession() as session:
        # 1. DexTools данные
        print("📊 Получаем данные из DexTools...")
        dextools_data = await fetch_dextools_token_data(session, token_address)
        print(f"DexTools данные: {dextools_data}")
        
        # 2. GeckoTerminal данные
        print("\n📈 Получаем данные из GeckoTerminal...")
        gecko_pools = []
        for page in range(1, 6):  # Проверяем первые 5 страниц
            pools = await fetch_geckoterminal_new_pools(session, page)
            if pools:
                gecko_pools.extend(pools)
        
        print(f"GeckoTerminal пулы: {len(gecko_pools) if gecko_pools else 0}")
        
        gecko_data = None
        if gecko_pools:
            for pool in gecko_pools:
                parsed = parse_geckoterminal_pool(pool)
                if parsed and parsed.get('address', '').lower() == token_address.lower():
                    gecko_data = parsed
                    break
        
        print(f"GeckoTerminal данные: {gecko_data}")
        
        # 3. Four.Meme данные
        print("\n🌐 Получаем данные из Four.Meme...")
        fourmeme_tokens = await fetch_fourmeme_tokens(session)
        fourmeme_data = None
        if fourmeme_tokens:
            for token in fourmeme_tokens:
                parsed = parse_fourmeme_token(token)
                if parsed and parsed.get('address', '').lower() == token_address.lower():
                    fourmeme_data = parsed
                    break
        
        print(f"Four.Meme данные: {fourmeme_data}")
    
    # Объединяем данные (приоритет: DexTools > GeckoTerminal > Four.Meme)
    token_data = {}
    if dextools_data:
        token_data.update(dextools_data)
    if gecko_data:
        token_data.update(gecko_data)
    if fourmeme_data:
        token_data.update(fourmeme_data)
    
    print(f"\n📋 Объединенные данные: {token_data}")
    
    # Проверяем фильтры
    print("\n🔍 ПРОВЕРКА ФИЛЬТРОВ:")
    print("=" * 50)
    
    # 1. Объем за 5 минут
    volume_5m = token_data.get('volume_5m', 0)
    print(f"📊 Объем за 5 минут: ${volume_5m:,.0f}")
    
    # 2. Market Cap
    market_cap = token_data.get('market_cap', 0)
    print(f"💰 Market Cap: ${market_cap:,.0f}")
    
    # 3. Возраст токена
    age_hours = token_data.get('age_hours', 0)
    print(f"⏰ Возраст: {age_hours:.1f} часов")
    
    # 4. Холдеры
    holders_count = token_data.get('holders_count', 0)
    print(f"👤 Холдеры: {holders_count}")
    
    # 5. Налоги
    buy_tax = token_data.get('buy_tax', 0)
    sell_tax = token_data.get('sell_tax', 0)
    print(f"💰 Налоги: Buy {buy_tax}%, Sell {sell_tax}%")
    
    # 6. Honeypot статус
    is_honeypot = token_data.get('is_honeypot', None)
    print(f"🛡️ Honeypot: {is_honeypot}")
    
    # Применяем фильтры
    print("\n🚫 РЕЗУЛЬТАТЫ ФИЛЬТРАЦИИ:")
    print("=" * 50)
    
    reasons = []
    
    # Проверка объема
    if age_hours < 24:  # Новый токен
        min_volume = MIN_5M_VOLUME_USD_NEW
        volume_ok = volume_5m >= min_volume
        print(f"📊 Объем (новый токен): ${volume_5m:,.0f} >= ${min_volume:,.0f} = {'✅' if volume_ok else '❌'}")
        if not volume_ok:
            reasons.append(f"Объем ${volume_5m:,.0f} < ${min_volume:,.0f}")
    else:  # Старый токен
        min_volume = MIN_5M_VOLUME_USD_ESTABLISHED
        volume_ok = volume_5m >= min_volume
        print(f"📊 Объем (старый токен): ${volume_5m:,.0f} >= ${min_volume:,.0f} = {'✅' if volume_ok else '❌'}")
        if not volume_ok:
            reasons.append(f"Объем ${volume_5m:,.0f} < ${min_volume:,.0f}")
    
    # Проверка Market Cap
    market_cap_ok = market_cap >= MIN_MARKET_CAP_USD
    print(f"💰 Market Cap: ${market_cap:,.0f} >= ${MIN_MARKET_CAP_USD:,.0f} = {'✅' if market_cap_ok else '❌'}")
    if not market_cap_ok:
        reasons.append(f"Market Cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
    
    # Проверка холдеров (только если объем < MIN_VOLUME_SKIP_HOLDERS)
    if volume_5m < MIN_VOLUME_SKIP_HOLDERS:
        holders_ok = holders_count >= MIN_HOLDERS
        print(f"👤 Холдеры: {holders_count} >= {MIN_HOLDERS} = {'✅' if holders_ok else '❌'}")
        if not holders_ok:
            reasons.append(f"Холдеры {holders_count} < {MIN_HOLDERS}")
    else:
        print(f"👤 Холдеры: ПРОПУЩЕНО (объем ${volume_5m:,.0f} >= ${MIN_VOLUME_SKIP_HOLDERS:,.0f})")
    
    # Проверка налогов
    buy_tax_ok = buy_tax is None or buy_tax <= MAX_BUY_TAX
    sell_tax_ok = sell_tax is None or sell_tax <= MAX_SELL_TAX
    print(f"💰 Buy Tax: {buy_tax}% <= {MAX_BUY_TAX}% = {'✅' if buy_tax_ok else '❌'}")
    print(f"💰 Sell Tax: {sell_tax}% <= {MAX_SELL_TAX}% = {'✅' if sell_tax_ok else '❌'}")
    if not buy_tax_ok:
        reasons.append(f"Buy Tax {buy_tax}% > {MAX_BUY_TAX}%")
    if not sell_tax_ok:
        reasons.append(f"Sell Tax {sell_tax}% > {MAX_SELL_TAX}%")
    
    # Проверка honeypot
    if EXCLUDE_HONEYPOTS:
        honeypot_ok = is_honeypot is False
        print(f"🛡️ Honeypot: {is_honeypot} = {'✅' if honeypot_ok else '❌'}")
        if not honeypot_ok:
            if is_honeypot is True:
                reasons.append("Honeypot токен")
            elif is_honeypot is None:
                reasons.append("Honeypot статус неизвестен")
    else:
        print(f"🛡️ Honeypot: ПРОПУЩЕНО (фильтр отключен)")
    
    # Итоговый результат
    print(f"\n🎯 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("=" * 50)
    
    if reasons:
        print(f"❌ ТОКЕН НЕ ПРОШЕЛ ФИЛЬТРЫ")
        print(f"📋 Причины:")
        for i, reason in enumerate(reasons, 1):
            print(f"   {i}. {reason}")
    else:
        print(f"✅ ТОКЕН ПРОШЕЛ ВСЕ ФИЛЬТРЫ")
        print(f"🚀 Должен был отправиться алерт!")

if __name__ == "__main__":
    token_address = "0xf857213e62d9419ca2076032a1ea3a89d0714444"
    asyncio.run(check_token(token_address))

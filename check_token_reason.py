#!/usr/bin/env python3
"""
Проверяет, почему токен не прошел фильтры
"""
import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from main import (
    fetch_dextools_token_data,
    fetch_token_creator_address,
    fetch_gmgn_token_data,
    parse_dexscreener_pair,
    parse_geckoterminal_pool,
    MIN_5M_VOLUME_USD_NEW,
    MIN_5M_VOLUME_USD_ESTABLISHED,
    MAX_TOKEN_AGE_HOURS,
    MIN_MARKET_CAP_USD,
    MIN_LIQUIDITY_USD,
    MIN_HOLDERS,
    MAX_BUY_TAX,
    MAX_SELL_TAX,
    EXCLUDE_HONEYPOTS,
    MAX_TOP10_HOLDERS_PERCENT,
    REQUIRE_RENOUNCED_CONTRACT,
    EXCLUDE_MINTABLE,
    EXCLUDE_PROXY,
    EXCLUDE_POTENTIALLY_SCAM,
    EXCLUDE_BLACKLISTED,
    BANNED_DEVELOPER_ADDRESSES,
    MIN_TOTAL_FEES_GMGN_BNB,
    EXCLUDE_HIGH_BUNDLER,
    MAX_BUNDLER_PERCENTAGE,
    EXCLUDE_LOW_TOTAL_FEES,
    MIN_VOLUME_SKIP_HOLDERS,
)

load_dotenv()

async def check_token(token_address: str):
    """Проверяет токен и выводит причины фильтрации"""
    token_address = token_address.lower()
    
    print(f"\n🔍 Проверка токена: {token_address}")
    print("=" * 80)
    
    async with aiohttp.ClientSession() as session:
        # 1. Проверяем через DexScreener
        print("\n1. Проверка через DexScreener API...")
        try:
            dexscreener_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with session.get(dexscreener_url, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        # Берем первую пару с BSC
                        bsc_pairs = [p for p in pairs if p.get("chainId") == "bsc"]
                        if bsc_pairs:
                            pair = bsc_pairs[0]
                            parsed = parse_dexscreener_pair(pair)
                            if parsed:
                                print(f"✅ Найден в DexScreener: {parsed['token_symbol']}")
                                print(f"   Volume 5m: ${parsed.get('volume_5m', 0):,.0f}")
                                print(f"   Age: {parsed.get('age_hours', 0):.2f} hours")
                                print(f"   Market Cap: ${parsed.get('market_cap', 0):,.0f}")
                                print(f"   Liquidity: ${parsed.get('liquidity_usd', 0):,.0f}")
                                
                                # Проверяем критерии
                                is_new = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS
                                is_established = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS
                                
                                print(f"\n   Критерии:")
                                print(f"   - Новый токен (< {MAX_TOKEN_AGE_HOURS}h): {is_new}")
                                print(f"   - Устоявшийся токен (>= {MAX_TOKEN_AGE_HOURS}h): {is_established}")
                                
                                if is_new:
                                    if parsed["volume_5m"] < MIN_5M_VOLUME_USD_NEW:
                                        print(f"   ❌ Volume 5m ${parsed['volume_5m']:,.0f} < ${MIN_5M_VOLUME_USD_NEW:,.0f} (MIN для новых)")
                                    else:
                                        print(f"   ✅ Volume 5m ${parsed['volume_5m']:,.0f} >= ${MIN_5M_VOLUME_USD_NEW:,.0f}")
                                
                                if is_established:
                                    if parsed["volume_5m"] < MIN_5M_VOLUME_USD_ESTABLISHED:
                                        print(f"   ❌ Volume 5m ${parsed['volume_5m']:,.0f} < ${MIN_5M_VOLUME_USD_ESTABLISHED:,.0f} (MIN для устоявшихся)")
                                    else:
                                        print(f"   ✅ Volume 5m ${parsed['volume_5m']:,.0f} >= {MIN_5M_VOLUME_USD_ESTABLISHED:,.0f}")
                                
                                token_data = parsed
                            else:
                                print("❌ Не удалось распарсить данные DexScreener")
                                token_data = None
                        else:
                            print("❌ Не найдено пар на BSC в DexScreener")
                            token_data = None
                    else:
                        print("❌ Нет пар в DexScreener")
                        token_data = None
                else:
                    print(f"❌ DexScreener API error: {r.status}")
                    token_data = None
        except Exception as e:
            print(f"❌ Ошибка DexScreener: {e}")
            token_data = None
        
        if not token_data:
            print("\n❌ Токен не найден в DexScreener. Возможно, он не соответствует базовым критериям.")
            return
        
        # 2. Получаем данные из DexTools
        print("\n2. Получение данных из DexTools...")
        try:
            dextools_data = await fetch_dextools_token_data(session, token_address)
            if dextools_data:
                # Важно: не перетираем адекватную ликвидность из DexScreener,
                # если DexTools вернул 0 / None (часто так для новых пулов).
                dx_liq = dextools_data.get("liquidity_usd")
                if dx_liq is None or dx_liq == 0:
                    dextools_data.pop("liquidity_usd", None)
                else:
                    print(f"   Liquidity (DexTools): ${dx_liq:,.0f}")

                # Аналогично с volume_24h: если DexTools дал 0, но в token_data уже есть
                # volume_24h от DexScreener/Gecko, не затираем его.
                dx_vol24 = dextools_data.get("volume_24h")
                if (dx_vol24 is None or dx_vol24 == 0) and token_data.get("volume_24h"):
                    dextools_data.pop("volume_24h", None)

                token_data.update(dextools_data)

                print(f"✅ DexTools данные получены")
                print(f"   Holders: {dextools_data.get('holders_count', 'N/A')}")
                print(f"   Honeypot: {dextools_data.get('is_honeypot', 'N/A')}")
                print(f"   Buy Tax: {dextools_data.get('buy_tax', 'N/A')}%")
                print(f"   Sell Tax: {dextools_data.get('sell_tax', 'N/A')}%")
                print(f"   Top 10 Holders: {dextools_data.get('top10_holders_percent', 'N/A')}%")
                print(f"   Contract Renounced: {dextools_data.get('is_contract_renounced', 'N/A')}")
                print(f"   Mintable: {dextools_data.get('is_mintable', 'N/A')}")
                print(f"   Proxy: {dextools_data.get('is_proxy', 'N/A')}")
                print(f"   Potentially Scam: {dextools_data.get('is_potentially_scam', 'N/A')}")
                print(f"   Blacklisted: {dextools_data.get('is_blacklisted', 'N/A')}")
                print(f"   Volume 24h (DexTools): ${dextools_data.get('volume_24h', 0):,.0f}")
            else:
                print("⚠️ DexTools данные недоступны")
        except Exception as e:
            print(f"❌ Ошибка DexTools: {e}")
        
        # 3. Проверяем адрес создателя
        print("\n3. Проверка адреса создателя...")
        try:
            creator_address = await fetch_token_creator_address(session, token_address)
            if creator_address:
                creator_lower = creator_address.lower()
                print(f"   Creator: {creator_lower}")
                if creator_lower in [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]:
                    print(f"   ❌ ЗАБАНЕН: Адрес создателя в списке забаненных!")
                else:
                    print(f"   ✅ Адрес создателя не забанен")
            else:
                print("   ⚠️ Не удалось получить адрес создателя")
        except Exception as e:
            print(f"   ❌ Ошибка получения адреса создателя: {e}")
        
        # 4. Проверяем все фильтры
        print("\n4. Проверка фильтров безопасности...")
        
        # Honeypot
        is_honeypot = token_data.get('is_honeypot')
        if EXCLUDE_HONEYPOTS and is_honeypot is True:
            print(f"   ❌ Honeypot: {is_honeypot}")
        else:
            print(f"   ✅ Honeypot: {is_honeypot}")
        
        # Buy/Sell Tax
        buy_tax = token_data.get('buy_tax')
        sell_tax = token_data.get('sell_tax')
        if buy_tax is not None:
            if buy_tax > MAX_BUY_TAX:
                print(f"   ❌ Buy Tax: {buy_tax}% > {MAX_BUY_TAX}%")
            else:
                print(f"   ✅ Buy Tax: {buy_tax}% <= {MAX_BUY_TAX}%")
        else:
            print(f"   ⚠️ Buy Tax: неизвестно (не блокируем)")
        
        if sell_tax is not None:
            if sell_tax > MAX_SELL_TAX:
                print(f"   ❌ Sell Tax: {sell_tax}% > {MAX_SELL_TAX}%")
            else:
                print(f"   ✅ Sell Tax: {sell_tax}% <= {MAX_SELL_TAX}%")
        else:
            print(f"   ⚠️ Sell Tax: неизвестно (не блокируем)")
        
        # Top 10 Holders
        top10_holders_percent = token_data.get('top10_holders_percent')
        if top10_holders_percent is not None:
            if top10_holders_percent > MAX_TOP10_HOLDERS_PERCENT:
                print(f"   ❌ Top 10 Holders: {top10_holders_percent:.1f}% > {MAX_TOP10_HOLDERS_PERCENT:.1f}%")
            else:
                print(f"   ✅ Top 10 Holders: {top10_holders_percent:.1f}% <= {MAX_TOP10_HOLDERS_PERCENT:.1f}%")
        else:
            print(f"   ⚠️ Top 10 Holders: неизвестно (не блокируем)")
        
        # Contract Renounced
        is_renounced = token_data.get('is_contract_renounced', False)
        if REQUIRE_RENOUNCED_CONTRACT and not is_renounced:
            print(f"   ❌ Contract Renounced: {is_renounced} (требуется True)")
        else:
            print(f"   ✅ Contract Renounced: {is_renounced}")
        
        # Mintable
        is_mintable = token_data.get('is_mintable', False)
        if EXCLUDE_MINTABLE and is_mintable:
            print(f"   ❌ Mintable: {is_mintable}")
        else:
            print(f"   ✅ Mintable: {is_mintable}")
        
        # Proxy
        is_proxy = token_data.get('is_proxy', False)
        if EXCLUDE_PROXY and is_proxy:
            print(f"   ❌ Proxy: {is_proxy}")
        else:
            print(f"   ✅ Proxy: {is_proxy}")
        
        # Potentially Scam
        is_potentially_scam = token_data.get('is_potentially_scam', False)
        if EXCLUDE_POTENTIALLY_SCAM and is_potentially_scam:
            print(f"   ❌ Potentially Scam: {is_potentially_scam}")
        else:
            print(f"   ✅ Potentially Scam: {is_potentially_scam}")
        
        # Blacklisted
        is_blacklisted = token_data.get('is_blacklisted', False)
        if EXCLUDE_BLACKLISTED and is_blacklisted:
            print(f"   ❌ Blacklisted: {is_blacklisted}")
        else:
            print(f"   ✅ Blacklisted: {is_blacklisted}")
        
        # Holders
        holders = token_data.get('holders_count', 0)
        holders_unavailable = token_data.get('holders_unavailable', False)
        volume_5m = token_data.get("volume_5m", 0)
        
        if volume_5m >= MIN_VOLUME_SKIP_HOLDERS:
            print(f"   ✅ Holders: пропуск проверки (высокий объем ${volume_5m:,.0f} >= ${MIN_VOLUME_SKIP_HOLDERS:,.0f})")
        elif holders_unavailable:
            print(f"   ⚠️ Holders: данные недоступны (не блокируем)")
        elif holders < MIN_HOLDERS:
            print(f"   ❌ Holders: {holders} < {MIN_HOLDERS}")
        else:
            print(f"   ✅ Holders: {holders} >= {MIN_HOLDERS}")
        
        # Market Cap
        market_cap = token_data.get('fdv') or token_data.get('market_cap') or 0
        if market_cap < MIN_MARKET_CAP_USD:
            print(f"   ❌ Market Cap: ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
        else:
            print(f"   ✅ Market Cap: ${market_cap:,.0f} >= ${MIN_MARKET_CAP_USD:,.0f}")
        
        # Liquidity (берём только из DexScreener / GeckoTerminal, не из DexTools)
        liquidity_usd = token_data.get('liquidity_usd', 0)
        print(f"   Liquidity (debug): ${liquidity_usd:,.0f}")
        if liquidity_usd < MIN_LIQUIDITY_USD:
            print(f"   ❌ Liquidity: ${liquidity_usd:,.0f} < ${MIN_LIQUIDITY_USD:,.0f}")
        else:
            print(f"   ✅ Liquidity: ${liquidity_usd:,.0f} >= {MIN_LIQUIDITY_USD:,.0f}")
        
        # Total Fees из APIFY GMGN (как в основном боте)
        print("\n5. Проверка Total Fees (GMGN / Apify)...")
        gmgn_data = await fetch_gmgn_token_data(session, token_address)
        if gmgn_data:
            total_fees_bnb = gmgn_data.get("total_fees_bnb")
            bundler_percentage = gmgn_data.get("bundler_percentage")
            top10_rate = gmgn_data.get("top_10_holder_rate")
            creator_count = gmgn_data.get("creator_open_count")

            print(f"   GMGN total_fees_bnb: {total_fees_bnb}")
            print(f"   GMGN bundler%: {bundler_percentage}")
            print(f"   GMGN top_10_holder_rate%: {top10_rate}")
            print(f"   GMGN creator_open_count: {creator_count}")

            # Фильтр по bundler (если включён)
            if EXCLUDE_HIGH_BUNDLER and bundler_percentage is not None:
                if bundler_percentage > MAX_BUNDLER_PERCENTAGE:
                    print(f"   ❌ Bundler%: {bundler_percentage:.1f}% > {MAX_BUNDLER_PERCENTAGE:.1f}%")
                else:
                    print(f"   ✅ Bundler%: {bundler_percentage:.1f}% <= {MAX_BUNDLER_PERCENTAGE:.1f}%")

            # Фильтр по total_fees_bnb (если включён)
            if EXCLUDE_LOW_TOTAL_FEES:
                if total_fees_bnb is None:
                    print(f"   ❌ Total Fees (GMGN): None (GMGN не вернул total_fees_bnb, бот заблокирует токен)")
                elif total_fees_bnb < MIN_TOTAL_FEES_GMGN_BNB:
                    print(f"   ❌ Total Fees (GMGN): {total_fees_bnb:.4f}BNB < {MIN_TOTAL_FEES_GMGN_BNB}BNB")
                else:
                    print(f"   ✅ Total Fees (GMGN): {total_fees_bnb:.4f}BNB >= {MIN_TOTAL_FEES_GMGN_BNB}BNB")
        else:
            print("   ❌ GMGN / Apify не вернул данные, токен будет заблокирован, если EXCLUDE_LOW_TOTAL_FEES=true")
        
        print("\n" + "=" * 80)
        print("Итог: Проверьте все ❌ выше - это причины, по которым токен мог быть отфильтрован")

if __name__ == "__main__":
    import sys
    # Можно передать адрес токена первым аргументом командной строки.
    # Если аргумент не передан, используется адрес по умолчанию.
    token_address = sys.argv[1] if len(sys.argv) > 1 else "0xF30bfb97D565891b374DE164531b9A6587e04444"
    asyncio.run(check_token(token_address))

#!/usr/bin/env python3
"""
Bot для мониторинга новых токенов на BSC с высоким объемом торгов.
Сканирует DexScreener и GeckoTerminal одновременно.
"""

import os
import asyncio
import aiohttp
import logging
import json
import re
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Загружаем переменные окружения
load_dotenv()

# =========================
# Конфигурация
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Временно перенаправляем все алерты в канал @pancakeswapvolume
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "@pancakeswapvolume")  # Временно: @pancakeswapvolume
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", TELEGRAM_CHAT_ID)
TELEGRAM_TEST_CHAT_ID = os.getenv("TELEGRAM_TEST_CHAT_ID", "")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Optional external trade bot link templates for inline buttons (used in TEST_MODE)
# Example: MAESTRO_URL_TEMPLATE="https://t.me/maestro?start=bsc_{token}"
#          AXIOM_URL_TEMPLATE="https://axiom.trade/t/{token}/@zodchii"
MAESTRO_URL_TEMPLATE = os.getenv("MAESTRO_URL_TEMPLATE", "").strip()
# Bloom deprecated; support Axiom instead
AXIOM_URL_TEMPLATE = os.getenv("AXIOM_URL_TEMPLATE", "https://axiom.trade/t/{token}/@zodchii").strip()

# Интервалы и пороги
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "15"))  # Сканируем каждые 15 сек

# Для новых токенов (< 2 часов)
MIN_5M_VOLUME_USD_NEW = float(os.getenv("MIN_5M_VOLUME_USD_NEW", "180000"))  # $180K за 5 минут для новых токенов
MAX_TOKEN_AGE_HOURS = float(os.getenv("MAX_TOKEN_AGE_HOURS", "2"))  # Максимум 2 часа для "новых" токенов
MIN_STABILITY_CHECKS = int(os.getenv("MIN_STABILITY_CHECKS", "2"))  # Минимум 2 проверки (2 * 30 сек = 1 минута)

# Для устоявшихся токенов (> 2 часов) - ловим резкие скачки объема
MIN_5M_VOLUME_USD_ESTABLISHED = float(os.getenv("MIN_5M_VOLUME_USD_ESTABLISHED", "2000000"))  # $2M за 5 минут

# Максимальный объем для исключения слишком популярных токенов
MAX_5M_VOLUME_USD = float(os.getenv("MAX_5M_VOLUME_USD", "40000000"))  # $40M за 5 минут

# Минимальный объем для пропуска проверки держателей
MIN_VOLUME_SKIP_HOLDERS = float(os.getenv("MIN_VOLUME_SKIP_HOLDERS", "1000000"))  # $1M за 5 минут

# Фильтры безопасности
MIN_HOLDERS = int(os.getenv("MIN_HOLDERS", "50"))  # Минимум 50 держателей
MIN_MARKET_CAP_USD = float(os.getenv("MIN_MARKET_CAP_USD", "100000"))  # Минимум $100K market cap
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "5000"))  # Минимум $5K ликвидности
MAX_BUY_TAX = float(os.getenv("MAX_BUY_TAX", "3"))  # Максимум 3% tax на покупку
MAX_SELL_TAX = float(os.getenv("MAX_SELL_TAX", "3"))  # Максимум 3% tax на продажу
EXCLUDE_HONEYPOTS = os.getenv("EXCLUDE_HONEYPOTS", "true").lower() == "true"  # Исключать honeypots

# Дополнительные фильтры безопасности (требуют DexTools API)
MAX_TOP10_HOLDERS_PERCENT = float(os.getenv("MAX_TOP10_HOLDERS_PERCENT", "25"))  # Максимум 25% у топ-10 holders
REQUIRE_RENOUNCED_CONTRACT = os.getenv("REQUIRE_RENOUNCED_CONTRACT", "false").lower() == "true"  # Требовать renounced контракт (по умолчанию отключено)
EXCLUDE_MINTABLE = os.getenv("EXCLUDE_MINTABLE", "true").lower() == "true"  # Исключать mintable токены
EXCLUDE_PROXY = os.getenv("EXCLUDE_PROXY", "true").lower() == "true"  # Исключать proxy контракты
EXCLUDE_POTENTIALLY_SCAM = os.getenv("EXCLUDE_POTENTIALLY_SCAM", "true").lower() == "true"  # Исключать потенциально scam
EXCLUDE_BLACKLISTED = os.getenv("EXCLUDE_BLACKLISTED", "true").lower() == "true"  # Исключать blacklisted токены

# Минимальный total fees для отправки алерта
MIN_TOTAL_FEES_BNB = float(os.getenv("MIN_TOTAL_FEES_BNB", "0.3"))  # Минимум 0.3 BNB total fees

# GMGN фильтры для скам токенов
MAX_BUNDLER_PERCENTAGE = float(os.getenv("MAX_BUNDLER_PERCENTAGE", "75"))  # Максимум 75% bundler
MIN_TOTAL_FEES_GMGN_BNB = float(os.getenv("MIN_TOTAL_FEES_GMGN_BNB", "0.025"))  # Минимум 0.025 BNB total fees (из GMGN)
EXCLUDE_HIGH_BUNDLER = os.getenv("EXCLUDE_HIGH_BUNDLER", "true").lower() == "true"  # Исключать токены с высоким bundler %
EXCLUDE_LOW_TOTAL_FEES = os.getenv("EXCLUDE_LOW_TOTAL_FEES", "true").lower() == "true"  # Исключать токены с низкими total fees

# Забаненные адреса разработчиков (создателей токенов)
# ВНИМАНИЕ: Блокируем токены, созданные этими адресами как создателями (deployer)
# Адрес 0xca143ce32fe78f1f7019d7d551a6402fc5350c73 - это адрес, который создает скам токены
# (НЕ путать с PancakeSwap Factory - мы проверяем создателя токена, а не использование factory)
BANNED_DEVELOPER_ADDRESSES = [
    "0xca143ce32fe78f1f7019d7d551a6402fc5350c73",  # Забаненный адрес создателя скам токенов
]

DEDUP_TTL_HOURS = int(os.getenv("DEDUP_TTL_HOURS", "24"))

# BSCScan API Key
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")

# DexTools API Key
DEXTOOLS_API_KEY = os.getenv("DEXTOOLS_API_KEY", "NwsXotBCJcaBdaRieXoFE9Fcdhin9dKL9ndoTGqG")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY", "")

# Apify API Key (для GMGN данных)
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")  # Получить на https://console.apify.com/account/integrations

# =========================
# Four.Meme API (Bitquery)
# =========================

async def fetch_fourmeme_tokens(session: aiohttp.ClientSession) -> List[Dict]:
    """
    Получает новые токены с Four.Meme через Bitquery API
    """
    if not BITQUERY_API_KEY:
        logger.debug("Bitquery API key not configured")
        return []

    try:
        # GraphQL запрос для получения новых токенов на Four.Meme
        query = """
        query {
          EVM(dataset: combined, network: bsc) {
            DEXTradeByTokens(
              orderBy: {descendingByField: "Block_Time"}
              limit: {count: 50}
              where: {
                Trade: {
                  Dex: {ProtocolName: {is: "fourmeme_v1"}}
                }
                Block: {
                  Time: {
                    since: "2025-10-14T00:00:00Z"
                  }
                }
              }
            ) {
              Trade {
                Currency {
                  Name
                  Symbol
                  SmartContract
                }
                Dex {
                  ProtocolName
                }
                Block {
                  Time
                }
              }
              volumeUsd: sum(of: Trade_Side_AmountInUSD)
              count: count
            }
          }
        }
        """

        headers = {
            "Authorization": f"Bearer {BITQUERY_API_KEY}",
            "Content-Type": "application/json"
        }

        async with session.post(
            "https://graphql.bitquery.io",
            json={"query": query},
            headers=headers,
            timeout=15
        ) as r:
            if r.status != 200:
                logger.debug(f"Bitquery API error: {r.status}")
                return []

            data = await r.json()
            if "data" not in data or "EVM" not in data["data"]:
                logger.debug(f"Bitquery API returned no data: {data}")
                return []

            trades = data["data"]["EVM"]["DEXTradeByTokens"]
            logger.info(f"✅ Bitquery: fetched {len(trades)} Four.Meme tokens")
            return trades

    except Exception as e:
        logger.debug(f"Bitquery API exception: {e}")
        return []

def parse_fourmeme_token(trade: Dict) -> Optional[Dict]:
    """
    Парсит токен из Four.Meme в unified формат
    """
    try:
        currency = trade["Trade"]["Currency"]
        block_time = trade["Trade"]["Block"]["Time"]
        
        # Время создания токена (примерно)
        created_at = datetime.fromisoformat(block_time.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        
        # Объем за последние торги (приблизительно)
        volume_5m = float(trade.get("volumeUsd", 0))
        
        # Адрес токена
        token_address = currency["SmartContract"].lower()
        if not token_address:
            return None
        
        # Проверяем что это не WBNB/USDT
        if token_address in ["0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c", "0x55d398326f99059ff775485246999027b3197955"]:
            return None
        
        return {
            "token_address": token_address,
            "token_symbol": currency["Symbol"],
            "token_name": currency["Name"],
            "volume_5m": volume_5m,
            "age_hours": age_hours,
            "is_new_token": age_hours < MAX_TOKEN_AGE_HOURS,
            "source": "fourmeme"
        }

    except Exception as e:
        logger.debug(f"Error parsing Four.Meme token: {e}")
        return None

# =========================
# BSCScan API (Fallback)
# =========================

async def fetch_bscscan_token_holders(session: aiohttp.ClientSession, token_address: str) -> Optional[int]:
    """
    Получает количество держателей токена через BSCScan API
    Fallback источник когда DexTools недоступен
    """
    if not BSCSCAN_API_KEY:
        logger.debug("BSCScan API key not configured")
        return None
    
    try:
        # BSCScan API для получения информации о токене
        url = "https://api.bscscan.com/api"
        params = {
            "module": "token",
            "action": "tokeninfo",
            "contractaddress": token_address,
            "apikey": BSCSCAN_API_KEY
        }
        
        async with session.get(url, params=params, timeout=15) as r:
            if r.status != 200:
                logger.debug(f"BSCScan API error: {r.status}")
                return None
            
            data = await r.json()
            if data.get("status") == "1" and data.get("result"):
                result = data["result"][0] if isinstance(data["result"], list) else data["result"]
                holders = result.get("TotalHolders")
                if holders:
                    holders_count = int(holders)
                    logger.info(f"✅ BSCScan: {token_address[:8]}... holders={holders_count}")
                    return holders_count
            else:
                logger.debug(f"BSCScan API returned no data: {data.get('message', 'Unknown error')}")
                return None
                
    except Exception as e:
        logger.debug(f"BSCScan API exception: {e}")
        return None

async def fetch_honeypot_is_status(session: aiohttp.ClientSession, token_address: str) -> Optional[bool]:
    """
    Проверяет honeypot статус через honeypot.is API
    Fallback источник когда DexTools недоступен
    """
    try:
        # Honeypot.is API для проверки BSC токенов
        url = f"https://api.honeypot.is/v2/IsHoneypot"
        params = {
            "address": token_address,
            "chainID": 56  # BSC chain ID
        }
        
        async with session.get(url, params=params, timeout=15) as r:
            if r.status != 200:
                logger.debug(f"Honeypot.is API error: {r.status}")
                return None
            
            data = await r.json()
            # Парсим ответ honeypot.is API
            if "honeypotResult" in data and "isHoneypot" in data["honeypotResult"]:
                is_honeypot = data["honeypotResult"]["isHoneypot"]
                logger.info(f"✅ Honeypot.is: {token_address[:8]}... honeypot={is_honeypot}")
                return is_honeypot
            elif "summary" in data and "risk" in data["summary"]:
                # Альтернативный способ проверки через risk level
                risk = data["summary"]["risk"]
                is_honeypot = risk == "honeypot"
                logger.info(f"✅ Honeypot.is: {token_address[:8]}... risk={risk}, honeypot={is_honeypot}")
                return is_honeypot
            else:
                logger.debug(f"Honeypot.is API returned no honeypot data: {data}")
                return None
                
    except Exception as e:
        logger.debug(f"Honeypot.is API exception: {e}")
        return None

async def fetch_token_creator_via_factory_events(session: aiohttp.ClientSession, pair_address: str) -> Optional[str]:
    """
    Альтернативный способ: Получает создателя через события PairCreated в PancakeSwap Factory
    Это самый надежный способ для пулов, созданных через PancakeSwap Factory
    """
    if not BSCSCAN_API_KEY or not pair_address:
        return None
    
    try:
        factory_address = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"
        url = "https://api.bscscan.com/api"
        
        # Topic0 для события PairCreated(address,address,address,uint256)
        # keccak256("PairCreated(address,address,address,uint256)")
        topic0 = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
        
        # ОПТИМИЗАЦИЯ: Используем очень ограниченный диапазон блоков (последние 10,000 блоков)
        # Это примерно последние 3-4 часа, что достаточно для новых токенов
        # Получаем текущий блок через простой запрос
        try:
            current_block_params = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": BSCSCAN_API_KEY
            }
            async with session.get(url, params=current_block_params, timeout=3) as r:
                if r.status == 200:
                    block_data = await r.json()
                    current_block_hex = block_data.get("result", "0x0")
                    current_block = int(current_block_hex, 16) if current_block_hex.startswith("0x") else 0
                    # Используем последние 10,000 блоков (примерно 3-4 часа) - намного быстрее
                    from_block = max(0, current_block - 10000)
                else:
                    # Если не удалось получить текущий блок, используем очень короткий фиксированный диапазон
                    # Используем последние 5,000 блоков (примерно 1.5-2 часа)
                    from_block = max(0, 40000000)  # Примерно последние 2 часа от текущего момента
        except Exception as e:
            logger.debug(f"Error getting current block: {e}")
            # Используем очень короткий фиксированный диапазон
            from_block = max(0, 40000000)
        
        # Получаем события PairCreated с ограниченным диапазоном блоков
        params = {
            "module": "logs",
            "action": "getLogs",
            "fromBlock": from_block,
            "toBlock": "latest",
            "address": factory_address,
            "topic0": topic0,
            "apikey": BSCSCAN_API_KEY
        }
        
        # Используем очень короткий таймаут и обработку ошибок
        try:
            async with session.get(url, params=params, timeout=3) as r:  # Очень короткий таймаут
                if r.status == 200:
                    data = await r.json()
                    if data.get("status") == "1" and data.get("result"):
                        logs = data["result"]
                        if isinstance(logs, list) and len(logs) > 0:
                            # Фильтруем события по адресу пары (topic2 содержит адрес пары)
                            pair_address_lower = pair_address.lower()
                            pair_topic = "0x" + "0" * 24 + pair_address_lower[2:]
                            
                            matching_logs = [
                                log for log in logs 
                                if isinstance(log, dict) and 
                                log.get("topics") and 
                                len(log.get("topics", [])) > 2 and
                                log.get("topics", [])[2].lower() == pair_topic.lower()
                            ]
                            
                            if not matching_logs:
                                # Если не нашли по topic2, пробуем найти по адресу в data
                                matching_logs = [
                                    log for log in logs 
                                    if isinstance(log, dict) and 
                                    pair_address_lower in log.get("data", "").lower()
                                ]
                            
                            if matching_logs:
                                # Берем последнее событие (самое свежее)
                                log = matching_logs[-1]
                                tx_hash = log.get("transactionHash")
                                
                                # Получаем транзакцию, чтобы узнать кто её отправил (создатель)
                                if tx_hash:
                                    tx_params = {
                                        "module": "proxy",
                                        "action": "eth_getTransactionByHash",
                                        "txhash": tx_hash,
                                        "apikey": BSCSCAN_API_KEY
                                    }
                                    try:
                                        async with session.get(url, params=tx_params, timeout=3) as r2:
                                            if r2.status == 200:
                                                tx_data = await r2.json()
                                                if tx_data.get("result"):
                                                    creator = tx_data["result"].get("from", "").lower()
                                                    if creator:
                                                        logger.info(f"✅ BSCScan (factory event): {pair_address[:8]}... creator={creator[:8]}...")
                                                        return creator
                                    except asyncio.TimeoutError:
                                        logger.debug(f"Timeout fetching transaction for {pair_address[:8]}...")
                                        return None
                                    except Exception as e:
                                        logger.debug(f"Error fetching transaction: {e}")
                                        return None
                else:
                    logger.debug(f"BSCScan getLogs returned status {r.status}")
        except asyncio.TimeoutError:
            logger.debug(f"Timeout fetching factory events for {pair_address[:8]}...")
            return None
        except Exception as e:
            logger.debug(f"BSCScan factory events exception: {e}")
            return None
    except asyncio.TimeoutError:
        logger.debug(f"Timeout in factory events check for {pair_address[:8]}...")
        return None
    except Exception as e:
        logger.debug(f"BSCScan factory events exception: {e}")
        return None
    
    return None

async def check_banned_developer(session: aiohttp.ClientSession, token_address: str, pair_address: str = None) -> bool:
    """
    Проверяет, является ли создатель токена забаненным разработчиком
    Возвращает True если токен создан забаненным разработчиком, False иначе
    ФОКУС НА СОЗДАТЕЛЕ: блокируем только токены, созданные забаненным адресом как создателем
    """
    if not BSCSCAN_API_KEY:
        logger.warning(f"⚠️ BSCScan API key not configured, cannot check banned developer for {token_address[:8]}...")
        return False
    
    banned_addresses_lower = [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]
    factory_address = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"
    factory_address_lower = factory_address.lower()
    
    try:
        # СПОСОБ 1: Проверяем адрес создателя токена (ГЛАВНЫЙ СПОСОБ)
        creator_address = await fetch_token_creator_address(session, token_address, pair_address)
        if creator_address:
            creator_lower = creator_address.lower()
            if creator_lower in banned_addresses_lower:
                logger.info(f"🚫 BANNED: {token_address[:8]}... creator={creator_lower[:8]}... matches banned address")
                return True
        
        # СПОСОБ 2: Проверяем события Factory (PairCreated) - проверяем кто вызвал factory для создания пула
        # Это более надежно, чем проверка транзакций, так как проверяет именно создание пула
        if pair_address:
            try:
                url = "https://api.bscscan.com/api"
                # Получаем события PairCreated от factory
                params_events = {
                    "module": "logs",
                    "action": "getLogs",
                    "fromBlock": "0",
                    "toBlock": "latest",
                    "address": factory_address,
                    "topic0": "0x0d3648bd0f6ba80134a33ba9275ac585d9d318f1adfd556bf3a8e5d2b27a2326",  # PairCreated(address,address,address,uint256)
                    "topic2": f"0x{'0'*24}{pair_address[2:]}",  # topic2 = pair address (padded)
                    "apikey": BSCSCAN_API_KEY
                }
                async with session.get(url, params=params_events, timeout=15) as r:
                    if r.status == 200:
                        event_data = await r.json()
                        event_result = event_data.get("result")
                        if isinstance(event_result, list) and len(event_result) > 0:
                            # Нашли событие создания пула, проверяем кто его вызвал
                            for event in event_result:
                                if isinstance(event, dict):
                                    tx_hash = event.get("transactionHash")
                                    if tx_hash:
                                        # Получаем транзакцию по хешу
                                        params_tx_hash = {
                                            "module": "proxy",
                                            "action": "eth_getTransactionByHash",
                                            "txhash": tx_hash,
                                            "apikey": BSCSCAN_API_KEY
                                        }
                                        async with session.get(url, params=params_tx_hash, timeout=10) as r2:
                                            if r2.status == 200:
                                                tx_data = await r2.json()
                                                tx_result = tx_data.get("result")
                                                if isinstance(tx_result, dict):
                                                    tx_from = tx_result.get("from", "").lower()
                                                    # Исключаем factory из проверки (это легитимный адрес)
                                                    if tx_from != factory_address_lower and tx_from in banned_addresses_lower:
                                                        logger.info(f"🚫 BANNED: {token_address[:8]}... pair={pair_address[:8]}... banned dev in PairCreated event: {tx_from[:8]}...")
                                                        return True
            except Exception as e:
                logger.debug(f"Error checking PairCreated events for {token_address[:8]}...: {e}")
        
        # СПОСОБ 3: Проверяем транзакции создания пула - кто вызвал factory (только первые транзакции)
        # Исключаем проверку транзакций к factory, так как factory - легитимный адрес
        if pair_address:
            url = "https://api.bscscan.com/api"
            params_tx = {
                "module": "account",
                "action": "txlist",
                "address": pair_address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 10,  # Проверяем только первые 10 транзакций (создание пула)
                "sort": "asc",
                "apikey": BSCSCAN_API_KEY
            }
            async with session.get(url, params=params_tx, timeout=15) as r:
                if r.status == 200:
                    tx_data = await r.json()
                    tx_result = tx_data.get("result")
                    if isinstance(tx_result, list) and len(tx_result) > 0:
                        # Проверяем только первые транзакции (создание пула)
                        for tx in tx_result[:5]:  # Только первые 5 транзакций
                            if isinstance(tx, dict):
                                tx_from = tx.get("from", "").lower()
                                tx_to = tx.get("to", "").lower()
                                
                                # Проверяем, если транзакция к factory (создание пула)
                                if tx_to == factory_address_lower:
                                    # Исключаем factory из проверки
                                    if tx_from != factory_address_lower and tx_from in banned_addresses_lower:
                                        logger.info(f"🚫 BANNED: {token_address[:8]}... pair={pair_address[:8]}... banned dev called factory: {tx_from[:8]}...")
                                        return True
                                
                                # Проверяем сам адрес отправителя (но не factory)
                                if tx_from != factory_address_lower and tx_from in banned_addresses_lower:
                                    logger.info(f"🚫 BANNED: {token_address[:8]}... pair={pair_address[:8]}... banned dev in tx: {tx_from[:8]}...")
                                    return True
        
        # СПОСОБ 4: Проверяем транзакции создания токена (только первые транзакции)
        url = "https://api.bscscan.com/api"
        params_token_tx = {
            "module": "account",
            "action": "txlist",
            "address": token_address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 10,  # Проверяем только первые 10 транзакций
            "sort": "asc",
            "apikey": BSCSCAN_API_KEY
        }
        async with session.get(url, params=params_token_tx, timeout=15) as r:
            if r.status == 200:
                tx_data = await r.json()
                tx_result = tx_data.get("result")
                if isinstance(tx_result, list) and len(tx_result) > 0:
                    # Проверяем только первые транзакции (создание токена)
                    for tx in tx_result[:5]:  # Только первые 5 транзакций
                        if isinstance(tx, dict):
                            tx_from = tx.get("from", "").lower()
                            tx_to = tx.get("to", "").lower()
                            
                            # Проверяем, если транзакция к factory
                            if tx_to == factory_address_lower:
                                # Исключаем factory из проверки
                                if tx_from != factory_address_lower and tx_from in banned_addresses_lower:
                                    logger.info(f"🚫 BANNED: {token_address[:8]}... banned dev called factory from token tx: {tx_from[:8]}...")
                                    return True
                            
                            # Проверяем сам адрес отправителя (но не factory)
                            if tx_from != factory_address_lower and tx_from in banned_addresses_lower:
                                logger.info(f"🚫 BANNED: {token_address[:8]}... banned dev in token tx: {tx_from[:8]}...")
                                return True
        
    except Exception as e:
        logger.warning(f"⚠️ Error checking banned developer for {token_address[:8]}...: {e}")
    
    return False

async def fetch_token_creator_address(session: aiohttp.ClientSession, token_address: str, pair_address: str = None) -> Optional[str]:
    """
    Получает адрес создателя токена через BSCScan API
    Использует транзакцию создания контракта (contract creation transaction)
    Если не удается получить адрес создателя токена, пробует получить адрес создателя пула
    Сначала пробует через события Factory (самый надежный способ)
    """
    if not BSCSCAN_API_KEY:
        logger.debug("BSCScan API key not configured for fetching creator address")
        return None
    
    # Способ 0: Проверяем через события Factory (самый надежный для PancakeSwap)
    if pair_address:
        creator = await fetch_token_creator_via_factory_events(session, pair_address)
        if creator:
            return creator
    
    try:
        # Способ 1: Получаем транзакцию создания контракта токена
        url = "https://api.bscscan.com/api"
        params = {
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": token_address,
            "apikey": BSCSCAN_API_KEY
        }
        
        async with session.get(url, params=params, timeout=15) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("status") == "1" and data.get("result"):
                    result = data["result"]
                    if isinstance(result, list) and len(result) > 0:
                        creator_address = result[0].get("contractCreator", "").lower()
                        if creator_address:
                            logger.info(f"✅ BSCScan: {token_address[:8]}... creator={creator_address[:8]}...")
                            return creator_address
                    elif isinstance(result, dict):
                        creator_address = result.get("contractCreator", "").lower()
                        if creator_address:
                            logger.info(f"✅ BSCScan: {token_address[:8]}... creator={creator_address[:8]}...")
                            return creator_address
        
        # Способ 2: Если не удалось получить адрес создателя токена, пробуем получить адрес создателя пула
        if pair_address:
            params_pair = {
                "module": "contract",
                "action": "getcontractcreation",
                "contractaddresses": pair_address,
                "apikey": BSCSCAN_API_KEY
            }
            
            async with session.get(url, params=params_pair, timeout=15) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("status") == "1" and data.get("result"):
                        result = data["result"]
                        if isinstance(result, list) and len(result) > 0:
                            creator_address = result[0].get("contractCreator", "").lower()
                            if creator_address:
                                logger.info(f"✅ BSCScan (pair): {pair_address[:8]}... creator={creator_address[:8]}...")
                                return creator_address
                        elif isinstance(result, dict):
                            creator_address = result.get("contractCreator", "").lower()
                            if creator_address:
                                logger.info(f"✅ BSCScan (pair): {pair_address[:8]}... creator={creator_address[:8]}...")
                                return creator_address
        
        # Способ 3: Получаем первую транзакцию пула (если пул создан через factory, проверяем кто вызвал factory)
        if pair_address:
            params_pair_tx = {
                "module": "account",
                "action": "txlist",
                "address": pair_address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 10,  # Проверяем первые 10 транзакций
                "sort": "asc",
                "apikey": BSCSCAN_API_KEY
            }
            
            async with session.get(url, params=params_pair_tx, timeout=15) as r:
                if r.status == 200:
                    data = await r.json()
                    # Проверяем result даже если status != "1" (иногда BSCScan возвращает данные при status=0)
                    result = data.get("result")
                    if isinstance(result, list) and len(result) > 0:
                        factory_addresses = ["0xca143ce32fe78f1f7019d7d551a6402fc5350c73"]  # PancakeSwap Factory
                        # Проверяем первые транзакции, ищем транзакцию к factory
                        for tx in result[:10]:
                            if isinstance(tx, dict):
                                creator_address = tx.get("from", "").lower()
                                to_address = tx.get("to", "").lower()
                                
                                # Если пул создан через factory, from будет адрес того, кто вызвал factory
                                if to_address in [addr.lower() for addr in factory_addresses] and creator_address:
                                    logger.info(f"✅ BSCScan (pair tx from factory caller): {pair_address[:8]}... creator={creator_address[:8]}...")
                                    return creator_address
                        
                        # Если не нашли транзакцию к factory, возвращаем адрес первой транзакции
                        first_tx = result[0]
                        if isinstance(first_tx, dict):
                            creator_address = first_tx.get("from", "").lower()
                            if creator_address:
                                logger.info(f"✅ BSCScan (pair first tx): {pair_address[:8]}... creator={creator_address[:8]}...")
                                return creator_address
        
        # Способ 4: Получаем первую транзакцию токена (от кого была отправлена)
        params_tx = {
            "module": "account",
            "action": "txlist",
            "address": token_address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 10,  # Проверяем первые 10 транзакций
            "sort": "asc",
            "apikey": BSCSCAN_API_KEY
        }
        
        async with session.get(url, params=params_tx, timeout=15) as r:
            if r.status == 200:
                data = await r.json()
                # Проверяем result даже если status != "1"
                result = data.get("result")
                if isinstance(result, list) and len(result) > 0:
                    factory_addresses = ["0xca143ce32fe78f1f7019d7d551a6402fc5350c73"]
                    # Проверяем первые транзакции, ищем транзакцию к factory
                    for tx in result[:10]:
                        if isinstance(tx, dict):
                            creator_address = tx.get("from", "").lower()
                            to_address = tx.get("to", "").lower()
                            
                            # Если токен создан через factory, from будет адрес того, кто вызвал factory
                            if to_address in [addr.lower() for addr in factory_addresses] and creator_address:
                                logger.info(f"✅ BSCScan (token tx from factory caller): {token_address[:8]}... creator={creator_address[:8]}...")
                                return creator_address
                    
                    # Если не нашли транзакцию к factory, возвращаем адрес первой транзакции
                    first_tx = result[0]
                    if isinstance(first_tx, dict):
                        creator_address = first_tx.get("from", "").lower()
                        if creator_address:
                            logger.info(f"✅ BSCScan (token first tx): {token_address[:8]}... creator={creator_address[:8]}...")
                            return creator_address
        
        logger.debug(f"BSCScan API returned no creator address for {token_address[:8]}...")
        return None
                
    except Exception as e:
        logger.debug(f"BSCScan API exception for creator address: {e}")
        return None

# Файл кеша для отслеженных токенов
CACHE_FILE = "tracked_tokens.json"

# =========================
# Настройка логирования
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("new_tokens_bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================
# Структуры данных
# =========================

class TokenTracker:
    """Отслеживает токены и их объемы во времени"""
    def __init__(self):
        self.tokens: Dict[str, Dict[str, Any]] = {}  # token_address -> data
        self.alerted: Set[str] = set()  # Токены, по которым уже отправлен alert
        self.last_alert_at: Dict[str, datetime] = {}  # Время последнего алерта
        self.volume_history: Dict[str, List[Dict]] = {}  # История объемов для отслеживания всплесков
        self.spike_alerted: Set[str] = set()  # Токены, по которым уже отправлен spike alert
        # Загружаем персистентный кеш, чтобы не дублировать алерты после рестартов
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    alerted_map = data.get("alerted", {}) if isinstance(data, dict) else {}
                    for addr, ts in alerted_map.items():
                        self.alerted.add(addr.lower())
                        try:
                            self.last_alert_at[addr.lower()] = datetime.fromisoformat(ts)
                        except Exception:
                            pass
        except Exception:
            # Не мешаем запуску, если файл битый
            pass
    
    def update(self, token_address: str, volume_5m: float, pool_data: Dict):
        """Обновляет данные токена"""
        now = datetime.now(timezone.utc)
        
        if token_address not in self.tokens:
            self.tokens[token_address] = {
                "first_seen": now,
                "checks": [],
                "pool_data": pool_data
            }
        
        # Добавляем новую проверку
        self.tokens[token_address]["checks"].append({
            "time": now,
            "volume_5m": volume_5m
        })
        
        # Обновляем данные пула
        self.tokens[token_address]["pool_data"] = pool_data
        
        # Удаляем старые проверки (старше 10 минут)
        cutoff = now - timedelta(minutes=10)
        self.tokens[token_address]["checks"] = [
            c for c in self.tokens[token_address]["checks"]
            if c["time"] > cutoff
        ]
    
    def is_stable(self, token_address: str) -> bool:
        """Проверяет, стабилен ли объем токена"""
        if token_address not in self.tokens:
            return False
        
        checks = self.tokens[token_address]["checks"]
        
        # Нужно минимум MIN_STABILITY_CHECKS проверок
        if len(checks) < MIN_STABILITY_CHECKS:
            return False
        
        # Проверяем, что во всех последних проверках объем > порога для новых токенов
        recent_checks = checks[-MIN_STABILITY_CHECKS:]
        return all(c["volume_5m"] >= MIN_5M_VOLUME_USD_NEW for c in recent_checks)
    
    def get_pool_data(self, token_address: str) -> Optional[Dict]:
        """Возвращает данные пула"""
        if token_address not in self.tokens:
            return None
        return self.tokens[token_address]["pool_data"]
    
    def mark_alerted(self, token_address: str):
        """Отмечает, что по токену отправлен alert"""
        addr = token_address.lower()
        self.alerted.add(addr)
        self.last_alert_at[addr] = datetime.now(timezone.utc)
        # Сохраняем в файл для персистентного dedup
        try:
            payload = {"alerted": {a: self.last_alert_at.get(a, datetime.now(timezone.utc)).isoformat() for a in self.alerted}}
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f)
        except Exception:
            pass
    
    def is_alerted(self, token_address: str) -> bool:
        """Проверяет, был ли уже отправлен alert"""
        # Нормализуем адрес для проверки
        return token_address.lower() in self.alerted

    def recently_alerted(self, token_address: str, minutes: int = 10) -> bool:
        """Был ли алерт по токену в последние N минут"""
        ts = self.last_alert_at.get(token_address)
        if not ts:
            return False
        return (datetime.now(timezone.utc) - ts) <= timedelta(minutes=minutes)
    
    def cleanup_old(self):
        """Удаляет старые токены"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=DEDUP_TTL_HOURS)
        
        to_remove = [
            addr for addr, data in self.tokens.items()
            if data["first_seen"] < cutoff
        ]
        
        for addr in to_remove:
            del self.tokens[addr]
            self.alerted.discard(addr)
            self.last_alert_at.pop(addr, None)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tokens")
    
    def update_volume_history(self, token_address: str, volume_5m: float):
        """Обновляет историю объемов для отслеживания всплесков"""
        now = datetime.now(timezone.utc)
        addr = token_address.lower()
        
        if addr not in self.volume_history:
            self.volume_history[addr] = []
        
        # Добавляем текущий объем
        self.volume_history[addr].append({
            "volume": volume_5m,
            "timestamp": now
        })
        
        # Очищаем старые записи (старше 1 часа)
        cutoff = now - timedelta(hours=1)
        self.volume_history[addr] = [
            entry for entry in self.volume_history[addr]
            if entry["timestamp"] > cutoff
        ]
    
    def check_volume_spike(self, token_address: str, current_volume: float) -> Optional[float]:
        """Проверяет, есть ли всплеск объема (3x рост за 5 минут)
        Возвращает коэффициент роста или None если всплеска нет
        """
        addr = token_address.lower()
        
        if addr not in self.volume_history or len(self.volume_history[addr]) < 2:
            return None
        
        now = datetime.now(timezone.utc)
        five_minutes_ago = now - timedelta(minutes=5)
        
        # Находим объем 5 минут назад
        historical_volumes = [
            entry["volume"] for entry in self.volume_history[addr]
            if entry["timestamp"] <= five_minutes_ago
        ]
        
        if not historical_volumes:
            return None
        
        # Берем последний объем из 5-минутного окна
        previous_volume = historical_volumes[-1]
        
        # Проверяем рост в 3 раза
        if previous_volume > 0 and current_volume >= previous_volume * 3:
            growth_multiplier = current_volume / previous_volume
            logger.info(f"🚀 Volume spike detected: {token_address} from ${previous_volume:,.0f} to ${current_volume:,.0f} ({growth_multiplier:.1f}x)")
            return growth_multiplier
        
        return None
    
    def mark_spike_alerted(self, token_address: str):
        """Отмечает, что по токену отправлен spike alert"""
        self.spike_alerted.add(token_address.lower())
    
    def is_spike_alerted(self, token_address: str) -> bool:
        """Проверяет, был ли уже отправлен spike alert"""
        return token_address.lower() in self.spike_alerted

# =========================
# Telegram API
# =========================

async def tg_send(
    session: aiohttp.ClientSession,
    text: str,
    chat_id: str = None,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> bool:
    """Отправка сообщения в Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not set")
        return False
    
    # Выбираем канал в зависимости от режима
    if chat_id:
        target_chat = chat_id
    elif TEST_MODE and TELEGRAM_TEST_CHAT_ID:
        target_chat = TELEGRAM_TEST_CHAT_ID
        logger.info("🧪 TEST MODE: Sending to test channel")
    else:
        target_chat = TELEGRAM_CHAT_ID
    
    if not target_chat:
        logger.warning("No Telegram chat ID configured")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Логируем отправку для отладки дублирования
    logger.info(f"📤 Sending Telegram message to {target_chat}")
    
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        # Disable previews to avoid GMGN attachment card in Telegram
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        async with session.post(url, json=payload, timeout=30) as r:
            if r.status != 200:
                body = await r.text()
                logger.error(f"Telegram send error {r.status}: {body[:200]}")
                return False
            logger.info(f"✅ Telegram message sent successfully")
            return True
    except Exception as e:
        logger.error(f"Telegram exception: {e}")
        return False

# =========================
# Inline buttons helpers
# =========================

def build_trade_bot_keyboard(token_addr: str) -> Optional[Dict[str, Any]]:
    """Builds inline keyboard with Maestro / Axiom / Based links for TEST_MODE.
    Uses env templates for Maestro/Axiom if provided. Always includes Based link.
    """
    try:
        buttons: List[List[Dict[str, str]]] = []

        row: List[Dict[str, str]] = []

        if MAESTRO_URL_TEMPLATE:
            row.append({
                "text": "Maestro",
                "url": MAESTRO_URL_TEMPLATE.format(token=token_addr)
            })
        if AXIOM_URL_TEMPLATE:
            row.append({
                "text": "Axiom",
                "url": AXIOM_URL_TEMPLATE.format(token=token_addr)
            })

        # Based bot link - fixed template
        based_url = f"https://t.me/based_eth_bot?start=r_darkzodchi_b_{token_addr}"
        row.append({"text": "Based Bot", "url": based_url})

        if row:
            buttons.append(row)
            return {"inline_keyboard": buttons}
    except Exception:
        pass
    return None

# =========================
# DexScreener API
# =========================

async def fetch_dexscreener_new_pairs(session: aiohttp.ClientSession) -> List[Dict]:
    """Получает новые пары с DexScreener"""
    try:
        # Получаем топ пары по объему и фильтруем по времени
        url = "https://api.dexscreener.com/latest/dex/search"
        params = {"q": "bsc"}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
            # Фильтруем только BSC пары
            bsc_pairs = [p for p in pairs if p.get("chainId") == "bsc"]
            
            # Сортируем по времени создания (новые сначала)
            bsc_pairs.sort(key=lambda x: x.get("pairCreatedAt", 0), reverse=True)
            
            logger.info(f"DexScreener: fetched {len(bsc_pairs)} BSC pairs")
            return bsc_pairs
    
    except Exception as e:
        logger.error(f"DexScreener exception: {e}")
        return []

async def fetch_dexscreener_usd1_pairs(session: aiohttp.ClientSession) -> List[Dict]:
    """Получает USD1 пары с DexScreener для BSC сети"""
    try:
        # Важно: DexScreener search по "USD1 bsc" часто возвращает пары без volume.
        # Надежнее получать пары через endpoint токена по адресу USD1.
        # Адрес USD1 на BSC берем из GeckoTerminal (base_token.id в пуле USD1/USDT):
        # bsc_0x8d0d000ee44948fc98c9b98a4fa4921476f08b0d
        usd1_token_address = os.getenv("USD1_TOKEN_ADDRESS_BSC", "0x8d0d000ee44948fc98c9b98a4fa4921476f08b0d").strip().lower()

        pairs = await fetch_dexscreener_token_by_address(session, usd1_token_address)

        # Фильтруем только BSC пары с USD1 (на всякий случай)
        usd1_pairs: List[Dict] = []
        for p in pairs:
            if p.get("chainId") != "bsc":
                continue
            base_symbol = (p.get("baseToken", {}) or {}).get("symbol", "").upper()
            quote_symbol = (p.get("quoteToken", {}) or {}).get("symbol", "").upper()
            if base_symbol == "USD1" or quote_symbol == "USD1":
                usd1_pairs.append(p)
            
        # Сортируем по времени создания (новые сначала)
        usd1_pairs.sort(key=lambda x: x.get("pairCreatedAt", 0), reverse=True)
        
        logger.info(f"DexScreener USD1: fetched {len(usd1_pairs)} USD1 BSC pairs")
        return usd1_pairs
    
    except Exception as e:
        logger.error(f"DexScreener USD1 exception: {e}")
        return []

async def fetch_dexscreener_token_by_address(session: aiohttp.ClientSession, token_address: str) -> List[Dict]:
    """Получает пары для конкретного токена по адресу"""
    try:
        url = "https://api.dexscreener.com/latest/dex/tokens"
        params = {"addresses": token_address}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener token search error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
            # Фильтруем только BSC пары
            bsc_pairs = [p for p in pairs if p.get("chainId") == "bsc"]
            
            logger.info(f"DexScreener token search: found {len(bsc_pairs)} BSC pairs for {token_address[:10]}...")
            return bsc_pairs
    
    except Exception as e:
        logger.error(f"DexScreener token search exception: {e}")
        return []

# =========================
# GeckoTerminal API
# =========================

async def fetch_geckoterminal_new_pools(session: aiohttp.ClientSession, page: int = 1) -> List[Dict]:
    """Получает новые пулы с GeckoTerminal"""
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/bsc/new_pools"
        params = {"page": page}
        
        # Добавляем User-Agent для избежания блокировок
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with session.get(url, params=params, headers=headers, timeout=20) as r:
            if r.status == 429:  # Rate limit
                logger.warning(f"GeckoTerminal rate limit (429) on page {page}, waiting...")
                await asyncio.sleep(2)
                return []
            elif r.status == 401:  # Unauthorized
                logger.warning(f"GeckoTerminal unauthorized (401) on page {page}")
                return []
            elif r.status != 200:
                logger.error(f"GeckoTerminal error: {r.status}")
                return []
            
            data = await r.json()
            pools = data.get("data", [])
            
            logger.info(f"GeckoTerminal: fetched {len(pools)} pools (page {page})")
            return pools
    
    except Exception as e:
        logger.error(f"GeckoTerminal exception: {e}")
        return []

# =========================
# GeckoTerminal Trending (Established spikes)
# =========================

async def fetch_geckoterminal_trending_pools(session: aiohttp.ClientSession, page: int = 1) -> List[Dict]:
    """Получает трендовые пулы (высокий 5m объем) с GeckoTerminal
    Используем как источник для established spike watcher.
    """
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/bsc/trending_pools"
        params = {"page": page}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        async with session.get(url, params=params, headers=headers, timeout=20) as r:
            if r.status == 429:
                logger.warning(f"GeckoTerminal trending rate limit (429) on page {page}, waiting...")
                await asyncio.sleep(2)
                return []
            elif r.status != 200:
                logger.error(f"GeckoTerminal trending error: {r.status}")
                return []

            data = await r.json()
            pools = data.get("data", [])

            logger.info(f"GeckoTerminal: fetched {len(pools)} trending pools (page {page})")
            return pools

    except Exception as e:
        logger.error(f"GeckoTerminal trending exception: {e}")
        return []

async def fetch_geckoterminal_usd1_pools(session: aiohttp.ClientSession) -> List[Dict]:
    """Получает USD1 пары с GeckoTerminal для BSC сети
    GeckoTerminal имеет данные по объему для USD1 пар, в отличие от DexScreener
    """
    try:
        url = "https://api.geckoterminal.com/api/v2/search/pools"
        params = {"query": "USD1", "network": "bsc"}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        async with session.get(url, params=params, headers=headers, timeout=20) as r:
            if r.status == 429:
                logger.warning(f"GeckoTerminal USD1 rate limit (429), waiting...")
                await asyncio.sleep(2)
                return []
            elif r.status != 200:
                logger.error(f"GeckoTerminal USD1 error: {r.status}")
                return []

            data = await r.json()
            pools = data.get("data", [])

            # Фильтруем только пулы, где USD1 является одним из токенов
            usd1_pools = []
            for pool in pools:
                attrs = pool.get("attributes", {})
                pool_name = attrs.get("name", "").upper()
                # Проверяем, что в названии есть USD1
                if "USD1" in pool_name:
                    usd1_pools.append(pool)

            logger.info(f"GeckoTerminal USD1: fetched {len(usd1_pools)} USD1 BSC pools")
            return usd1_pools

    except Exception as e:
        logger.error(f"GeckoTerminal USD1 exception: {e}")
        return []

# =========================
# Обработка данных
# =========================

def parse_dexscreener_pair(pair: Dict) -> Optional[Dict]:
    """Парсит пару из DexScreener в unified формат"""
    try:
        # Время создания пула
        created_at_ms = pair.get("pairCreatedAt")
        if not created_at_ms:
            return None
        
        created_at = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        
        # Объем за 5 минут
        volume_5m = pair.get("volume", {}).get("m5", 0)
        # Если volume_5m отсутствует, пробуем использовать volume_1h как fallback
        if not volume_5m:
            volume_1h = pair.get("volume", {}).get("h1", 0)
            if volume_1h:
                # Используем 1h volume как приближение для 5m (делим на 12)
                volume_5m = volume_1h / 12
            else:
                # Если и 1h нет, пробуем 24h (делим на 288)
                volume_24h = pair.get("volume", {}).get("h24", 0)
                if volume_24h:
                    volume_5m = volume_24h / 288
                else:
                    # Если вообще нет volume данных, используем 0 (токен не пройдет фильтры, но будет обработан)
                    volume_5m = 0
        
        # Определяем какой токен - новый токен (не WBNB/USDT)
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        # Известные стейблкоины и wrapped токены
        STABLE_TOKENS = ["WBNB", "USDT", "BUSD", "USDC", "USD1", "BNB", "ETH", "WETH", "DAI"]
        
        base_symbol = base_token.get("symbol", "").upper()
        quote_symbol = quote_token.get("symbol", "").upper()
        
        # Выбираем токен, который НЕ является стейблкоином
        if quote_symbol in STABLE_TOKENS and base_symbol not in STABLE_TOKENS:
            # Новый токен - это base token
            new_token = base_token
            pair_symbol = quote_symbol
        elif base_symbol in STABLE_TOKENS and quote_symbol not in STABLE_TOKENS:
            # Новый токен - это quote token
            new_token = quote_token
            pair_symbol = base_symbol
        else:
            # По умолчанию используем base token
            new_token = base_token
            pair_symbol = quote_symbol
        
        token_address = new_token.get("address", "").lower()
        
        if not token_address:
            return None
        
        return {
            "source": "dexscreener",
            "token_address": token_address,
            "token_symbol": new_token.get("symbol", "???"),
            "token_name": new_token.get("name", "Unknown"),
            "pair_address": pair.get("pairAddress", ""),
            "pair_name": f"{new_token.get('symbol', '???')}/{pair_symbol}",
            "dex": pair.get("dexId", "unknown"),
            "created_at": created_at,
            "age_hours": age_hours,
            "volume_5m": volume_5m,
            "volume_1h": pair.get("volume", {}).get("h1", 0),
            "volume_24h": pair.get("volume", {}).get("h24", 0),
            "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
            "fdv": pair.get("fdv"),
            "market_cap": pair.get("marketCap"),
            "price_usd": pair.get("priceUsd"),
            "price_change_5m": pair.get("priceChange", {}).get("m5", 0),
            "txns_5m_buys": pair.get("txns", {}).get("m5", {}).get("buys", 0),
            "txns_5m_sells": pair.get("txns", {}).get("m5", {}).get("sells", 0),
            "url": pair.get("url", "")
        }
    
    except Exception as e:
        logger.debug(f"Error parsing DexScreener pair: {e}")
        return None

def parse_geckoterminal_pool(pool: Dict) -> Optional[Dict]:
    """Парсит пул из GeckoTerminal в unified формат"""
    try:
        attrs = pool.get("attributes", {})
        
        # Время создания пула
        created_at_str = attrs.get("pool_created_at")
        if not created_at_str:
            return None
        
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        
        # Объем за 5 минут (может быть строкой!)
        volume_5m_raw = attrs.get("volume_usd", {}).get("m5", 0)
        if isinstance(volume_5m_raw, str):
            volume_5m = float(volume_5m_raw) if volume_5m_raw else 0
        else:
            volume_5m = float(volume_5m_raw) if volume_5m_raw else 0
        
        if not volume_5m:
            return None
        
        # Адрес пула
        pool_address = attrs.get("address", "").lower()
        if not pool_address:
            return None
        
        # Извлекаем адреса токенов из relationships
        relationships = pool.get("relationships", {})
        base_token_rel = relationships.get("base_token", {})
        base_token_data = base_token_rel.get("data", {})
        base_token_address = base_token_data.get("id", "").replace("bsc_", "").lower() if base_token_data else None
        
        quote_token_rel = relationships.get("quote_token", {})
        quote_token_data = quote_token_rel.get("data", {})
        quote_token_address = quote_token_data.get("id", "").replace("bsc_", "").lower() if quote_token_data else None
        
        # Определяем, какой токен является новым токеном (не стейблкоин)
        STABLE_TOKENS = ["WBNB", "USDT", "BUSD", "USDC", "USD1", "BNB", "ETH", "WETH", "DAI"]
        
        # Парсим имя пула для определения символов
        pool_name = attrs.get("name", "Unknown")
        name_parts = pool_name.split("/")
        base_symbol = name_parts[0].strip().upper() if len(name_parts) > 0 else ""
        quote_symbol = name_parts[1].split()[0].strip().upper() if len(name_parts) > 1 else ""
        
        # Специальная обработка для USD1 пар: выбираем токен, который НЕ является USD1
        # НО пропускаем, если второй токен тоже стейблкоин (USD1/USDT, USD1/USDC и т.д.)
        if base_symbol == "USD1" and quote_symbol != "USD1":
            # USD1/TOKEN - новый токен это quote token
            # Пропускаем, если quote token тоже стейблкоин
            if quote_symbol in STABLE_TOKENS:
                return None  # Пропускаем пары USD1/STABLECOIN
            token_address = quote_token_address
            token_symbol = quote_symbol
            pair_symbol = base_symbol
        elif quote_symbol == "USD1" and base_symbol != "USD1":
            # TOKEN/USD1 - новый токен это base token
            # Пропускаем, если base token тоже стейблкоин
            if base_symbol in STABLE_TOKENS:
                return None  # Пропускаем пары STABLECOIN/USD1
            token_address = base_token_address
            token_symbol = base_symbol
            pair_symbol = quote_symbol
        elif quote_symbol in STABLE_TOKENS and base_symbol not in STABLE_TOKENS:
            # Новый токен - это base token
            token_address = base_token_address
            token_symbol = base_symbol
            pair_symbol = quote_symbol
        elif base_symbol in STABLE_TOKENS and quote_symbol not in STABLE_TOKENS:
            # Новый токен - это quote token
            token_address = quote_token_address
            token_symbol = quote_symbol
            pair_symbol = base_symbol
        else:
            # По умолчанию используем base token
            token_address = base_token_address
            token_symbol = base_symbol
            pair_symbol = quote_symbol
        
        # Если не получилось извлечь адрес токена, пропускаем этот пул
        if not token_address or token_address == pool_address:
            return None
        
        # Получаем fee percentage если доступен
        pool_fee_percentage = attrs.get("pool_fee_percentage")
        
        # Получаем volume за 24 часа для вычисления fees
        volume_24h = float(attrs.get("volume_usd", {}).get("h24", 0))
        
        return {
            "source": "geckoterminal",
            "token_address": token_address,
            "token_symbol": token_symbol,
            "token_name": pool_name,
            "pair_address": pool_address,
            "pair_name": pool_name,
            "dex": "unknown",  # GeckoTerminal не всегда дает DEX ID
            "created_at": created_at,
            "age_hours": age_hours,
            "volume_5m": volume_5m,
            "volume_1h": float(attrs.get("volume_usd", {}).get("h1", 0)),
            "volume_24h": volume_24h,
            "liquidity_usd": float(attrs.get("reserve_in_usd", 0)),
            "fdv": attrs.get("fdv_usd"),
            "market_cap": attrs.get("market_cap_usd"),
            "price_usd": attrs.get("base_token_price_usd"),
            "price_change_5m": float(attrs.get("price_change_percentage", {}).get("m5", 0)),
            "txns_5m_buys": attrs.get("transactions", {}).get("m5", {}).get("buys", 0),
            "txns_5m_sells": attrs.get("transactions", {}).get("m5", {}).get("sells", 0),
            "pool_fee_percentage": pool_fee_percentage,
            "url": f"https://www.geckoterminal.com/bsc/pools/{pool_address}"
        }
    
    except Exception as e:
        logger.debug(f"Error parsing GeckoTerminal pool: {e}")
        return None

# =========================
# Дополнительные данные токена
# =========================

async def fetch_dextools_token_data(session: aiohttp.ClientSession, token_address: str) -> Dict[str, Any]:
    """
    Получает полные данные о токене из DexTools API
    Возвращает: {holders_count, audit_score, buy_tax, sell_tax, is_honeypot, liquidity_locked, etc}
    Если DexTools недоступен, использует fallback: BSCScan для holders и honeypot.is для honeypot статуса
    """
    if not DEXTOOLS_API_KEY:
        logger.info(f"ℹ️ DexTools API key not configured, using fallback for {token_address[:8]}...")
        # Используем fallback даже без API ключа
        bscscan_holders = await fetch_bscscan_token_holders(session, token_address)
        honeypot_is_result = await fetch_honeypot_is_status(session, token_address)
        
        return {
            "holders_count": bscscan_holders or 0,
            "holders_unavailable": True if not bscscan_holders else False,
            "mcap": 0,
            "fdv": 0,
            "total_supply": 0,
            "circulating_supply": 0,
            "transactions": 0,
            # Ликвидность никогда не берём из DexTools, только из DexScreener / GeckoTerminal
            "price_usd": 0,
            "price_change_24h": 0,
            "volume_24h": 0,
            "website": "",
            "telegram": "",
            "twitter": "",
            "discord": "",
            "dext_score": 0,
            "top10_holders_percent": 0,
            "is_honeypot": honeypot_is_result,  # Используем результат honeypot.is или None
            "is_contract_renounced": False,
            "is_mintable": False,
            "is_proxy": False,
            "is_blacklisted": False,
            "is_potentially_scam": False,
            "buy_tax": None,  # None означает "неизвестно"
            "sell_tax": None  # None означает "неизвестно"
        }
    
    try:
        # DexTools v2 Public API
        headers = {
            "X-API-Key": DEXTOOLS_API_KEY,
            "accept": "application/json"
        }
        
        # Получаем информацию о токене (holders, mcap, etc)
        info_url = f"https://public-api.dextools.io/trial/v2/token/bsc/{token_address}/info"
        
        async with session.get(info_url, headers=headers, timeout=15) as r:
            if r.status == 429:  # Rate limit
                logger.warning(f"DexTools rate limit (429) for token {token_address[:8]}...")
                await asyncio.sleep(2)
                return {}
            elif r.status != 200:
                body = await r.text()
                logger.warning(f"⚠️ DexTools info API error: status {r.status}, body: {body[:200]}")
                # Используем fallback при ошибке API
                bscscan_holders = await fetch_bscscan_token_holders(session, token_address)
                honeypot_is_result = await fetch_honeypot_is_status(session, token_address)
                
                if bscscan_holders or honeypot_is_result is not None:
                    logger.info(f"✅ Fallback successful: holders={bscscan_holders}, honeypot={honeypot_is_result}")
                    return {
                        "holders_count": bscscan_holders or 0,
                        "holders_unavailable": True if not bscscan_holders and honeypot_is_result is None else False,
                        "mcap": 0,
                        "fdv": 0,
                        "total_supply": 0,
                        "circulating_supply": 0,
                        "transactions": 0,
                        # Ликвидность никогда не берём из DexTools, только из DexScreener / GeckoTerminal
                        "price_usd": 0,
                        "price_change_24h": 0,
                        "volume_24h": 0,
                        "website": "",
                        "telegram": "",
                        "twitter": "",
                        "discord": "",
                        "dext_score": 0,
                        "top10_holders_percent": 0,
                        "is_honeypot": honeypot_is_result,
                        "is_contract_renounced": False,
                        "is_mintable": False,
                        "is_proxy": False,
                        "is_blacklisted": False,
                        "is_potentially_scam": False,
                        "buy_tax": None,
                        "sell_tax": None
                    }
                
                return {"holders_unavailable": True}
            
            info_data = await r.json()
        
        # Получаем audit информацию (honeypot, tax, etc)
        audit_url = f"https://public-api.dextools.io/trial/v2/token/bsc/{token_address}/audit"
        
        audit_data = None
        try:
            async with session.get(audit_url, headers=headers, timeout=15) as r:
                if r.status != 200:
                    body = await r.text()
                    logger.debug(f"DexTools audit API error: status {r.status}, body: {body[:200]}")
                    audit_data = None
                else:
                    audit_data = await r.json()
        except Exception as e:
            logger.debug(f"DexTools audit API exception: {e}")
            audit_data = None
        
        # Извлекаем нужные данные
        result = {}
        
        # Holders and market cap from /info endpoint
        if "data" in info_data:
            info = info_data["data"]
            result["holders_count"] = info.get("holders", 0)
            result["mcap"] = info.get("mcap", 0)
            result["fdv"] = info.get("fdv", 0)
            result["total_supply"] = info.get("totalSupply", 0)
            result["circulating_supply"] = info.get("circulatingSupply", 0)
            result["transactions"] = info.get("transactions", 0)
            
            # Если нет данных о держателях из DexTools, пробуем BSCScan
            if not result["holders_count"]:
                bscscan_holders = await fetch_bscscan_token_holders(session, token_address)
                if bscscan_holders:
                    result["holders_count"] = bscscan_holders
                    logger.info(f"🔄 Using BSCScan fallback for holders: {bscscan_holders}")
                else:
                    # Если оба API не дали данных, помечаем как 0 для специальной обработки
                    result["holders_count"] = 0
                    result["holders_unavailable"] = True
            
            # Дополнительная информация
            # Ликвидность никогда не берём из DexTools, только из DexScreener / GeckoTerminal
            result["price_usd"] = info.get("price", 0)
            result["price_change_24h"] = info.get("priceChange24h", 0)
            result["volume_24h"] = info.get("volume24h", 0)
            
            # Социальные ссылки
            result["website"] = info.get("website", "")
            result["telegram"] = info.get("telegram", "")
            result["twitter"] = info.get("twitter", "")
            result["discord"] = info.get("discord", "")
            
            # DEXTScore (если доступен) - проверяем несколько возможных полей
            dext_score_raw = (
                info.get("dextScore") or 
                info.get("dext_score") or 
                info.get("score") or 
                info.get("DEXTScore") or 
                info.get("dext") or
                None
            )
            # Конвертируем в число если это строка
            if dext_score_raw is not None:
                try:
                    if isinstance(dext_score_raw, str):
                        result["dext_score"] = float(dext_score_raw)
                    else:
                        result["dext_score"] = float(dext_score_raw) if dext_score_raw else 0
                except (ValueError, TypeError):
                    result["dext_score"] = 0
            else:
                result["dext_score"] = 0
            
            # Если dextScore равен 0 или None, пробуем получить из audit endpoint
            if (not result["dext_score"] or result["dext_score"] == 0) and audit_data:
                audit = audit_data.get("data", {}) if isinstance(audit_data, dict) else {}
                if isinstance(audit, dict):
                    audit_score_raw = (
                        audit.get("dextScore") or 
                        audit.get("dext_score") or 
                        audit.get("score") or 
                        audit.get("DEXTScore") or
                        audit.get("dext") or
                        None
                    )
                    if audit_score_raw is not None:
                        try:
                            if isinstance(audit_score_raw, str):
                                audit_score = float(audit_score_raw)
                            else:
                                audit_score = float(audit_score_raw) if audit_score_raw else 0
                            if audit_score > 0:
                                result["dext_score"] = audit_score
                        except (ValueError, TypeError):
                            pass
            
            # Логируем для отладки
            if result.get("dext_score"):
                logger.debug(f"DextScore для {token_address[:8]}...: {result['dext_score']} (из info: {info.get('dextScore')}, из audit: {audit_data.get('data', {}).get('dextScore') if audit_data else None})")
            
            # Топ холдеры
            result["top10_holders_percent"] = info.get("top10HoldersPercent", 0)
        
        # Audit/Security info from /audit endpoint (if available)
        if audit_data and "data" in audit_data and audit_data["data"] is not None:
            audit = audit_data["data"]
            # Convert "yes"/"no" strings to boolean
            result["is_honeypot"] = audit.get("isHoneypot", "no") == "yes"
            result["is_contract_renounced"] = audit.get("isContractRenounced", "no") == "yes"
            result["is_mintable"] = audit.get("isMintable", "no") == "yes"
            result["is_proxy"] = audit.get("isProxy", "no") == "yes"
            result["is_blacklisted"] = audit.get("isBlacklisted", "no") == "yes"
            result["is_potentially_scam"] = audit.get("isPotentiallyScam", "no") == "yes"
            
            # Tax info
            buy_tax_data = audit.get("buyTax", {})
            sell_tax_data = audit.get("sellTax", {})
            result["buy_tax"] = buy_tax_data.get("max", 0) if isinstance(buy_tax_data, dict) else 0
            result["sell_tax"] = sell_tax_data.get("max", 0) if isinstance(sell_tax_data, dict) else 0
        else:
            # Set defaults when audit data is not available
            # Пробуем honeypot.is fallback для проверки honeypot статуса
            logger.info(f"🔄 DexTools audit unavailable, trying honeypot.is fallback for {token_address[:8]}...")
            honeypot_is_result = await fetch_honeypot_is_status(session, token_address)
            
            if honeypot_is_result is not None:
                result["is_honeypot"] = honeypot_is_result
                logger.info(f"✅ Honeypot.is fallback successful: honeypot={honeypot_is_result}")
            else:
                # Безопасный подход: если нет данных audit, считаем потенциально опасным
                result["is_honeypot"] = None  # None означает "неизвестно"
                logger.info(f"⚠️ No honeypot data available from any source for {token_address[:8]}...")
            
            result["is_contract_renounced"] = False
            result["is_mintable"] = False
            result["is_proxy"] = False
            result["is_blacklisted"] = False
            result["is_potentially_scam"] = False
            result["buy_tax"] = None  # None означает "неизвестно"
            result["sell_tax"] = None  # None означает "неизвестно"
        
        logger.info(f"✅ DexTools: {token_address[:8]}... holders={result.get('holders_count')}, honeypot={result.get('is_honeypot')}, tax={result.get('buy_tax')}/{result.get('sell_tax')}, dext_score={result.get('dext_score')}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ DexTools API exception: {e}", exc_info=True)
        
        # Fallback: пробуем получить хотя бы держателей через BSCScan и honeypot статус через honeypot.is
        logger.info(f"🔄 DexTools failed, trying BSCScan + honeypot.is fallback for {token_address[:8]}...")
        bscscan_holders = await fetch_bscscan_token_holders(session, token_address)
        honeypot_is_result = await fetch_honeypot_is_status(session, token_address)
        
        if bscscan_holders or honeypot_is_result is not None:
            logger.info(f"✅ Fallback successful: holders={bscscan_holders}, honeypot={honeypot_is_result}")
            return {
                "holders_count": bscscan_holders or 0,
                "holders_unavailable": True if not bscscan_holders and honeypot_is_result is None else False,
                "mcap": 0,
                "fdv": 0,
                "total_supply": 0,
                "circulating_supply": 0,
                "transactions": 0,
                "liquidity_usd": 0,
                "price_usd": 0,
                "price_change_24h": 0,
                "volume_24h": 0,
                "website": "",
                "telegram": "",
                "twitter": "",
                "discord": "",
                "dext_score": 0,
                "top10_holders_percent": 0,
                "is_honeypot": honeypot_is_result,  # Используем результат honeypot.is или None
                "is_contract_renounced": False,
                "is_mintable": False,
                "is_proxy": False,
                "is_blacklisted": False,
                "is_potentially_scam": False,
                "buy_tax": None,  # None означает "неизвестно"
                "sell_tax": None  # None означает "неизвестно"
            }
        
        # Если все fallback не сработали, возвращаем минимальные данные
        return {"holders_unavailable": True}

async def fetch_gmgn_token_data(session: aiohttp.ClientSession, token_address: str) -> Dict[str, Any]:
    """
    Получает данные о токене из GMGN (bundler %, total fees, creator_address)
    
    ПРИОРИТЕТ 1: Пробует Apify API (GMGN Token Stat Scraper) - более надежно
    ПРИОРИТЕТ 2: Fallback на парсинг HTML страницы GMGN
    
    Возвращает: {bundler_percentage: float, total_fees_bnb: float, creator_address: str} или {}
    """
    result = {}
    
    # ПРИОРИТЕТ 1: Пробуем Apify API (если настроен)
    apify_token = os.getenv("APIFY_API_TOKEN", "")
    if apify_token:
        try:
            apify_data = await fetch_gmgn_via_apify(session, token_address, apify_token)
            if apify_data:
                result.update(apify_data)
                logger.info(f"✅ GMGN data from Apify for {token_address[:8]}...: bundler={result.get('bundler_percentage')}, total_fees={result.get('total_fees_bnb')}, top10={result.get('top_10_holder_rate')}, creator_count={result.get('creator_open_count')}")
                return result
            else:
                logger.warning(f"⚠️ Apify returned empty data for {token_address[:8]}..., trying HTML fallback...")
        except Exception as e:
            logger.warning(f"Apify GMGN fetch failed for {token_address[:8]}...: {e}, trying HTML fallback...")
    
    # ПРИОРИТЕТ 2: Fallback на парсинг HTML (если Apify недоступен или не настроен)
    result = {}
    try:
        url = f"https://gmgn.ai/bsc/token/{token_address}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        async with session.get(url, headers=headers, timeout=15) as r:
            if r.status != 200:
                logger.debug(f"GMGN HTTP error: status {r.status} for {token_address[:8]}...")
                return result
            
            html = await r.text()
            
            # Парсим HTML с помощью BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            
            # Ищем bundler percentage
            # GMGN показывает bundler в разных местах, пробуем несколько вариантов
            bundler_found = False
            
            # Вариант 1: Ищем текст "Bundler" и извлекаем процент
            bundler_elements = soup.find_all(string=re.compile(r'Bundler', re.I))
            for element in bundler_elements:
                # Ищем родительский элемент и соседние элементы с процентом
                parent = element.parent if hasattr(element, 'parent') else None
                if parent:
                    # Ищем процент в тексте родителя или соседних элементов
                    text = parent.get_text() if hasattr(parent, 'get_text') else str(parent)
                    # Ищем паттерн типа "33.6%" или "33.6 %"
                    bundler_match = re.search(r'(\d+\.?\d*)\s*%', text)
                    if bundler_match:
                        try:
                            bundler_value = float(bundler_match.group(1))
                            result["bundler_percentage"] = bundler_value
                            bundler_found = True
                            logger.debug(f"GMGN bundler found: {bundler_value}% for {token_address[:8]}...")
                            break
                        except (ValueError, AttributeError):
                            continue
            
            # Вариант 2: Ищем через data-атрибуты или классы (если известна структура)
            if not bundler_found:
                # Ищем элементы с классом или атрибутом, содержащим "bundler"
                bundler_divs = soup.find_all(attrs={'class': re.compile(r'bundler', re.I)})
                for div in bundler_divs:
                    text = div.get_text()
                    bundler_match = re.search(r'(\d+\.?\d*)\s*%', text)
                    if bundler_match:
                        try:
                            bundler_value = float(bundler_match.group(1))
                            result["bundler_percentage"] = bundler_value
                            bundler_found = True
                            logger.debug(f"GMGN bundler found (via class): {bundler_value}% for {token_address[:8]}...")
                            break
                        except (ValueError, AttributeError):
                            continue
            
            # Ищем Total Fees в BNB
            # Вариант 1: Ищем текст "Total Fees" и извлекаем значение в BNB
            total_fees_found = False
            fees_elements = soup.find_all(string=re.compile(r'Total\s+Fees?', re.I))
            for element in fees_elements:
                parent = element.parent if hasattr(element, 'parent') else None
                if parent:
                    text = parent.get_text() if hasattr(parent, 'get_text') else str(parent)
                    # Ищем паттерн типа "0.017 BNB" или "0.017BNB"
                    fees_match = re.search(r'(\d+\.?\d*)\s*BNB', text, re.I)
                    if fees_match:
                        try:
                            fees_value = float(fees_match.group(1))
                            result["total_fees_bnb"] = fees_value  # Сохраняем как total_fees_bnb для совместимости
                            total_fees_found = True
                            logger.debug(f"GMGN total fees found: {fees_value} BNB for {token_address[:8]}...")
                            break
                        except (ValueError, AttributeError):
                            continue
            
            # Вариант 2: Ищем через data-атрибуты или классы
            if not total_fees_found:
                fees_divs = soup.find_all(attrs={'class': re.compile(r'fee|cost', re.I)})
                for div in fees_divs:
                    text = div.get_text()
                    fees_match = re.search(r'(\d+\.?\d*)\s*BNB', text, re.I)
                    if fees_match:
                        try:
                            fees_value = float(fees_match.group(1))
                            result["total_fees_bnb"] = fees_value
                            total_fees_found = True
                            logger.debug(f"GMGN total fees found (via class): {fees_value} BNB for {token_address[:8]}...")
                            break
                        except (ValueError, AttributeError):
                            continue
            
            # Вариант 3: Пробуем найти в JSON данных страницы (если GMGN использует client-side rendering)
            # Ищем script теги с JSON данными
            script_tags = soup.find_all('script', type=re.compile(r'application/json|text/javascript', re.I))
            for script in script_tags:
                try:
                    script_text = script.string or script.get_text()
                    # Ищем bundler в JSON
                    if 'bundler' in script_text.lower() or 'batch' in script_text.lower():
                        # Пробуем извлечь JSON и найти bundler
                        json_match = re.search(r'["\']bundler["\']\s*:\s*(\d+\.?\d*)', script_text, re.I)
                        if json_match:
                            bundler_value = float(json_match.group(1))
                            result["bundler_percentage"] = bundler_value
                            bundler_found = True
                            logger.debug(f"GMGN bundler found (via JSON): {bundler_value}% for {token_address[:8]}...")
                    
                    # Ищем total fees в JSON
                    if 'total.*fee' in script_text.lower() or 'network.*cost' in script_text.lower():
                        fees_match = re.search(r'["\']total.*fee["\']\s*:\s*(\d+\.?\d*)', script_text, re.I)
                        if fees_match:
                            fees_value = float(fees_match.group(1))
                            result["total_fees_bnb"] = fees_value
                            total_fees_found = True
                            logger.debug(f"GMGN total fees found (via JSON): {fees_value} BNB for {token_address[:8]}...")
                except Exception:
                    continue
            
            if result:
                logger.debug(f"✅ GMGN data extracted for {token_address[:8]}...: bundler={result.get('bundler_percentage')}, total_fees={result.get('total_fees_bnb')}")
            else:
                logger.debug(f"⚠️ GMGN data not found for {token_address[:8]}... (page structure may have changed)")
            
            return result
    
    except asyncio.TimeoutError:
        logger.debug(f"GMGN timeout for {token_address[:8]}...")
        return result
    except Exception as e:
        logger.debug(f"GMGN fetch error for {token_address[:8]}...: {e}")
        return result

async def fetch_gmgn_via_apify(session: aiohttp.ClientSession, token_address: str, apify_token: str) -> Dict[str, Any]:
    """
    Получает данные о токене через Apify GMGN Token Stat Scraper
    Возвращает: {bundler_percentage: float, total_fees_bnb: float, creator_address: str} или {}
    """
    result = {}
    
    try:
        # Apify API
        base_url = "https://api.apify.com/v2"
        actor_id = "muhammetakkurtt~gmgn-token-stat-scraper"  # ВАЖНО: используем ~ вместо / в URL
        headers = {
            "Authorization": f"Bearer {apify_token}",
            "Content-Type": "application/json"
        }
        
        # Запускаем актор синхронно (с таймаутом)
        input_data = {
            "tokenAddresses": [token_address],
            "chain": "bsc",
            "proxyConfiguration": {
                "useApifyProxy": True
            }
        }
        
        # Запуск актора
        run_url = f"{base_url}/acts/{actor_id}/runs"
        async with session.post(run_url, headers=headers, json=input_data, timeout=30) as resp:
            if resp.status != 201:
                err_body = (await resp.text())[:200]
                logger.warning(f"Apify run failed: HTTP {resp.status} for {token_address[:8]}... — {err_body}")
                return result
            
            run_data = await resp.json()
            run_id = run_data["data"]["id"]
            logger.info(f"Apify run started for {token_address[:8]}... run_id={run_id}")
        
        # Ждем завершения (максимум 2 минуты для одного токена)
        status_url = f"{base_url}/actor-runs/{run_id}"
        max_wait = 120
        waited = 0
        
        while waited < max_wait:
            await asyncio.sleep(3)
            waited += 3
            
            async with session.get(status_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    status = status_data["data"]["status"]
                    
                    if status == "SUCCEEDED":
                        break
                    elif status in ["FAILED", "ABORTED"]:
                        logger.warning(f"Apify run {status} for {token_address[:8]}... run_id={run_id}")
                        return result
        
        if waited >= max_wait:
            logger.warning(f"Apify timeout after {max_wait}s for {token_address[:8]}... run_id={run_id}")
            return result
        
        # Получаем результаты
        dataset_url = f"{base_url}/actor-runs/{run_id}/dataset/items"
        async with session.get(dataset_url, headers=headers, timeout=10) as resp:
            if resp.status != 200:
                logger.warning(f"Apify dataset fetch failed: HTTP {resp.status} for {token_address[:8]}...")
                return result
            
            results = await resp.json()
            if not results:
                logger.warning(f"Apify returned 0 items for {token_address[:8]}... (token may not be on GMGN yet)")
                return result
            
            token_data = results[0]
            
            # Ищем total_fee (snake_case) или totalFee (camelCase) — total fees в BNB
            total_fee_value = token_data.get('total_fee') or token_data.get('totalFee')
            if total_fee_value is not None:
                try:
                    if isinstance(total_fee_value, (int, float)):
                        result["total_fees_bnb"] = float(total_fee_value)
                    elif isinstance(total_fee_value, str):
                        result["total_fees_bnb"] = float(total_fee_value)
                    logger.debug(f"Apify: found total_fee = {result['total_fees_bnb']} BNB")
                except (ValueError, TypeError) as e:
                    logger.debug(f"Apify: failed to parse total_fee: {e}")
            
            # Ищем bundler % в данных
            # В Apify данных bundler % может быть не указан напрямую
            # Проверяем разные возможные поля
            bundler_candidates = [
                'bundler', 'bundler_percentage', 'batch_percentage', 
                'bundler_rate', 'bundler_pct', 'maker_token_tags'
            ]
            
            for key in bundler_candidates:
                if key in token_data:
                    value = token_data[key]
                    # Если это список тегов, проверяем наличие "bundler"
                    if isinstance(value, list) and 'bundler' in [str(v).lower() for v in value]:
                        # Если есть тег bundler, это индикатор, но не процент
                        logger.debug(f"Apify: found bundler tag in {key}")
                        # Можно использовать как индикатор, но не как процент
                        continue
                    # Если это число или строка с числом
                    try:
                        if isinstance(value, (int, float)):
                            result["bundler_percentage"] = float(value)
                            logger.debug(f"Apify: found bundler_percentage = {result['bundler_percentage']}%")
                            break
                        elif isinstance(value, str):
                            # Пробуем извлечь число из строки
                            import re
                            match = re.search(r'(\d+\.?\d*)', value)
                            if match:
                                result["bundler_percentage"] = float(match.group(1))
                                logger.debug(f"Apify: found bundler_percentage = {result['bundler_percentage']}%")
                                break
                    except (ValueError, TypeError):
                        continue
            
            # Если не нашли bundler напрямую, проверяем вложенные объекты
            if 'dev' in token_data and isinstance(token_data['dev'], dict):
                dev_data = token_data['dev']
                # Может быть в dev секции
                for key in ['bundler', 'bundler_percentage', 'batch_percentage']:
                    if key in dev_data:
                        try:
                            value = dev_data[key]
                            if isinstance(value, (int, float)):
                                result["bundler_percentage"] = float(value)
                                logger.debug(f"Apify: found bundler_percentage in dev.{key} = {result['bundler_percentage']}%")
                                break
                            elif isinstance(value, str):
                                import re
                                match = re.search(r'(\d+\.?\d*)', value)
                                if match:
                                    result["bundler_percentage"] = float(match.group(1))
                                    logger.debug(f"Apify: found bundler_percentage in dev.{key} = {result['bundler_percentage']}%")
                                    break
                        except (ValueError, TypeError):
                            continue
            
            # Извлекаем creator_address из dev секции (для проверки забаненных адресов)
            if 'dev' in token_data and isinstance(token_data['dev'], dict):
                dev_data = token_data['dev']
                if 'creator_address' in dev_data:
                    creator_addr = dev_data['creator_address']
                    if creator_addr and isinstance(creator_addr, str) and creator_addr.lower() != '0x0000000000000000000000000000000000000000':
                        result["creator_address"] = creator_addr.lower()
                        logger.debug(f"Apify: found creator_address = {result['creator_address']}")
                
                # Извлекаем top_10_holder_rate (концентрация у топ-10 holders)
                if 'top_10_holder_rate' in dev_data:
                    try:
                        top10_rate = dev_data['top_10_holder_rate']
                        if isinstance(top10_rate, (int, float)):
                            result["top_10_holder_rate"] = float(top10_rate) * 100  # Конвертируем в проценты (если это доля 0-1)
                        elif isinstance(top10_rate, str):
                            top10_value = float(top10_rate)
                            # Если значение < 1, значит это доля (0.1524 = 15.24%), иначе уже проценты
                            if top10_value < 1:
                                result["top_10_holder_rate"] = top10_value * 100
                            else:
                                result["top_10_holder_rate"] = top10_value
                        logger.debug(f"Apify: found top_10_holder_rate = {result['top_10_holder_rate']}%")
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Apify: failed to parse top_10_holder_rate: {e}")
                
                # Извлекаем creator_open_count (количество токенов, созданных этим адресом)
                if 'creator_open_count' in dev_data:
                    try:
                        creator_count = dev_data['creator_open_count']
                        if isinstance(creator_count, (int, float)):
                            result["creator_open_count"] = int(creator_count)
                        elif isinstance(creator_count, str):
                            result["creator_open_count"] = int(float(creator_count))
                        logger.debug(f"Apify: found creator_open_count = {result['creator_open_count']}")
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Apify: failed to parse creator_open_count: {e}")
            
            # Извлекаем buy/sell volume для вычисления buy/sell ratio
            if 'price' in token_data and isinstance(token_data['price'], dict):
                price_data = token_data['price']
                buy_volume_24h = None
                sell_volume_24h = None
                
                # Buy volume 24h
                if 'buy_volume_24h' in price_data:
                    try:
                        buy_vol = price_data['buy_volume_24h']
                        if isinstance(buy_vol, (int, float)):
                            buy_volume_24h = float(buy_vol)
                        elif isinstance(buy_vol, str):
                            buy_volume_24h = float(buy_vol)
                    except (ValueError, TypeError):
                        pass
                
                # Sell volume 24h
                if 'sell_volume_24h' in price_data:
                    try:
                        sell_vol = price_data['sell_volume_24h']
                        if isinstance(sell_vol, (int, float)):
                            sell_volume_24h = float(sell_vol)
                        elif isinstance(sell_vol, str):
                            sell_volume_24h = float(sell_vol)
                    except (ValueError, TypeError):
                        pass
                
                # Вычисляем buy/sell ratio
                if buy_volume_24h is not None and sell_volume_24h is not None and sell_volume_24h > 0:
                    buy_sell_ratio = buy_volume_24h / sell_volume_24h
                    result["buy_sell_ratio"] = buy_sell_ratio
                    logger.debug(f"Apify: calculated buy_sell_ratio = {buy_sell_ratio:.2f}")
            
            if result:
                logger.info(f"✅ Apify GMGN data for {token_address[:8]}...: {result}")
            else:
                logger.warning(f"⚠️ Apify returned empty result for {token_address[:8]}...")
            
            return result
            
    except asyncio.TimeoutError:
        logger.debug(f"Apify timeout for {token_address[:8]}...")
        return result
    except Exception as e:
        logger.debug(f"Apify GMGN fetch error: {e}")
        return result

# =========================
# Перевод названий токенов
# =========================

def translate_token_name(symbol: str) -> str:
    """Семантический перевод названий на английский с fallback на пиньин.
    1) Пытаемся найти точный перевод в словаре/овверрайдах.
    2) Если нет — оставляем транслитерацию (пиньин/кана -> латиница).
    """
    # Базовый словарь семантических переводов (идиомы/частые названия)
    translations = {
        # Китайские токены
        "米菲": "Miffy",
        "算命": "Fortune Telling",
        "老干妈": "Laoganma",
        "相信相信的力量": "Believe in the Power of Belief",
        "做市商人生": "Market Maker Life",
        "知妤": "Zhi Yu",
        "放屁幣": "Fart Coin",
        "相信易和": "Believe Easy Harmony",
        "okcoin": "OK Coin",
        "DONTKNOW": "Don't Know",
        "LLAMA": "Llama",
        "ai4cz": "AI4CZ",
        
        # Китайские идиомы и частые названия (семантический перевод)
        "花开富贵": "Flowers Bloom and Wealth",
        "完美融合": "Perfect fusion",

        # Японские токены
        "ねこ": "Cat",
        "いぬ": "Dog",
        "さくら": "Sakura",
        "たんぽぽ": "Dandelion",
        "つばめ": "Swallow",
        "ひまわり": "Sunflower",
        "もみじ": "Maple",
        "ゆき": "Snow",
        "はな": "Flower",
        "つき": "Moon",
        
        # Корейские токены
        "고양이": "Cat",
        "강아지": "Puppy",
        "꽃": "Flower",
        "별": "Star",
        "달": "Moon",
        "해": "Sun",
        "물": "Water",
        "불": "Fire",
        "바람": "Wind",
        "땅": "Earth",
    }
    # Поддержка пользовательских овверрайдов через ENV (JSON: {"原":"Translated"})
    try:
        overrides = os.getenv("TRANSLATION_OVERRIDES", "").strip()
        if overrides:
            import json as _json
            user_map = _json.loads(overrides)
            if isinstance(user_map, dict):
                translations.update({str(k): str(v) for k, v in user_map.items()})
    except Exception:
        pass

    # Если строка начинается с $, уберем для проверки
    plain = symbol[1:] if symbol.startswith("$") else symbol

    # Применяем перевод/пиньин ТОЛЬКО для CJK-имен
    has_cjk = any('\u4e00' <= ch <= '\u9fff' or  # Chinese
                  '\u3040' <= ch <= '\u309f' or  # Hiragana
                  '\u30a0' <= ch <= '\u30ff' or  # Katakana
                  '\uac00' <= ch <= '\ud7af'     # Hangul
                  for ch in plain)

    if not has_cjk:
        return symbol  # английские/латиница — без перевода

    # 1) Точный перевод по словарю (семантический)
    if plain in translations:
        return translations[plain]

    # 2) Fallback: транслитерация в пиньин (если библиотека доступна)
    try:
        from pypinyin import lazy_pinyin
        pinyin_parts = lazy_pinyin(plain)
        if pinyin_parts:
            return " ".join(p.capitalize() for p in pinyin_parts)
    except Exception:
        pass

    return symbol

# =========================
# Форматирование сообщений
# =========================

def calculate_total_fees(token: Dict) -> Optional[float]:
    """
    Вычисляет total fees в BNB на основе РЕАЛЬНОГО объема торговли за 24 часа
    Использует ТОЛЬКО volume_24h - не экстраполирует из volume_5m или volume_1h
    """
    try:
        # Используем ТОЛЬКО реальный volume_24h - не экстраполируем!
        volume_24h = token.get('volume_24h', 0)
        
        # Если volume_24h нет или равен 0, не показываем fees
        if not volume_24h or volume_24h == 0:
            return None
        
        volume_for_fees = volume_24h
        
        # Получаем fee percentage
        # Сначала пробуем из GeckoTerminal pool_fee_percentage
        # GeckoTerminal возвращает fee в процентах (например, 0.25 для 0.25%, 0.05 для 0.05%)
        pool_fee_percentage = token.get('pool_fee_percentage')
        
        # Конвертируем в float если это строка
        if pool_fee_percentage is not None:
            try:
                if isinstance(pool_fee_percentage, str):
                    fee_percentage = float(pool_fee_percentage)
                else:
                    fee_percentage = float(pool_fee_percentage)
            except (ValueError, TypeError):
                fee_percentage = None
        else:
            fee_percentage = None
        
        # Если fee_percentage не получен или равен 0, используем стандартную комиссию PancakeSwap
        if fee_percentage is None or fee_percentage == 0:
            # Стандартная комиссия PancakeSwap V2: 0.25% для обычных пулов
            fee_percentage = 0.25
        
        # Вычисляем total fees в USD
        # fee_percentage уже в процентах (0.25 = 0.25%), поэтому делим на 100
        total_fees_usd = volume_for_fees * (fee_percentage / 100)
        
        # Конвертируем в BNB
        # Получаем реальную цену BNB (примерно $600-700, не $850)
        # Используем более актуальную цену BNB
        bnb_price_usd = token.get('bnb_price_usd', 650)  # Более актуальная цена BNB
        
        # Если цена BNB не указана, используем стандартное значение
        if not bnb_price_usd or bnb_price_usd == 0:
            bnb_price_usd = 650  # Более актуальная цена BNB (январь 2026)
        
        total_fees_bnb = total_fees_usd / bnb_price_usd if bnb_price_usd > 0 else None
        
        return total_fees_bnb
    
    except Exception as e:
        logger.debug(f"Error calculating total fees: {e}")
        return None

def format_alert(token: Dict, checks_count: int, is_established: bool = False) -> str:
    """Форматирует alert сообщение"""
    # Format volume
    volume_str = f"{token['volume_5m'] / 1_000_000:.1f}M" if token['volume_5m'] >= 1_000_000 else f"{token['volume_5m'] / 1_000:.0f}K"
    
    # Format FDV/Market Cap
    fdv_value = token.get('fdv') or token.get('market_cap')
    fdv_str = f"${float(fdv_value):,.0f}" if fdv_value else "N/A"
    
    # Holders count (if available)
    holders_count = token.get('holders_count')
    
    # Token age
    age_hours = token.get('age_hours', 0)
    age_str = f"{age_hours:.1f}h" if age_hours < 24 else f"{age_hours/24:.1f}d"
    
    # Переводим название токена
    original_symbol = token['token_symbol']
    translated_name = translate_token_name(original_symbol)
    
    # Формируем название с переводом (если есть)
    if translated_name != original_symbol:
        display_name = f"${original_symbol} ({translated_name})"
    else:
        display_name = f"${original_symbol}"
    
    # Different headers for new vs established tokens
    if is_established:
        text = "🔴 <b>BSC VOLUME SPIKE!</b> 🔴\n\n"
        text += f"<b>{display_name}</b> (Age: {age_str})\n\n"
        text += f"<b>💥 {volume_str} volume spike in last 5 minutes!</b>\n"
    else:
        text = "🟡 <b>BSC Volume Alert</b> 🟡\n\n"
        text += f"<b>{display_name}</b>\n\n"
        text += f"<b>🔥 {volume_str} volume in last 5 minutes</b>\n"
    
    text += f"<b>📈 MC (FDV):</b> {fdv_str}\n"
    
    # Ликвидность
    liquidity_usd = token.get('liquidity_usd')
    if liquidity_usd is not None and liquidity_usd > 0:
        if liquidity_usd >= 1_000_000:
            liquidity_str = f"${liquidity_usd / 1_000_000:.1f}M"
        elif liquidity_usd >= 1_000:
            liquidity_str = f"${liquidity_usd / 1_000:.0f}K"
        else:
            liquidity_str = f"${liquidity_usd:,.0f}"
        text += f"<b>💧 Liquidity:</b> {liquidity_str}\n"
    
    # Holders and distribution (if available)
    if holders_count:
        text += f"<b>👤 Holders:</b> {holders_count:,}"
        top10_percent = token.get('top10_holders_percent')
        if top10_percent is not None and top10_percent > 0:
            text += f" | 🥷 <b>Top 10:</b> {top10_percent:.1f}%"
        text += "\n"
    
    # DEXT Score
    dext_score = token.get('dext_score')
    if dext_score is not None and dext_score > 0:
        text += f"<b>⭐ DEXT Score:</b> {dext_score:.1f}\n"
    
    # Age
    age_hours = token.get('age_hours', 0)
    if age_hours < 1:
        age_str = f"{int(age_hours * 60)}m"
    elif age_hours < 24:
        hours = int(age_hours)
        minutes = int((age_hours - hours) * 60)
        if minutes > 0:
            age_str = f"{hours}h {minutes}m"
        else:
            age_str = f"{hours}h"
    else:
        days = int(age_hours // 24)
        remaining_hours = int(age_hours % 24)
        if remaining_hours > 0:
            age_str = f"{days}d {remaining_hours}h"
        else:
            age_str = f"{days}d"
    text += f"<b>⌛️ Age:</b> {age_str}\n\n"
    
    # Total Fees - используем ТОЛЬКО из GMGN (не calculate_total_fees)
    total_fees_bnb = token.get('total_fees_bnb')  # Только из GMGN
    if total_fees_bnb is not None and total_fees_bnb > 0:
        if total_fees_bnb >= 1:
            fees_str = f"{total_fees_bnb:.2f}BNB"
        elif total_fees_bnb >= 0.01:
            fees_str = f"{total_fees_bnb:.3f}BNB"
        else:
            fees_str = f"{total_fees_bnb:.4f}BNB"
        text += f"<b>💼 Total fees:</b> {fees_str}\n"
    
    # Bundler % (из GMGN)
    bundler_percentage = token.get('bundler_percentage')
    if bundler_percentage is not None:
        text += f"<b>📦 Bundler:</b> {bundler_percentage:.1f}%\n"
    
    # Top 10% Holders (из GMGN)
    top_10_holder_rate = token.get('top_10_holder_rate')
    if top_10_holder_rate is not None:
        text += f"<b>📊 Top 10% Holders:</b> {top_10_holder_rate:.1f}%\n"
    
    # Dev Previous Tokens (из GMGN)
    creator_open_count = token.get('creator_open_count')
    if creator_open_count is not None:
        text += f"<b>👨‍💻 Dev Previous Tokens:</b> {creator_open_count}\n"
    
    # Buy/Sell Ratio (из GMGN)
    buy_sell_ratio = token.get('buy_sell_ratio')
    if buy_sell_ratio is not None:
        text += f"<b>📈 Buy/Sell Ratio:</b> {buy_sell_ratio:.2f}\n"
    
    # Source - показываем только настоящие launchpad'ы
    source = token.get('source', 'unknown')
    if source == 'fourmeme':
        text += f"<b>🚀 Launchpad:</b> Four.Meme\n"
    
    # Contract address - monospace
    text += f"\n<b>🔗 CA:</b> <code>{token['token_address']}</code>\n\n"
    
    # Links
    token_addr = token['token_address']
    
    # GMGN link
    gmgn_url = f"https://gmgn.ai/bsc/token/{token_addr}?tag=whale&min=5&isInputValue=true"
    
    # Pancake Pools link (search by token address)
    pancake_pools_url = (
        "https://pancakeswap.finance/liquidity/pools?chain=bsc&network=56&network=1&network=8453&network=204&network=324&network=59144&network=42161&network=8000001001&search="
        f"{token_addr}"
    )
    
    # Krystal link
    krystal_url = f"https://defi.krystal.app/token?chainId=56&address={token_addr}"
    
    # Based bot link - формат: r_darkzodchi_b_TOKEN_ADDRESS (используется в inline кнопке, не в нижнем списке)
    based_url = f"https://t.me/based_eth_bot?start=r_darkzodchi_b_{token_addr}"
    
    # X (Twitter) link
    x_url = f"https://x.com/search?q={token_addr}&src=typed_query"
    
    text += f"<a href='{gmgn_url}'>GMGN</a> | "
    text += f"<a href='{pancake_pools_url}'>Pancake Pools</a> | "
    text += f"<a href='{krystal_url}'>Krystal</a> | "
    text += f"<a href='{x_url}'>X</a>\n\n"
    
    # Социальные ссылки (если доступны)
    social_links = []
    if token.get('website'):
        social_links.append(f"<a href='{token['website']}'>🌐 Website</a>")
    if token.get('telegram'):
        social_links.append(f"<a href='{token['telegram']}'>📱 Telegram</a>")
    if token.get('twitter'):
        social_links.append(f"<a href='{token['twitter']}'>🐦 Twitter</a>")
    if token.get('discord'):
        social_links.append(f"<a href='{token['discord']}'>💬 Discord</a>")
    
    if social_links:
        text += "<b>🔗 Social:</b> " + " | ".join(social_links)
    
    return text

def format_more_volume_alert(token: Dict, previous_volume: float, current_volume: float, growth_multiplier: float) -> str:
    """Форматирует alert сообщение о всплеске объема"""
    # Format volumes
    prev_volume_str = f"{previous_volume / 1_000_000:.1f}M" if previous_volume >= 1_000_000 else f"{previous_volume / 1_000:.0f}K"
    curr_volume_str = f"{current_volume / 1_000_000:.1f}M" if current_volume >= 1_000_000 else f"{current_volume / 1_000:.0f}K"
    
    # Format FDV/Market Cap
    fdv_value = token.get('fdv') or token.get('market_cap')
    fdv_str = f"${float(fdv_value):,.0f}" if fdv_value else "N/A"
    
    # Holders count (if available)
    holders_count = token.get('holders_count')
    
    # Token age
    age_hours = token.get('age_hours', 0)
    if age_hours < 1:
        age_str = f"{int(age_hours * 60)}m"
    elif age_hours < 24:
        hours = int(age_hours)
        minutes = int((age_hours - hours) * 60)
        if minutes > 0:
            age_str = f"{hours}h {minutes}m"
        else:
            age_str = f"{hours}h"
    else:
        days = int(age_hours // 24)
        remaining_hours = int(age_hours % 24)
        if remaining_hours > 0:
            age_str = f"{days}d {remaining_hours}h"
        else:
            age_str = f"{days}d"
    
    # Переводим название токена
    original_symbol = token['token_symbol']
    translated_name = translate_token_name(original_symbol)
    
    # Формируем название с переводом (если есть)
    if translated_name != original_symbol:
        display_name = f"${original_symbol} ({translated_name})"
    else:
        display_name = f"${original_symbol}"
    
    text = "🟡 <b>More BSC Volume Alert</b> 🟡\n\n"
    text += f"<b>{display_name}</b>\n\n"
    text += f"<b>🔥 {curr_volume_str} volume in last 5 minutes</b>\n"
    text += f"<b>📈 MC (FDV):</b> {fdv_str}\n"
    
    # Ликвидность
    liquidity_usd = token.get('liquidity_usd')
    if liquidity_usd is not None and liquidity_usd > 0:
        if liquidity_usd >= 1_000_000:
            liquidity_str = f"${liquidity_usd / 1_000_000:.1f}M"
        elif liquidity_usd >= 1_000:
            liquidity_str = f"${liquidity_usd / 1_000:.0f}K"
        else:
            liquidity_str = f"${liquidity_usd:,.0f}"
        text += f"<b>💧 Liquidity:</b> {liquidity_str}\n"
    
    # Holders and distribution (if available)
    if holders_count:
        text += f"<b>👤 Holders:</b> {holders_count:,}"
        top10_percent = token.get('top10_holders_percent')
        if top10_percent is not None and top10_percent > 0:
            text += f" | 🥷 <b>Top 10:</b> {top10_percent:.1f}%"
        text += "\n"
    
    # DEXT Score
    dext_score = token.get('dext_score')
    if dext_score is not None and dext_score > 0:
        text += f"<b>⭐ DEXT Score:</b> {dext_score:.1f}\n"
    
    text += f"<b>⌛️ Age:</b> {age_str}\n\n"
    
    # Total Fees - используем ТОЛЬКО из GMGN (не calculate_total_fees)
    total_fees_bnb = token.get('total_fees_bnb')  # Только из GMGN
    if total_fees_bnb is not None and total_fees_bnb > 0:
        if total_fees_bnb >= 1:
            fees_str = f"{total_fees_bnb:.2f}BNB"
        elif total_fees_bnb >= 0.01:
            fees_str = f"{total_fees_bnb:.3f}BNB"
        else:
            fees_str = f"{total_fees_bnb:.4f}BNB"
        text += f"<b>💼 Total fees:</b> {fees_str}\n"
    
    # Bundler % (из GMGN)
    bundler_percentage = token.get('bundler_percentage')
    if bundler_percentage is not None:
        text += f"<b>📦 Bundler:</b> {bundler_percentage:.1f}%\n"
    
    # Top 10% Holders (из GMGN)
    top_10_holder_rate = token.get('top_10_holder_rate')
    if top_10_holder_rate is not None:
        text += f"<b>📊 Top 10% Holders:</b> {top_10_holder_rate:.1f}%\n"
    
    # Dev Previous Tokens (из GMGN)
    creator_open_count = token.get('creator_open_count')
    if creator_open_count is not None:
        text += f"<b>👨‍💻 Dev Previous Tokens:</b> {creator_open_count}\n"
    
    # Buy/Sell Ratio (из GMGN)
    buy_sell_ratio = token.get('buy_sell_ratio')
    if buy_sell_ratio is not None:
        text += f"<b>📈 Buy/Sell Ratio:</b> {buy_sell_ratio:.2f}\n"
    
    # Source - показываем только настоящие launchpad'ы
    source = token.get('source', 'unknown')
    if source == 'fourmeme':
        text += f"<b>🚀 Launchpad:</b> Four.Meme\n"
    
    # Contract address - monospace
    text += f"\n<b>🔗 CA:</b> <code>{token['token_address']}</code>\n\n"
    
    # Links
    token_addr = token['token_address']
    
    # GMGN link
    gmgn_url = f"https://gmgn.ai/bsc/token/{token_addr}?tag=whale&min=5&isInputValue=true"
    
    # Pancake Pools link (search by token address)
    pancake_pools_url = (
        "https://pancakeswap.finance/liquidity/pools?chain=bsc&network=56&network=1&network=8453&network=204&network=324&network=59144&network=42161&network=8000001001&search="
        f"{token_addr}"
    )
    
    # Krystal link
    krystal_url = f"https://defi.krystal.app/token?chainId=56&address={token_addr}"
    
    # X (Twitter) link
    x_url = f"https://x.com/search?q={token_addr}&src=typed_query"
    
    text += f"<a href='{gmgn_url}'>GMGN</a> | "
    text += f"<a href='{pancake_pools_url}'>Pancake Pools</a> | "
    text += f"<a href='{krystal_url}'>Krystal</a> | "
    text += f"<a href='{x_url}'>X</a>\n\n"
    
    # Социальные ссылки (если доступны)
    social_links = []
    if token.get('website'):
        social_links.append(f"<a href='{token['website']}'>🌐 Website</a>")
    if token.get('telegram'):
        social_links.append(f"<a href='{token['telegram']}'>📱 Telegram</a>")
    if token.get('twitter'):
        social_links.append(f"<a href='{token['twitter']}'>🐦 Twitter</a>")
    if token.get('discord'):
        social_links.append(f"<a href='{token['discord']}'>💬 Discord</a>")
    
    if social_links:
        text += "<b>🔗 Social:</b> " + " | ".join(social_links)
    
    return text

# =========================
# Основная логика
# =========================

async def scan_once(session: aiohttp.ClientSession, tracker: TokenTracker):
    """Один цикл сканирования"""
    try:
        # Параллельно запрашиваем данные из всех источников
        # GeckoTerminal - 10 страниц (200 пулов) с задержками для избежания rate limits
        dex_task = fetch_dexscreener_new_pairs(session)
        usd1_dex_task = fetch_dexscreener_usd1_pairs(session)  # DexScreener USD1 (может не иметь volume)
        usd1_gecko_task = fetch_geckoterminal_usd1_pools(session)  # GeckoTerminal USD1 (имеет volume!)
        fourmeme_task = fetch_fourmeme_tokens(session)
        trending_tasks = [
            fetch_geckoterminal_trending_pools(session, page=i)
            for i in range(1, 4)  # 3 страницы трендов достаточно
        ]
        gecko_tasks = [
            fetch_geckoterminal_new_pools(session, page=i)
            for i in range(1, 13)  # 12 страниц = 240 пулов (было 10 страниц = 200 пулов)
        ]
        
        results = await asyncio.gather(dex_task, usd1_dex_task, usd1_gecko_task, fourmeme_task, *trending_tasks, *gecko_tasks, return_exceptions=True)
        
        dex_pairs = results[0] if not isinstance(results[0], Exception) else []
        usd1_dex_pairs = results[1] if not isinstance(results[1], Exception) else []
        usd1_gecko_pools = results[2] if not isinstance(results[2], Exception) else []
        fourmeme_tokens = results[3] if not isinstance(results[3], Exception) else []
        trending_pools = []
        gecko_pools = []
        # trending pages occupy indexes 4..6 (после usd1_gecko_task)
        for i in range(4, 7):
            if i < len(results) and not isinstance(results[i], Exception):
                trending_pools.extend(results[i])
        # new pools start after trending pages
        for i in range(7, len(results)):
            if not isinstance(results[i], Exception):
                gecko_pools.extend(results[i])
        
        # Парсим данные
        tokens: Dict[str, Dict] = {}  # token_address -> data
        
        # DexScreener
        for pair in dex_pairs:
            parsed = parse_dexscreener_pair(pair)
            if parsed:
                # РАННЯЯ ПРОВЕРКА: Блокируем забаненных разработчиков сразу после парсинга
                pair_address = parsed.get('pair_address', '')
                is_banned = await check_banned_developer(session, parsed["token_address"], pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {parsed['token_symbol']} ({parsed['token_address'][:8]}...): banned developer - early check")
                    continue
                
                # Проверяем две категории:
                # 1. Новые токены (< 2h) с объемом >= $250K
                # 2. Устоявшиеся токены (> 2h) с объемом >= $3M
                # 3. Исключаем токены с объемом > $40M (слишком популярные)
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем токены с высоким объемом для отладки
                if parsed["volume_5m"] >= 200000:  # Логируем токены с объемом > $200K
                    logger.info(f"🔍 DexScreener token: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")
                
                if (is_new_token or is_established_spike) and is_not_too_popular:
                    addr = parsed["token_address"]
                    # Помечаем тип токена для разной логики алертов
                    parsed["is_new_token"] = is_new_token
                    parsed["source"] = "dexscreener"  # Добавляем источник
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
        
        # GeckoTerminal USD1 пулы (приоритет - есть данные по объему!)
        logger.info(f"Processing {len(usd1_gecko_pools)} GeckoTerminal USD1 pools...")
        parsed_count = 0
        for pool in usd1_gecko_pools:
            parsed = parse_geckoterminal_pool(pool)
            if parsed:
                parsed_count += 1
                # РАННЯЯ ПРОВЕРКА: Блокируем забаненных разработчиков сразу после парсинга
                pair_address = parsed.get('pair_address', '')
                is_banned = await check_banned_developer(session, parsed["token_address"], pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {parsed['token_symbol']} ({parsed['token_address'][:8]}...): banned developer - early check")
                    continue
                
                # Применяем те же фильтры для USD1 пар
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем ВСЕ USD1 пулы для отладки
                logger.info(f"🔍 GeckoTerminal USD1 pool: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")
                
                if (is_new_token or is_established_spike) and is_not_too_popular:
                    addr = parsed["token_address"]
                    # Помечаем тип токена для разной логики алертов
                    parsed["is_new_token"] = is_new_token
                    parsed["source"] = "geckoterminal_usd1"  # Добавляем источник
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
            else:
                # Логируем, если парсинг не удался
                pool_name = pool.get("attributes", {}).get("name", "Unknown")
                volume_5m_raw = pool.get("attributes", {}).get("volume_usd", {}).get("m5", 0)
                logger.debug(f"⚠️ Failed to parse GeckoTerminal USD1 pool: {pool_name}, volume_5m: {volume_5m_raw}")
        
        logger.info(f"Parsed {parsed_count}/{len(usd1_gecko_pools)} GeckoTerminal USD1 pools")
        
        # DexScreener USD1 пары (fallback - может не иметь volume данных)
        logger.info(f"Processing {len(usd1_dex_pairs)} DexScreener USD1 pairs...")
        for pair in usd1_dex_pairs:
            parsed = parse_dexscreener_pair(pair)
            if parsed:
                # РАННЯЯ ПРОВЕРКА: Блокируем забаненных разработчиков сразу после парсинга
                pair_address = parsed.get('pair_address', '')
                is_banned = await check_banned_developer(session, parsed["token_address"], pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {parsed['token_symbol']} ({parsed['token_address'][:8]}...): banned developer - early check")
                    continue
                
                # Применяем те же фильтры для USD1 пар
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем USD1 пары с объемом для отладки
                if parsed["volume_5m"] >= 200000:  # Логируем токены с объемом > $200K
                    logger.info(f"🔍 DexScreener USD1 pair: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")
                
                if (is_new_token or is_established_spike) and is_not_too_popular:
                    addr = parsed["token_address"]
                    # Помечаем тип токена для разной логики алертов
                    parsed["is_new_token"] = is_new_token
                    parsed["source"] = "dexscreener_usd1"  # Добавляем источник
                    # Используем только если нет данных из GeckoTerminal или объем больше
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
        
        # Four.Meme
        for trade in fourmeme_tokens:
            parsed = parse_fourmeme_token(trade)
            if parsed:
                # РАННЯЯ ПРОВЕРКА: Блокируем забаненных разработчиков сразу после парсинга
                pair_address = parsed.get('pair_address', '')
                is_banned = await check_banned_developer(session, parsed["token_address"], pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {parsed['token_symbol']} ({parsed['token_address'][:8]}...): banned developer - early check")
                    continue
                
                # Проверяем новые токены с объемом >= $300K
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем токены с высоким объемом для отладки
                if parsed["volume_5m"] >= 200000:  # Логируем токены с объемом > $200K
                    logger.info(f"🔍 Four.Meme token: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, NotPopular: {is_not_too_popular}")
                
                if is_new_token and is_not_too_popular:
                    addr = parsed["token_address"]
                    # Помечаем тип токена для разной логики алертов
                    parsed["is_new_token"] = is_new_token
                    parsed["source"] = "fourmeme"  # Добавляем источник
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
        
        # GeckoTerminal
        for pool in gecko_pools:
            parsed = parse_geckoterminal_pool(pool)
            if parsed:
                # РАННЯЯ ПРОВЕРКА: Блокируем забаненных разработчиков сразу после парсинга
                pair_address = parsed.get('pair_address', '')
                is_banned = await check_banned_developer(session, parsed["token_address"], pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {parsed['token_symbol']} ({parsed['token_address'][:8]}...): banned developer - early check")
                    continue
                
                # Проверяем две категории:
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем токены с высоким объемом для отладки
                if parsed["volume_5m"] >= 200000:  # Логируем токены с объемом > $200K
                    logger.info(f"🔍 GeckoTerminal token: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")
                
                if (is_new_token or is_established_spike) and is_not_too_popular:
                    addr = parsed["token_address"]
                    parsed["is_new_token"] = is_new_token
                    parsed["source"] = "geckoterminal"  # Добавляем источник
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed

        # GeckoTerminal Trending (established spikes)
        for pool in trending_pools:
            parsed = parse_geckoterminal_pool(pool)
            if parsed:
                # РАННЯЯ ПРОВЕРКА: Блокируем забаненных разработчиков сразу после парсинга
                pair_address = parsed.get('pair_address', '')
                is_banned = await check_banned_developer(session, parsed["token_address"], pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {parsed['token_symbol']} ({parsed['token_address'][:8]}...): banned developer - early check")
                    continue
                
                # Ищем только established spikes
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD

                if parsed["volume_5m"] >= 200000:
                    logger.info(f"🔍 GeckoTerminal trending: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")

                if is_established_spike and is_not_too_popular:
                    addr = parsed["token_address"]
                    parsed["is_new_token"] = False
                    parsed["source"] = "geckoterminal_trending"
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
        
        logger.info(f"Found {len(tokens)} tokens matching criteria (new: vol >= ${MIN_5M_VOLUME_USD_NEW:,.0f} mcap >= ${MIN_MARKET_CAP_USD:,.0f} age < {MAX_TOKEN_AGE_HOURS}h | established: vol >= ${MIN_5M_VOLUME_USD_ESTABLISHED:,.0f} age > {MAX_TOKEN_AGE_HOURS}h | max: vol <= ${MAX_5M_VOLUME_USD:,.0f})")
        
        # Логируем топ-5 токенов по объему для отладки
        if tokens:
            sorted_tokens = sorted(tokens.values(), key=lambda t: t["volume_5m"], reverse=True)[:5]
            logger.info("Top 5 tokens by 5m volume:")
            for t in sorted_tokens:
                source = t.get("source", "unknown")
                logger.info(f"  {t['token_symbol']}: ${t['volume_5m']:,.0f} (age: {t['age_hours']:.1f}h, source: {source})")
        
        # ОПТИМИЗАЦИЯ: Параллельная предзагрузка GMGN данных для всех токенов
        # Это ускоряет обработку в 3-4 раза без дополнительных затрат
        if tokens:
            logger.info(f"🔄 Starting parallel GMGN data fetch for {len(tokens)} tokens...")
            gmgn_tasks = []
            token_addresses_list = list(tokens.keys())
            
            for token_address in token_addresses_list:
                gmgn_tasks.append(fetch_gmgn_token_data(session, token_address))
            
            # Запускаем все GMGN проверки параллельно
            gmgn_results = await asyncio.gather(*gmgn_tasks, return_exceptions=True)
            
            # Применяем результаты к соответствующим токенам
            for i, token_address in enumerate(token_addresses_list):
                if i < len(gmgn_results) and not isinstance(gmgn_results[i], Exception):
                    gmgn_data = gmgn_results[i]
                    if gmgn_data:
                        tokens[token_address].update(gmgn_data)
                        logger.info(f"✅ GMGN data fetched for {tokens[token_address]['token_symbol']}: bundler={gmgn_data.get('bundler_percentage')}, total_fees={gmgn_data.get('total_fees_bnb')}, top10={gmgn_data.get('top_10_holder_rate')}, creator_count={gmgn_data.get('creator_open_count')}")
                    else:
                        logger.warning(f"⚠️ GMGN data not fetched for {tokens[token_address]['token_symbol']} - will be blocked if EXCLUDE_LOW_TOTAL_FEES is enabled")
                elif isinstance(gmgn_results[i], Exception):
                    logger.warning(f"Failed to fetch GMGN data for {token_address}: {gmgn_results[i]}")
            
            logger.info(f"✅ Parallel GMGN fetch completed for {len(tokens)} tokens")
        
        # Обновляем tracker
        for token_address, token_data in tokens.items():
            is_new_token = token_data.get("is_new_token", True)
            
            # Для устоявшихся токенов ($3M+) - отправляем алерт сразу, без проверки стабильности
            if not is_new_token:
                # Обновляем историю объемов для отслеживания всплесков
                tracker.update_volume_history(token_address, token_data["volume_5m"])
                
                if tracker.recently_alerted(token_address, minutes=10):
                    logger.info(f"⏳ Skip duplicate alert (10m window) for {token_data['token_symbol']}")
                    continue
                if not tracker.is_alerted(token_address):
                    logger.info(f"🔥 INSTANT ALERT: {token_data['token_symbol']} (established token with ${token_data['volume_5m']:,.0f} volume spike!)")
                    
                    # Сразу помечаем как alerted, чтобы избежать дублирования
                    tracker.mark_alerted(token_address)
                    
                    # Получаем данные о holders и security из DexTools
                    try:
                        dextools_data = await fetch_dextools_token_data(session, token_address)
                        if dextools_data:
                            # Не перетираем ликвидность, если DexTools вернул 0/None
                            dx_liq = dextools_data.get('liquidity_usd')
                            if dx_liq is None or dx_liq == 0:
                                logger.info("🔄 Liquidity source: GeckoTerminal (DexTools returned empty liquidity)")
                                dextools_data.pop('liquidity_usd', None)
                            else:
                                logger.info(f"🔄 Liquidity source: DexTools (${dx_liq:,.0f})")
                            token_data.update(dextools_data)
                            logger.info(f"📊 DexTools data: holders={dextools_data.get('holders_count')}, honeypot={dextools_data.get('is_honeypot')}, tax={dextools_data.get('buy_tax')}/{dextools_data.get('sell_tax')}")
                        else:
                            logger.info(f"⚠️ No DexTools data returned for {token_address}")
                        # Rate limit: DexTools allows 1 request/second
                        await asyncio.sleep(1.1)
                    except Exception as e:
                        logger.info(f"❌ DexTools API error for {token_address}: {e}")
                        await asyncio.sleep(1.1)
                    
                    # GMGN данные уже получены параллельно выше, используем их из token_data
                    
                    # Проверяем адрес создателя токена (забаненные разработчики)
                    # Сначала проверяем creator_address из GMGN данных (если есть)
                    creator_address = token_data.get('creator_address')
                    if creator_address:
                        creator_lower = creator_address.lower()
                        banned_addresses_lower = [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]
                        if creator_lower in banned_addresses_lower:
                            logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer address from GMGN data: {creator_address[:8]}...")
                            continue
                    
                    # Если creator_address не найден в GMGN, используем стандартную проверку через BSCScan
                    pair_address = token_data.get('pair_address', '')
                    is_banned = await check_banned_developer(session, token_address, pair_address)
                    if is_banned:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer address")
                        continue

                    # Проверка GMGN фильтров
                    if EXCLUDE_HIGH_BUNDLER:
                        bundler_percentage = token_data.get('bundler_percentage')
                        if bundler_percentage is not None and bundler_percentage > MAX_BUNDLER_PERCENTAGE:
                            logger.info(f"🚫 Skipping {token_data['token_symbol']}: high bundler percentage {bundler_percentage:.1f}% > {MAX_BUNDLER_PERCENTAGE:.1f}% (scam indicator)")
                            continue

                    if EXCLUDE_LOW_TOTAL_FEES:
                        # Используем ТОЛЬКО реальные данные из GMGN (без fallback)
                        total_fees_gmgn = token_data.get('total_fees_bnb')
                        if total_fees_gmgn is None:
                            logger.info(f"🚫 Skipping {token_data['token_symbol']}: GMGN total fees not available (required)")
                            continue
                        if total_fees_gmgn < MIN_TOTAL_FEES_GMGN_BNB:
                            logger.info(f"🚫 Skipping {token_data['token_symbol']}: low total fees {total_fees_gmgn:.4f}BNB < {MIN_TOTAL_FEES_GMGN_BNB}BNB (scam indicator)")
                            continue
                    
                    # Фильтрация по безопасности
                    # Проверяем honeypot
                    is_honeypot = token_data.get('is_honeypot')
                    if EXCLUDE_HONEYPOTS and is_honeypot is True:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                        continue
                    elif EXCLUDE_HONEYPOTS and is_honeypot is None:
                        # Не блокируем токены когда статус неизвестен - DexTools может быть временно недоступен
                        logger.info(f"ℹ️ {token_data['token_symbol']}: honeypot status unknown (DexTools unavailable) - allowing token")
                    
                    # Проверяем buy/sell tax
                    buy_tax = token_data.get('buy_tax')
                    sell_tax = token_data.get('sell_tax')
                    
                    # Проверяем налоги только если они известны
                    if buy_tax is not None and buy_tax > MAX_BUY_TAX:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: buy tax {buy_tax}% > {MAX_BUY_TAX}%")
                        continue
                    if sell_tax is not None and sell_tax > MAX_SELL_TAX:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: sell tax {sell_tax}% > {MAX_SELL_TAX}%")
                        continue
                    
                    # Логируем если налоги неизвестны, но не блокируем
                    if buy_tax is None or sell_tax is None:
                        logger.info(f"ℹ️ {token_data['token_symbol']}: tax info unknown (DexTools unavailable) - allowing token")
                    
                    # Проверяем концентрацию у топ-10 holders
                    top10_holders_percent = token_data.get('top10_holders_percent')
                    if top10_holders_percent is not None and top10_holders_percent > MAX_TOP10_HOLDERS_PERCENT:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: top 10 holders concentration {top10_holders_percent:.1f}% > {MAX_TOP10_HOLDERS_PERCENT:.1f}%")
                        continue
                    elif top10_holders_percent is None:
                        logger.info(f"ℹ️ {token_data['token_symbol']}: top 10 holders data unavailable - allowing token")
                    
                    # Проверяем renounced контракт
                    is_renounced = token_data.get('is_contract_renounced', False)
                    if REQUIRE_RENOUNCED_CONTRACT and not is_renounced:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: contract not renounced")
                        continue
                    
                    # Проверяем mintable токены
                    is_mintable = token_data.get('is_mintable', False)
                    if EXCLUDE_MINTABLE and is_mintable:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: token is mintable")
                        continue
                    
                    # Проверяем proxy контракты
                    is_proxy = token_data.get('is_proxy', False)
                    if EXCLUDE_PROXY and is_proxy:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: contract is proxy")
                        continue
                    
                    # Проверяем потенциально scam токены
                    is_potentially_scam = token_data.get('is_potentially_scam', False)
                    if EXCLUDE_POTENTIALLY_SCAM and is_potentially_scam:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: potentially scam token")
                        continue
                    
                    # Проверяем blacklisted токены
                    is_blacklisted = token_data.get('is_blacklisted', False)
                    if EXCLUDE_BLACKLISTED and is_blacklisted:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: token is blacklisted")
                        continue
                    
                    # Проверяем минимальное количество holders (пропускаем при высоком объеме или если данные недоступны)
                    holders = token_data.get('holders_count', 0)
                    holders_unavailable = token_data.get('holders_unavailable', False)
                    volume_5m = token_data.get("volume_5m", 0)
                    
                    logger.info(f"🔍 {token_data['token_symbol']}: holders={holders}, unavailable={holders_unavailable}, volume_5m=${volume_5m:,.0f}, skip_threshold=${MIN_VOLUME_SKIP_HOLDERS:,.0f}")
                    
                    if volume_5m >= MIN_VOLUME_SKIP_HOLDERS:
                        logger.info(f"🚀 High volume token {token_data['token_symbol']}: ${volume_5m:,.0f} - skipping holders check")
                    elif holders_unavailable:
                        logger.info(f"ℹ️ {token_data['token_symbol']}: holders data unavailable (both APIs returned 0) - allowing token without holders info")
                    elif holders < MIN_HOLDERS:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: only {holders} holders (min {MIN_HOLDERS})")
                        continue
                    
                    # Проверяем минимальный market cap
                    market_cap = token_data.get('fdv') or token_data.get('market_cap') or 0
                    if market_cap < MIN_MARKET_CAP_USD:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: market cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
                        continue
                    
                    # Проверяем минимальную ликвидность
                    liquidity_usd = token_data.get('liquidity_usd', 0)
                    if liquidity_usd < MIN_LIQUIDITY_USD:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: liquidity ${liquidity_usd:,.0f} < ${MIN_LIQUIDITY_USD:,.0f}")
                        continue

                    # Отправляем alert
                    message = format_alert(token_data, checks_count=0, is_established=True)
                    # Established spikes now go to MAIN channel
                    target_chat = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else None
                    # Add inline buttons for main channel as well
                    keyboard = build_trade_bot_keyboard(token_address) if target_chat == TELEGRAM_CHAT_ID else None
                    success = await tg_send(session, message, chat_id=target_chat, reply_markup=keyboard)
                    
                    if success:
                        logger.info(f"✅ Alert sent for {token_data['token_symbol']} (established)")
                    else:
                        logger.error(f"❌ Failed to send alert for {token_data['token_symbol']} (established)")
                continue
            
            # Для новых токенов (< 2h)
            # 1) INSTANT ALERT для объемов >= MIN_VOLUME_SKIP_HOLDERS (например, $1M)
            if token_data.get("is_new_token", True) and token_data.get("volume_5m", 0) >= MIN_VOLUME_SKIP_HOLDERS and not tracker.recently_alerted(token_address, minutes=10) and not tracker.is_alerted(token_address):
                # Обновляем историю объемов для отслеживания всплесков
                tracker.update_volume_history(token_address, token_data["volume_5m"])
                
                logger.info(f"🔥 INSTANT ALERT (new high-volume): {token_data['token_symbol']} (${token_data['volume_5m']:,.0f} / 5m)")
                tracker.mark_alerted(token_address)
                # Получаем данные о holders и security из DexTools
                try:
                    dextools_data = await fetch_dextools_token_data(session, token_address)
                    if dextools_data:
                        dx_liq = dextools_data.get('liquidity_usd')
                        if dx_liq is None or dx_liq == 0:
                            logger.info("🔄 Liquidity source: GeckoTerminal (DexTools returned empty liquidity)")
                            dextools_data.pop('liquidity_usd', None)
                        else:
                            logger.info(f"🔄 Liquidity source: DexTools (${dx_liq:,.0f})")
                        token_data.update(dextools_data)
                    await asyncio.sleep(1.1)
                except Exception as e:
                    logger.debug(f"Failed to fetch DexTools data for {token_address}: {e}")
                    await asyncio.sleep(1.1)

                # GMGN данные уже получены параллельно выше, используем их из token_data
                
                # Проверяем адрес создателя токена (забаненные разработчики)
                # Сначала проверяем creator_address из GMGN данных (если есть)
                creator_address = token_data.get('creator_address')
                if creator_address:
                    creator_lower = creator_address.lower()
                    banned_addresses_lower = [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]
                    if creator_lower in banned_addresses_lower:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer address from GMGN data: {creator_address[:8]}...")
                        continue
                
                # Если creator_address не найден в GMGN, используем стандартную проверку через BSCScan
                pair_address = token_data.get('pair_address', '')
                is_banned = await check_banned_developer(session, token_address, pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer address")
                    continue

                # Проверка GMGN фильтров
                if EXCLUDE_HIGH_BUNDLER:
                    bundler_percentage = token_data.get('bundler_percentage')
                    if bundler_percentage is not None and bundler_percentage > MAX_BUNDLER_PERCENTAGE:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: high bundler percentage {bundler_percentage:.1f}% > {MAX_BUNDLER_PERCENTAGE:.1f}% (scam indicator)")
                        continue

                if EXCLUDE_LOW_TOTAL_FEES:
                    # Используем ТОЛЬКО реальные данные из GMGN (без fallback)
                    total_fees_gmgn = token_data.get('total_fees_bnb')
                    if total_fees_gmgn is None:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: GMGN total fees not available (required)")
                        continue
                    if total_fees_gmgn < MIN_TOTAL_FEES_GMGN_BNB:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: low total fees {total_fees_gmgn:.4f}BNB < {MIN_TOTAL_FEES_GMGN_BNB}BNB (scam indicator)")
                        continue
                
                # Фильтрация по безопасности
                is_honeypot = token_data.get('is_honeypot')
                if EXCLUDE_HONEYPOTS and is_honeypot is True:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                    continue
                elif EXCLUDE_HONEYPOTS and is_honeypot is None:
                    # Не блокируем токены когда статус неизвестен - DexTools может быть временно недоступен
                    logger.info(f"ℹ️ {token_data['token_symbol']}: honeypot status unknown (DexTools unavailable) - allowing token")

                buy_tax = token_data.get('buy_tax')
                sell_tax = token_data.get('sell_tax')
                if buy_tax is not None and buy_tax > MAX_BUY_TAX:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: buy tax {buy_tax}% > {MAX_BUY_TAX}%")
                    continue
                if sell_tax is not None and sell_tax > MAX_SELL_TAX:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: sell tax {sell_tax}% > {MAX_SELL_TAX}%")
                    continue
                if buy_tax is None or sell_tax is None:
                    logger.info(f"ℹ️ {token_data['token_symbol']}: tax info unknown (DexTools unavailable) - allowing token")

                # Проверяем концентрацию у топ-10 holders
                top10_holders_percent = token_data.get('top10_holders_percent')
                if top10_holders_percent is not None and top10_holders_percent > MAX_TOP10_HOLDERS_PERCENT:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: top 10 holders concentration {top10_holders_percent:.1f}% > {MAX_TOP10_HOLDERS_PERCENT:.1f}%")
                    continue
                elif top10_holders_percent is None:
                    logger.info(f"ℹ️ {token_data['token_symbol']}: top 10 holders data unavailable - allowing token")
                
                # Проверяем renounced контракт
                is_renounced = token_data.get('is_contract_renounced', False)
                if REQUIRE_RENOUNCED_CONTRACT and not is_renounced:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: contract not renounced")
                    continue
                
                # Проверяем mintable токены
                is_mintable = token_data.get('is_mintable', False)
                if EXCLUDE_MINTABLE and is_mintable:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: token is mintable")
                    continue
                
                # Проверяем proxy контракты
                is_proxy = token_data.get('is_proxy', False)
                if EXCLUDE_PROXY and is_proxy:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: contract is proxy")
                    continue
                
                # Проверяем потенциально scam токены
                is_potentially_scam = token_data.get('is_potentially_scam', False)
                if EXCLUDE_POTENTIALLY_SCAM and is_potentially_scam:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: potentially scam token")
                    continue
                
                # Проверяем blacklisted токены
                is_blacklisted = token_data.get('is_blacklisted', False)
                if EXCLUDE_BLACKLISTED and is_blacklisted:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: token is blacklisted")
                    continue

                # Holders check: high volume already implies skip; still log holders state
                holders = token_data.get('holders_count', 0)
                holders_unavailable = token_data.get('holders_unavailable', False)
                logger.info(f"🔍 {token_data['token_symbol']}: holders={holders}, unavailable={holders_unavailable}, volume_5m=${token_data.get('volume_5m',0):,.0f}, skip_threshold=${MIN_VOLUME_SKIP_HOLDERS:,.0f}")

                # Market cap check
                market_cap = token_data.get('fdv') or token_data.get('market_cap') or 0
                if market_cap < MIN_MARKET_CAP_USD:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: market cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
                    continue

                # Liquidity check
                liquidity_usd = token_data.get('liquidity_usd', 0)
                if liquidity_usd < MIN_LIQUIDITY_USD:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: liquidity ${liquidity_usd:,.0f} < ${MIN_LIQUIDITY_USD:,.0f}")
                    continue

                # Отправляем alert в основной канал
                message = format_alert(token_data, checks_count=0, is_established=False)
                target_chat = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else None
                keyboard = build_trade_bot_keyboard(token_address) if target_chat == TELEGRAM_CHAT_ID else None
                success = await tg_send(session, message, chat_id=target_chat, reply_markup=keyboard)
                if success:
                    logger.info(f"✅ Alert sent for {token_data['token_symbol']} (new high-volume)")
                else:
                    logger.error(f"❌ Failed to send alert for {token_data['token_symbol']} (new high-volume)")
                continue

            # 2) Иначе — обычная проверка стабильности (2 замера)
            # Сначала обновляем историю объемов для отслеживания всплесков
            tracker.update_volume_history(token_address, token_data["volume_5m"])
            
            # Проверяем всплеск объема (3x рост за 5 минут)
            growth_multiplier = tracker.check_volume_spike(token_address, token_data["volume_5m"])
            if growth_multiplier and not tracker.is_spike_alerted(token_address):
                logger.info(f"🚀 VOLUME SPIKE ALERT: {token_data['token_symbol']} - {growth_multiplier:.1f}x growth!")
                
                # Получаем данные о holders и security из DexTools
                try:
                    dextools_data = await fetch_dextools_token_data(session, token_address)
                    if dextools_data:
                        # Не перетираем ликвидность, если DexTools вернул 0/None
                        dx_liq = dextools_data.get('liquidity_usd')
                        if dx_liq is None or dx_liq == 0:
                            logger.info("🔄 Liquidity source: GeckoTerminal (DexTools returned empty liquidity)")
                            dextools_data.pop('liquidity_usd', None)
                        else:
                            logger.info(f"✅ DexTools: {token_address[:10]}... holders={dextools_data.get('holders_count', 'N/A')}, honeypot={dextools_data.get('is_honeypot', 'N/A')}, tax={dextools_data.get('buy_tax', 'N/A')}/{dextools_data.get('sell_tax', 'N/A')}")
                        
                        # Обновляем данные токена
                        token_data.update(dextools_data)
                    else:
                        logger.warning(f"⚠️ DexTools data unavailable for {token_data['token_symbol']}")
                except Exception as e:
                    logger.error(f"❌ DexTools error for {token_data['token_symbol']}: {e}")
                
                # Проверяем адрес создателя токена (забаненные разработчики)
                pair_address = token_data.get('pair_address', '')
                is_banned = await check_banned_developer(session, token_address, pair_address)
                if is_banned:
                    logger.info(f"🚫 Skipping volume spike for {token_data['token_symbol']}: banned developer address")
                    continue
                
                # Проверяем концентрацию у топ-10 holders
                top10_holders_percent = token_data.get('top10_holders_percent')
                if top10_holders_percent is not None and top10_holders_percent > MAX_TOP10_HOLDERS_PERCENT:
                    logger.info(f"⚠️ Skipping volume spike for {token_data['token_symbol']}: top 10 holders concentration {top10_holders_percent:.1f}% > {MAX_TOP10_HOLDERS_PERCENT:.1f}%")
                    continue
                
                # Проверяем renounced контракт
                is_renounced = token_data.get('is_contract_renounced', False)
                if REQUIRE_RENOUNCED_CONTRACT and not is_renounced:
                    logger.info(f"⚠️ Skipping volume spike for {token_data['token_symbol']}: contract not renounced")
                    continue
                
                # Проверяем mintable токены
                is_mintable = token_data.get('is_mintable', False)
                if EXCLUDE_MINTABLE and is_mintable:
                    logger.info(f"⚠️ Skipping volume spike for {token_data['token_symbol']}: token is mintable")
                    continue
                
                # Проверяем proxy контракты
                is_proxy = token_data.get('is_proxy', False)
                if EXCLUDE_PROXY and is_proxy:
                    logger.info(f"⚠️ Skipping volume spike for {token_data['token_symbol']}: contract is proxy")
                    continue
                
                # Проверяем потенциально scam токены
                is_potentially_scam = token_data.get('is_potentially_scam', False)
                if EXCLUDE_POTENTIALLY_SCAM and is_potentially_scam:
                    logger.info(f"⚠️ Skipping volume spike for {token_data['token_symbol']}: potentially scam token")
                    continue
                
                # Проверяем blacklisted токены
                is_blacklisted = token_data.get('is_blacklisted', False)
                if EXCLUDE_BLACKLISTED and is_blacklisted:
                    logger.info(f"⚠️ Skipping volume spike for {token_data['token_symbol']}: token is blacklisted")
                    continue
                
                # Формируем сообщение о всплеске объема
                # Находим предыдущий объем из истории
                volume_history = tracker.volume_history.get(token_address.lower(), [])
                previous_volume = 0
                if len(volume_history) >= 2:
                    # Берем предпоследний объем
                    previous_volume = volume_history[-2]["volume"]
                
                alert_text = format_more_volume_alert(token_data, previous_volume, token_data["volume_5m"], growth_multiplier)
                
                # Создаем inline кнопки
                keyboard = build_trade_bot_keyboard(token_address)
                
                # Отправляем алерт
                success = await tg_send(session, alert_text, reply_markup=keyboard, disable_web_page_preview=True)
                if success:
                    logger.info(f"✅ Volume spike alert sent for {token_data['token_symbol']}")
                    tracker.mark_spike_alerted(token_address)
                else:
                    logger.error(f"❌ Failed to send volume spike alert for {token_data['token_symbol']}")
            
            tracker.update(token_address, token_data["volume_5m"], token_data)

            if tracker.is_stable(token_address) and not tracker.recently_alerted(token_address, minutes=10) and not tracker.is_alerted(token_address):
                checks_count = len(tracker.tokens[token_address]["checks"])
                logger.info(f"🔥 ALERT: {token_data['token_symbol']} is stable! ({checks_count} checks)")
                
                # Сразу помечаем как alerted, чтобы избежать дублирования
                tracker.mark_alerted(token_address)
                
                # Получаем данные о holders и security из DexTools
                try:
                    dextools_data = await fetch_dextools_token_data(session, token_address)
                    if dextools_data:
                        # Не перетираем ликвидность, если DexTools вернул 0/None
                        dx_liq = dextools_data.get('liquidity_usd')
                        if dx_liq is None or dx_liq == 0:
                            logger.info("🔄 Liquidity source: GeckoTerminal (DexTools returned empty liquidity)")
                            dextools_data.pop('liquidity_usd', None)
                        else:
                            logger.info(f"🔄 Liquidity source: DexTools (${dx_liq:,.0f})")
                        # Не перезаписываем market cap/fdv если DexTools вернул 0/None (используем данные из GeckoTerminal/DexScreener)
                        dx_mcap = dextools_data.get('mcap')
                        dx_fdv = dextools_data.get('fdv')
                        if dx_mcap is None or dx_mcap == 0:
                            dextools_data.pop('mcap', None)
                        if dx_fdv is None or dx_fdv == 0:
                            dextools_data.pop('fdv', None)
                        
                        token_data.update(dextools_data)
                        logger.debug(f"Fetched DexTools data: holders={dextools_data.get('holders_count')}, honeypot={dextools_data.get('is_honeypot')}")
                        
                        # Когда DexTools недоступен, устанавливаем holders_unavailable=True если holders=0
                        if token_data.get('holders_count', 0) == 0 and not token_data.get('holders_unavailable', False):
                            token_data['holders_unavailable'] = True
                            logger.info(f"ℹ️ Setting holders_unavailable=True for {token_data['token_symbol']} (DexTools unavailable)")
                    else:
                        # Если DexTools вернул пустой словарь, устанавливаем holders_unavailable
                        if token_data.get('holders_count', 0) == 0:
                            token_data['holders_unavailable'] = True
                            logger.info(f"ℹ️ Setting holders_unavailable=True for {token_data['token_symbol']} (DexTools returned empty)")
                    # Rate limit: DexTools allows 1 request/second
                    await asyncio.sleep(1.1)
                except Exception as e:
                    logger.debug(f"Failed to fetch DexTools data for {token_address}: {e}")
                    # При ошибке тоже устанавливаем holders_unavailable если holders=0
                    if token_data.get('holders_count', 0) == 0:
                        token_data['holders_unavailable'] = True
                        logger.info(f"ℹ️ Setting holders_unavailable=True for {token_data['token_symbol']} (DexTools error)")
                    await asyncio.sleep(1.1)

                # GMGN данные уже получены параллельно выше, используем их из token_data
                
                # Проверяем адрес создателя токена (забаненные разработчики)
                # Сначала проверяем creator_address из GMGN данных (если есть)
                creator_address = token_data.get('creator_address')
                if creator_address:
                    creator_lower = creator_address.lower()
                    banned_addresses_lower = [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]
                    if creator_lower in banned_addresses_lower:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer address from GMGN data: {creator_address[:8]}...")
                        continue
                
                # Если creator_address не найден в GMGN, используем стандартную проверку через BSCScan
                try:
                    pair_address = token_data.get('pair_address', '')
                    if not creator_address:
                        creator_address = await fetch_token_creator_address(session, token_address, pair_address)
                    if creator_address:
                        creator_lower = creator_address.lower()
                        if creator_lower in [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]:
                            logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer address {creator_lower[:8]}...")
                            continue
                    else:
                        # Если не удалось получить адрес создателя, проверяем транзакцию создания пула через factory
                        if pair_address and BSCSCAN_API_KEY:
                            factory_address = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"  # PancakeSwap Factory
                            url = "https://api.bscscan.com/api"
                            params = {
                                "module": "account",
                                "action": "txlist",
                                "address": pair_address,
                                "startblock": 0,
                                "endblock": 99999999,
                                "page": 1,
                                "offset": 1,
                                "sort": "asc",
                                "apikey": BSCSCAN_API_KEY
                            }
                            try:
                                async with session.get(url, params=params, timeout=5) as r:  # Уменьшен таймаут до 5 секунд
                                    if r.status == 200:
                                        data = await r.json()
                                        if data.get("status") == "1" and data.get("result") and len(data["result"]) > 0:
                                            first_tx = data["result"][0]
                                            tx_from = first_tx.get("from", "").lower()
                                            tx_to = first_tx.get("to", "").lower()
                                            if tx_to == factory_address.lower():
                                                if tx_from in [addr.lower() for addr in BANNED_DEVELOPER_ADDRESSES]:
                                                    logger.info(f"🚫 Skipping {token_data['token_symbol']}: banned developer called factory {tx_from[:8]}...")
                                                    continue
                            except asyncio.TimeoutError:
                                logger.debug(f"Timeout checking factory for {token_address[:8]}...")
                                # Продолжаем работу, не блокируем токен при таймауте
                            except Exception as e:
                                logger.debug(f"Error checking factory for {token_address[:8]}...: {e}")
                                # Продолжаем работу, не блокируем токен при ошибке
                except Exception as e:
                    logger.debug(f"Error fetching creator address for {token_address}: {e}")
                    # Не блокируем токен если не удалось получить адрес создателя
                
                # Проверка GMGN фильтров
                if EXCLUDE_HIGH_BUNDLER:
                    bundler_percentage = token_data.get('bundler_percentage')
                    if bundler_percentage is not None and bundler_percentage > MAX_BUNDLER_PERCENTAGE:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: high bundler percentage {bundler_percentage:.1f}% > {MAX_BUNDLER_PERCENTAGE:.1f}% (scam indicator)")
                        continue
                
                if EXCLUDE_LOW_TOTAL_FEES:
                    # Используем ТОЛЬКО реальные данные из GMGN (без fallback)
                    total_fees_gmgn = token_data.get('total_fees_bnb')
                    if total_fees_gmgn is None:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: GMGN total fees not available (required)")
                        continue
                    if total_fees_gmgn < MIN_TOTAL_FEES_GMGN_BNB:
                        logger.info(f"🚫 Skipping {token_data['token_symbol']}: low total fees {total_fees_gmgn:.4f}BNB < {MIN_TOTAL_FEES_GMGN_BNB}BNB (scam indicator)")
                        continue
                
                # Фильтрация по безопасности
                # Проверяем honeypot
                is_honeypot = token_data.get('is_honeypot')
                if EXCLUDE_HONEYPOTS and is_honeypot is True:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                    continue
                elif EXCLUDE_HONEYPOTS and is_honeypot is None:
                    # Не блокируем токены когда статус неизвестен - DexTools может быть временно недоступен
                    logger.info(f"ℹ️ {token_data['token_symbol']}: honeypot status unknown (DexTools unavailable) - allowing token")
                
                # Проверяем buy/sell tax
                buy_tax = token_data.get('buy_tax')
                sell_tax = token_data.get('sell_tax')
                
                # Проверяем налоги только если они известны
                if buy_tax is not None and buy_tax > MAX_BUY_TAX:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: buy tax {buy_tax}% > {MAX_BUY_TAX}%")
                    continue
                if sell_tax is not None and sell_tax > MAX_SELL_TAX:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: sell tax {sell_tax}% > {MAX_SELL_TAX}%")
                    continue
                
                # Логируем если налоги неизвестны, но не блокируем
                if buy_tax is None or sell_tax is None:
                    logger.info(f"ℹ️ {token_data['token_symbol']}: tax info unknown (DexTools unavailable) - allowing token")
                
                # Проверяем концентрацию у топ-10 holders
                top10_holders_percent = token_data.get('top10_holders_percent')
                if top10_holders_percent is not None and top10_holders_percent > MAX_TOP10_HOLDERS_PERCENT:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: top 10 holders concentration {top10_holders_percent:.1f}% > {MAX_TOP10_HOLDERS_PERCENT:.1f}%")
                    continue
                elif top10_holders_percent is None:
                    logger.info(f"ℹ️ {token_data['token_symbol']}: top 10 holders data unavailable - allowing token")
                
                # Проверяем renounced контракт
                is_renounced = token_data.get('is_contract_renounced', False)
                if REQUIRE_RENOUNCED_CONTRACT and not is_renounced:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: contract not renounced")
                    continue
                
                # Проверяем mintable токены
                is_mintable = token_data.get('is_mintable', False)
                if EXCLUDE_MINTABLE and is_mintable:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: token is mintable")
                    continue
                
                # Проверяем proxy контракты
                is_proxy = token_data.get('is_proxy', False)
                if EXCLUDE_PROXY and is_proxy:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: contract is proxy")
                    continue
                
                # Проверяем потенциально scam токены
                is_potentially_scam = token_data.get('is_potentially_scam', False)
                if EXCLUDE_POTENTIALLY_SCAM and is_potentially_scam:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: potentially scam token")
                    continue
                
                # Проверяем blacklisted токены
                is_blacklisted = token_data.get('is_blacklisted', False)
                if EXCLUDE_BLACKLISTED and is_blacklisted:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: token is blacklisted")
                    continue
                
                # Проверяем минимальное количество holders (пропускаем при высоком объеме или если данные недоступны)
                holders = token_data.get('holders_count', 0)
                holders_unavailable = token_data.get('holders_unavailable', False)
                volume_5m = token_data.get("volume_5m", 0)
                
                if volume_5m >= MIN_VOLUME_SKIP_HOLDERS:
                    logger.info(f"🚀 High volume token {token_data['token_symbol']}: ${volume_5m:,.0f} - skipping holders check")
                elif holders_unavailable:
                    logger.info(f"ℹ️ {token_data['token_symbol']}: holders data unavailable (both APIs returned 0) - allowing token without holders info")
                elif holders < MIN_HOLDERS:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: only {holders} holders (min {MIN_HOLDERS})")
                    continue
                
                # Проверяем минимальный market cap
                market_cap_raw = token_data.get('fdv') or token_data.get('market_cap') or 0
                market_cap = float(market_cap_raw) if market_cap_raw else 0
                if market_cap < MIN_MARKET_CAP_USD:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: market cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
                    continue
                
                # Проверяем минимальную ликвидность
                liquidity_usd = token_data.get('liquidity_usd', 0)
                if liquidity_usd < MIN_LIQUIDITY_USD:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: liquidity ${liquidity_usd:,.0f} < ${MIN_LIQUIDITY_USD:,.0f}")
                    continue
                
                # Отправляем alert
                message = format_alert(token_data, checks_count, is_established=False)
                # New-token normal alerts go to MAIN channel explicitly
                target_chat = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else None
                keyboard = build_trade_bot_keyboard(token_address) if target_chat == TELEGRAM_CHAT_ID else None
                success = await tg_send(session, message, chat_id=target_chat, reply_markup=keyboard)
                
                if success:
                    logger.info(f"✅ Alert sent for {token_data['token_symbol']} (new)")
                else:
                    logger.error(f"❌ Failed to send alert for {token_data['token_symbol']}")
        
        # Cleanup
        tracker.cleanup_old()
    
    except Exception as e:
        logger.error(f"Scan error: {e}", exc_info=True)

async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("Starting New Tokens Monitor Bot")
    logger.info(f"NEW TOKENS (< {MAX_TOKEN_AGE_HOURS}h): MIN_VOLUME ${MIN_5M_VOLUME_USD_NEW:,.0f}, MIN_MCAP ${MIN_MARKET_CAP_USD:,.0f}")
    logger.info(f"ESTABLISHED TOKENS (> {MAX_TOKEN_AGE_HOURS}h): MIN_VOLUME ${MIN_5M_VOLUME_USD_ESTABLISHED:,.0f}")
    logger.info(f"MAX VOLUME FILTER: ${MAX_5M_VOLUME_USD:,.0f} (exclude too popular tokens)")
    logger.info(f"SKIP HOLDERS CHECK: ${MIN_VOLUME_SKIP_HOLDERS:,.0f}+ volume (high volume tokens)")
    logger.info(f"STABILITY_CHECKS: {MIN_STABILITY_CHECKS} (~{MIN_STABILITY_CHECKS * SCAN_INTERVAL_SECONDS // 60} min)")
    logger.info(f"SCAN_INTERVAL: {SCAN_INTERVAL_SECONDS}s")
    logger.info("=" * 50)
    
    tracker = TokenTracker()
    
    async with aiohttp.ClientSession() as session:
        # Стартовое сообщение убрано по запросу пользователя
        
        while True:
            try:
                await scan_once(session, tracker)
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                await asyncio.sleep(SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

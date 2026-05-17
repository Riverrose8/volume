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
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# =========================
# Конфигурация
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", TELEGRAM_CHAT_ID)

# Интервалы и пороги
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))  # Сканируем каждые 30 сек

# Для новых токенов (< 2 часов)
MIN_5M_VOLUME_USD_NEW = float(os.getenv("MIN_5M_VOLUME_USD_NEW", "300000"))  # $300K за 5 минут для новых токенов
MAX_TOKEN_AGE_HOURS = float(os.getenv("MAX_TOKEN_AGE_HOURS", "2"))  # Максимум 2 часа для "новых" токенов
MIN_STABILITY_CHECKS = int(os.getenv("MIN_STABILITY_CHECKS", "2"))  # Минимум 2 проверки (2 * 30 сек = 1 минута)

# Для устоявшихся токенов (> 2 часов) - ловим резкие скачки объема
MIN_5M_VOLUME_USD_ESTABLISHED = float(os.getenv("MIN_5M_VOLUME_USD_ESTABLISHED", "3000000"))  # $3M за 5 минут

# Максимальный объем для исключения слишком популярных токенов
MAX_5M_VOLUME_USD = float(os.getenv("MAX_5M_VOLUME_USD", "40000000"))  # $40M за 5 минут

# Фильтры безопасности
MIN_HOLDERS = int(os.getenv("MIN_HOLDERS", "200"))  # Минимум 200 держателей
MIN_MARKET_CAP_USD = float(os.getenv("MIN_MARKET_CAP_USD", "100000"))  # Минимум $100K market cap
MAX_BUY_TAX = float(os.getenv("MAX_BUY_TAX", "3"))  # Максимум 3% tax на покупку
MAX_SELL_TAX = float(os.getenv("MAX_SELL_TAX", "3"))  # Максимум 3% tax на продажу
EXCLUDE_HONEYPOTS = os.getenv("EXCLUDE_HONEYPOTS", "true").lower() == "true"  # Исключать honeypots

DEDUP_TTL_HOURS = int(os.getenv("DEDUP_TTL_HOURS", "24"))

# BSCScan API Key
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")

# DexTools API Key
DEXTOOLS_API_KEY = os.getenv("DEXTOOLS_API_KEY", "")

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
        self.alerted.add(token_address)
    
    def is_alerted(self, token_address: str) -> bool:
        """Проверяет, был ли уже отправлен alert"""
        return token_address in self.alerted
    
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
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tokens")

# =========================
# Telegram API
# =========================

async def tg_send(session: aiohttp.ClientSession, text: str, chat_id: str = None) -> bool:
    """Отправка сообщения в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not (chat_id or TELEGRAM_CHAT_ID):
        logger.warning("Telegram credentials not set")
        return False
    
    target_chat = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Логируем отправку для отладки дублирования
    logger.info(f"📤 Sending Telegram message to {target_chat}")
    
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
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
        if not volume_5m:
            return None
        
        # Определяем какой токен - новый токен (не WBNB/USDT)
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        # Известные стейблкоины и wrapped токены
        STABLE_TOKENS = ["WBNB", "USDT", "BUSD", "USDC", "BNB", "ETH", "WETH", "DAI"]
        
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
        
        # Объем за 5 минут
        volume_5m = float(attrs.get("volume_usd", {}).get("m5", 0))
        if not volume_5m:
            return None
        
        # Адрес пула
        pool_address = attrs.get("address", "").lower()
        if not pool_address:
            return None
        
        # Извлекаем адрес токена из relationships
        relationships = pool.get("relationships", {})
        base_token_rel = relationships.get("base_token", {})
        base_token_data = base_token_rel.get("data", {})
        token_address = base_token_data.get("id", "").replace("bsc_", "").lower() if base_token_data else None
        
        # Если не получилось извлечь адрес токена, пропускаем этот пул
        # GeckoTerminal пулы без адреса токена будут дополнены через DexScreener
        if not token_address or token_address == pool_address:
            return None
        
        # Парсим имя пула
        pool_name = attrs.get("name", "Unknown")
        
        return {
            "source": "geckoterminal",
            "token_address": token_address,  # Используем pool address
            "token_symbol": pool_name.split("/")[0].strip() if "/" in pool_name else "???",
            "token_name": pool_name,
            "pair_address": pool_address,
            "pair_name": pool_name,
            "dex": "unknown",  # GeckoTerminal не всегда дает DEX ID
            "created_at": created_at,
            "age_hours": age_hours,
            "volume_5m": volume_5m,
            "volume_1h": float(attrs.get("volume_usd", {}).get("h1", 0)),
            "liquidity_usd": float(attrs.get("reserve_in_usd", 0)),
            "fdv": attrs.get("fdv_usd"),
            "market_cap": attrs.get("market_cap_usd"),
            "price_usd": attrs.get("base_token_price_usd"),
            "price_change_5m": float(attrs.get("price_change_percentage", {}).get("m5", 0)),
            "txns_5m_buys": attrs.get("transactions", {}).get("m5", {}).get("buys", 0),
            "txns_5m_sells": attrs.get("transactions", {}).get("m5", {}).get("sells", 0),
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
    """
    if not DEXTOOLS_API_KEY:
        logger.error("❌ DexTools API key not configured! Set DEXTOOLS_API_KEY in .env")
        return {}
    
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
                logger.error(f"❌ DexTools info API error: status {r.status}, body: {body[:200]}")
                return {}
            
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
            
            # Дополнительная информация
            result["liquidity_usd"] = info.get("liquidity", {}).get("usd", 0) if isinstance(info.get("liquidity"), dict) else 0
            result["price_usd"] = info.get("price", 0)
            result["price_change_24h"] = info.get("priceChange24h", 0)
            result["volume_24h"] = info.get("volume24h", 0)
            
            # Социальные ссылки
            result["website"] = info.get("website", "")
            result["telegram"] = info.get("telegram", "")
            result["twitter"] = info.get("twitter", "")
            result["discord"] = info.get("discord", "")
            
            # DEXTScore (если доступен)
            result["dext_score"] = info.get("dextScore", 0)
            
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
            result["is_honeypot"] = False
            result["is_contract_renounced"] = False
            result["is_mintable"] = False
            result["is_proxy"] = False
            result["is_blacklisted"] = False
            result["is_potentially_scam"] = False
            result["buy_tax"] = 0
            result["sell_tax"] = 0
        
        logger.info(f"✅ DexTools: {token_address[:8]}... holders={result.get('holders_count')}, honeypot={result.get('is_honeypot')}, tax={result.get('buy_tax')}/{result.get('sell_tax')}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ DexTools API exception: {e}", exc_info=True)
        return {}

# =========================
# Форматирование сообщений
# =========================

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
    
    # Different headers for new vs established tokens
    if is_established:
        text = "🔴 <b>BSC VOLUME SPIKE!</b> 🔴\n\n"
        text += f"<b>${token['token_symbol']}</b> (Age: {age_str})\n\n"
        text += f"<b>💥 {volume_str} volume spike in last 5 minutes!</b>\n"
    else:
        text = "🟡 <b>BSC Volume Alert</b> 🟡\n\n"
        text += f"<b>${token['token_symbol']}</b>\n\n"
        text += f"<b>🔥 {volume_str} volume in last 5 minutes</b>\n"
    
    text += f"<b>📈 MC (FDV):</b> {fdv_str}\n"
    
    # Holders and distribution (if available)
    if holders_count:
        text += f"<b>👤 Holders:</b> {holders_count:,}"
        top10_percent = token.get('top10_holders_percent')
        if top10_percent is not None and top10_percent > 0:
            text += f" | 🥷 <b>Top 10:</b> {top10_percent:.1f}%"
        text += "\n"
    
    # DEXTScore (если доступен)
    dext_score = token.get('dext_score')
    if dext_score and dext_score > 0:
        score_emoji = "🟢" if dext_score >= 80 else "🟡" if dext_score >= 60 else "🔴"
        text += f"<b>{score_emoji} DEXTScore:</b> {dext_score}/100\n"
    
    # Ликвидность
    liquidity_usd = token.get('liquidity_usd')
    if liquidity_usd and liquidity_usd > 0:
        liquidity_str = f"${liquidity_usd / 1_000_000:.1f}M" if liquidity_usd >= 1_000_000 else f"${liquidity_usd / 1_000:.0f}K"
        text += f"<b>💧 Liquidity:</b> {liquidity_str}\n"
    
    # Изменение цены за 24ч
    price_change_24h = token.get('price_change_24h')
    if price_change_24h is not None:
        change_emoji = "📈" if price_change_24h > 0 else "📉" if price_change_24h < 0 else "➡️"
        text += f"<b>{change_emoji} 24h Change:</b> {price_change_24h:+.1f}%\n"
    
    # Security info from DexTools (if available)
    is_honeypot = token.get('is_honeypot')
    buy_tax = token.get('buy_tax')
    sell_tax = token.get('sell_tax')
    liquidity_locked = token.get('liquidity_locked')
    is_contract_renounced = token.get('is_contract_renounced')
    
    # Security warnings/badges
    if is_honeypot:
        text += "⚠️ <b>WARNING: Potential Honeypot!</b>\n"
    
    # Tax info removed from display (but still filtered - tokens with >5% tax are blocked)
    # if buy_tax is not None or sell_tax is not None:
    #     buy_str = f"{buy_tax:.1f}%" if buy_tax is not None else "N/A"
    #     sell_str = f"{sell_tax:.1f}%" if sell_tax is not None else "N/A"
    #     text += f"<b>💸 Tax:</b> Buy {buy_str} / Sell {sell_str}\n"
    
    if liquidity_locked is not None:
        lock_emoji = "🔒" if liquidity_locked else "🔓"
        lock_text = "Locked" if liquidity_locked else "Not Locked"
        text += f"<b>{lock_emoji} Liquidity:</b> {lock_text}\n"
    
    if is_contract_renounced is not None:
        renounced_emoji = "✅" if is_contract_renounced else "❌"
        renounced_text = "Renounced" if is_contract_renounced else "Not Renounced"
        text += f"<b>{renounced_emoji} Ownership:</b> {renounced_text}\n"
    
    # Contract address - monospace
    text += f"<b>🔗 CA:</b> <code>{token['token_address']}</code>\n\n"
    
    # Links
    token_addr = token['token_address']
    
    # GMGN link
    gmgn_url = f"https://gmgn.ai/bsc/token/{token_addr}?tag=whale&min=5&isInputValue=true"
    
    # PancakeSwap swap link (USDT pair)
    pancake_url = f"https://pancakeswap.finance/swap?chain=bsc&inputCurrency={token_addr}&outputCurrency=0x55d398326f99059fF775485246999027B3197955"
    
    # Krystal link
    krystal_url = f"https://defi.krystal.app/token?chainId=56&address={token_addr}"
    
    # Based bot link - формат: r_ssdssaass_b_TOKEN_ADDRESS
    based_url = f"https://t.me/based_eth_bot?start=r_ssdssaass_b_{token_addr}"
    
    text += f"<a href='{gmgn_url}'>GMGN</a> | "
    text += f"<a href='{pancake_url}'>Pancake Swap</a> | "
    text += f"<a href='{krystal_url}'>Krystal</a> | "
    text += f"<a href='{based_url}'>Based</a>\n\n"
    
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
        # Параллельно запрашиваем данные из обоих источников
        # GeckoTerminal - 10 страниц (200 пулов) с задержками для избежания rate limits
        dex_task = fetch_dexscreener_new_pairs(session)
        gecko_tasks = [
            fetch_geckoterminal_new_pools(session, page=i)
            for i in range(1, 11)  # 10 страниц = 200 пулов
        ]
        
        results = await asyncio.gather(dex_task, *gecko_tasks, return_exceptions=True)
        
        dex_pairs = results[0] if not isinstance(results[0], Exception) else []
        gecko_pools = []
        for i in range(1, len(results)):
            if not isinstance(results[i], Exception):
                gecko_pools.extend(results[i])
        
        # Парсим данные
        tokens: Dict[str, Dict] = {}  # token_address -> data
        
        # DexScreener
        for pair in dex_pairs:
            parsed = parse_dexscreener_pair(pair)
            if parsed:
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
        
        # GeckoTerminal
        for pool in gecko_pools:
            parsed = parse_geckoterminal_pool(pool)
            if parsed:
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
        
        logger.info(f"Found {len(tokens)} tokens matching criteria (new: vol >= ${MIN_5M_VOLUME_USD_NEW:,.0f} mcap >= ${MIN_MARKET_CAP_USD:,.0f} age < {MAX_TOKEN_AGE_HOURS}h | established: vol >= ${MIN_5M_VOLUME_USD_ESTABLISHED:,.0f} age > {MAX_TOKEN_AGE_HOURS}h | max: vol <= ${MAX_5M_VOLUME_USD:,.0f})")
        
        # Логируем топ-5 токенов по объему для отладки
        if tokens:
            sorted_tokens = sorted(tokens.values(), key=lambda t: t["volume_5m"], reverse=True)[:5]
            logger.info("Top 5 tokens by 5m volume:")
            for t in sorted_tokens:
                source = t.get("source", "unknown")
                logger.info(f"  {t['token_symbol']}: ${t['volume_5m']:,.0f} (age: {t['age_hours']:.1f}h, source: {source})")
        
        # Обновляем tracker
        for token_address, token_data in tokens.items():
            is_new_token = token_data.get("is_new_token", True)
            
            # Для устоявшихся токенов ($3M+) - отправляем алерт сразу, без проверки стабильности
            if not is_new_token:
                if not tracker.is_alerted(token_address):
                    logger.info(f"🔥 INSTANT ALERT: {token_data['token_symbol']} (established token with ${token_data['volume_5m']:,.0f} volume spike!)")
                    
                    # Сразу помечаем как alerted, чтобы избежать дублирования
                    tracker.mark_alerted(token_address)
                    
                    # Получаем данные о holders и security из DexTools
                    try:
                        dextools_data = await fetch_dextools_token_data(session, token_address)
                        if dextools_data:
                            token_data.update(dextools_data)
                            logger.info(f"📊 DexTools data: holders={dextools_data.get('holders_count')}, honeypot={dextools_data.get('is_honeypot')}, tax={dextools_data.get('buy_tax')}/{dextools_data.get('sell_tax')}")
                        else:
                            logger.info(f"⚠️ No DexTools data returned for {token_address}")
                        # Rate limit: DexTools allows 1 request/second
                        await asyncio.sleep(1.1)
                    except Exception as e:
                        logger.info(f"❌ DexTools API error for {token_address}: {e}")
                        await asyncio.sleep(1.1)
                    
                    # Фильтрация по безопасности
                    # Проверяем honeypot
                    if EXCLUDE_HONEYPOTS and token_data.get('is_honeypot'):
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                        continue
                    
                    # Проверяем buy/sell tax
                    buy_tax = token_data.get('buy_tax') or 0
                    sell_tax = token_data.get('sell_tax') or 0
                    if buy_tax > MAX_BUY_TAX:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: buy tax {buy_tax}% > {MAX_BUY_TAX}%")
                        continue
                    if sell_tax > MAX_SELL_TAX:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: sell tax {sell_tax}% > {MAX_SELL_TAX}%")
                        continue
                    
                    # Проверяем минимальное количество holders
                    holders = token_data.get('holders_count', 0)
                    if holders < MIN_HOLDERS:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: only {holders} holders (min {MIN_HOLDERS})")
                        continue
                    
                    # Проверяем минимальный market cap
                    market_cap = token_data.get('fdv') or token_data.get('market_cap') or 0
                    if market_cap < MIN_MARKET_CAP_USD:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: market cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
                        continue
                    
                    # Отправляем alert
                    message = format_alert(token_data, checks_count=0, is_established=True)
                    success = await tg_send(session, message)
                    
                    if success:
                        logger.info(f"✅ Alert sent for {token_data['token_symbol']} (established)")
                    else:
                        logger.error(f"❌ Failed to send alert for {token_data['token_symbol']} (established)")
                continue
            
            # Для новых токенов (< 2h) - проверяем стабильность
            tracker.update(token_address, token_data["volume_5m"], token_data)
            
            if tracker.is_stable(token_address) and not tracker.is_alerted(token_address):
                checks_count = len(tracker.tokens[token_address]["checks"])
                logger.info(f"🔥 ALERT: {token_data['token_symbol']} is stable! ({checks_count} checks)")
                
                # Сразу помечаем как alerted, чтобы избежать дублирования
                tracker.mark_alerted(token_address)
                
                # Получаем данные о holders и security из DexTools
                try:
                    dextools_data = await fetch_dextools_token_data(session, token_address)
                    if dextools_data:
                        token_data.update(dextools_data)
                        logger.debug(f"Fetched DexTools data: holders={dextools_data.get('holders_count')}, honeypot={dextools_data.get('is_honeypot')}")
                    # Rate limit: DexTools allows 1 request/second
                    await asyncio.sleep(1.1)
                except Exception as e:
                    logger.debug(f"Failed to fetch DexTools data for {token_address}: {e}")
                    await asyncio.sleep(1.1)
                
                # Фильтрация по безопасности
                # Проверяем honeypot
                if EXCLUDE_HONEYPOTS and token_data.get('is_honeypot'):
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                    continue
                
                # Проверяем buy/sell tax
                buy_tax = token_data.get('buy_tax') or 0
                sell_tax = token_data.get('sell_tax') or 0
                if buy_tax > MAX_BUY_TAX:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: buy tax {buy_tax}% > {MAX_BUY_TAX}%")
                    continue
                if sell_tax > MAX_SELL_TAX:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: sell tax {sell_tax}% > {MAX_SELL_TAX}%")
                    continue
                
                # Проверяем минимальное количество holders
                holders = token_data.get('holders_count', 0)
                if holders < MIN_HOLDERS:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: only {holders} holders (min {MIN_HOLDERS})")
                    continue
                
                # Проверяем минимальный market cap
                market_cap = token_data.get('fdv') or token_data.get('market_cap') or 0
                if market_cap < MIN_MARKET_CAP_USD:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: market cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
                    continue
                
                # Отправляем alert
                message = format_alert(token_data, checks_count, is_established=False)
                success = await tg_send(session, message)
                
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
    logger.info(f"STABILITY_CHECKS: {MIN_STABILITY_CHECKS} (~{MIN_STABILITY_CHECKS * SCAN_INTERVAL_SECONDS // 60} min)")
    logger.info(f"SCAN_INTERVAL: {SCAN_INTERVAL_SECONDS}s")
    logger.info("=" * 50)
    
    tracker = TokenTracker()
    
    async with aiohttp.ClientSession() as session:
        # Отправляем стартовое сообщение
        await tg_send(session, "🤖 <b>New Tokens Monitor Bot Started</b>\n\nMonitoring BSC for new tokens...")
        
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


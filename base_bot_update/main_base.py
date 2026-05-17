#!/usr/bin/env python3
"""
Bot для мониторинга новых токенов на Base с высоким объемом торгов.
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

# Загружаем переменные окружения из .env_base
load_dotenv('.env_base')

# =========================
# Конфигурация
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ALERT_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", TELEGRAM_CHAT_ID)
TELEGRAM_TEST_CHAT_ID = os.getenv("TELEGRAM_TEST_CHAT_ID", "")
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Optional external trade bot link templates for inline buttons (used in TEST_MODE)
# Example: MAESTRO_URL_TEMPLATE="https://t.me/maestro?start=bsc_{token}"
#          BLOOM_URL_TEMPLATE="https://t.me/bloom?start=bsc_{token}"
MAESTRO_URL_TEMPLATE = os.getenv("MAESTRO_URL_TEMPLATE", "").strip()
# Bloom URL template
BLOOM_URL_TEMPLATE = os.getenv("BLOOM_URL_TEMPLATE", "").strip()

# Интервалы и пороги
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "15"))  # Сканируем каждые 15 сек

# Для новых токенов (< 4 часов)
MIN_5M_VOLUME_USD_NEW = float(os.getenv("MIN_5M_VOLUME_USD_NEW", "30000"))  # $30K за 5 минут для новых токенов на Base
MAX_TOKEN_AGE_HOURS = float(os.getenv("MAX_TOKEN_AGE_HOURS", "4"))  # Максимум 4 часа для "новых" токенов
MIN_STABILITY_CHECKS = int(os.getenv("STABILITY_CHECKS", "1"))  # Минимум 1 проверка для быстрого алерта

# Для устоявшихся токенов (> 2 часов) - ловим резкие скачки объема
MIN_5M_VOLUME_USD_ESTABLISHED = float(os.getenv("MIN_5M_VOLUME_USD_ESTABLISHED", "500000"))  # $500K за 5 минут

# Максимальный объем для исключения слишком популярных токенов
MAX_5M_VOLUME_USD = float(os.getenv("MAX_5M_VOLUME_USD", "40000000"))  # $40M за 5 минут

# Минимальный объем для пропуска проверки держателей
MIN_VOLUME_SKIP_HOLDERS = float(os.getenv("MIN_VOLUME_SKIP_HOLDERS", "1000000"))  # $1M за 5 минут

# Фильтры безопасности
MIN_HOLDERS = int(os.getenv("MIN_HOLDERS", "40"))  # Минимум 40 держателей
MIN_MARKET_CAP_USD = float(os.getenv("MIN_MARKET_CAP_USD", "60000"))  # Минимум $60K market cap
MIN_LIQUIDITY_USD = float(os.getenv("MIN_LIQUIDITY_USD", "10000"))  # Минимум $10K ликвидности
MAX_BUY_TAX = float(os.getenv("MAX_BUY_TAX", "3"))  # Максимум 3% tax на покупку
MAX_SELL_TAX = float(os.getenv("MAX_SELL_TAX", "3"))  # Максимум 3% tax на продажу
EXCLUDE_HONEYPOTS = os.getenv("EXCLUDE_HONEYPOTS", "true").lower() == "true"  # Исключать honeypots

DEDUP_TTL_HOURS = int(os.getenv("DEDUP_TTL_HOURS", "24"))

# BSCScan API Key
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")

# DexTools API Key
DEXTOOLS_API_KEY = os.getenv("DEXTOOLS_API_KEY", "")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY", "")

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
        # GraphQL запрос для получения новых токенов на Base (пока без Four.Meme эквивалента)
        query = """
        query {
          EVM(dataset: combined, network: base) {
            DEXTradeByTokens(
              orderBy: {descendingByField: "Block_Time"}
              limit: {count: 50}
              where: {
                Trade: {
                  Dex: {ProtocolName: {in: ["uniswap_v3", "aerodrome"]}}
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
        
        # Проверяем что это не WETH/USDC на Base
        if token_address in ["0x4200000000000000000000000000000000000006", "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"]:
            return None
        
        return {
            "token_address": token_address,
            "token_symbol": currency["Symbol"],
            "token_name": currency["Name"],
            "volume_5m": volume_5m,
            "age_hours": age_hours,
            "is_new_token": age_hours < MAX_TOKEN_AGE_HOURS,
            "source": "base_dex"
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
        # Honeypot.is API для проверки Base токенов
        url = f"https://api.honeypot.is/v2/IsHoneypot"
        params = {
            "address": token_address,
            "chainID": 8453  # Base chain ID
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
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tracked tokens: {e}")
    
    def is_alerted(self, token_address: str) -> bool:
        """Проверяет, был ли уже отправлен alert"""
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
    
    def check_volume_spike(self, token_address: str, current_volume: float) -> bool:
        """Проверяет, есть ли всплеск объема (4x рост за 5 минут)"""
        addr = token_address.lower()
        
        if addr not in self.volume_history or len(self.volume_history[addr]) < 2:
            return False
        
        now = datetime.now(timezone.utc)
        five_minutes_ago = now - timedelta(minutes=5)
        
        # Находим объем 5 минут назад
        historical_volumes = [
            entry["volume"] for entry in self.volume_history[addr]
            if entry["timestamp"] <= five_minutes_ago
        ]
        
        if not historical_volumes:
            return False
        
        # Берем последний объем из 5-минутного окна
        previous_volume = historical_volumes[-1]
        
        # Проверяем рост в 4 раза
        if previous_volume > 0 and current_volume >= previous_volume * 4:
            logger.info(f"🚀 Volume spike detected: {token_address} from ${previous_volume:,.0f} to ${current_volume:,.0f} ({(current_volume/previous_volume):.1f}x)")
            return True
        
        return False

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
    """Builds inline keyboard with Maestro / Bloom / Based links for TEST_MODE.
    Uses env templates for Maestro/Bloom if provided. Always includes Based link.
    """
    try:
        buttons: List[List[Dict[str, str]]] = []

        row: List[Dict[str, str]] = []

        if MAESTRO_URL_TEMPLATE:
            row.append({
                "text": "Maestro",
                "url": MAESTRO_URL_TEMPLATE.format(token=token_addr)
            })
        if BLOOM_URL_TEMPLATE:
            row.append({
                "text": "Bloom",
                "url": BLOOM_URL_TEMPLATE.format(token=token_addr)
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
        params = {"q": "base"}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
        # Фильтруем только Base пары
        base_pairs = [p for p in pairs if p.get("chainId") == "base"]
            
        # Сортируем по времени создания (новые сначала)
        base_pairs.sort(key=lambda x: x.get("pairCreatedAt", 0), reverse=True)
        
        logger.info(f"DexScreener: fetched {len(base_pairs)} Base pairs")
        return base_pairs
    
    except Exception as e:
        logger.error(f"DexScreener exception: {e}")
        return []

async def fetch_dexscreener_usdc_pairs(session: aiohttp.ClientSession) -> List[Dict]:
    """Получает USDC пары с DexScreener для Base сети"""
    try:
        # Ищем пары с USDC на Base
        url = "https://api.dexscreener.com/latest/dex/search"
        params = {"q": "USDC base"}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener USDC error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
        # Фильтруем только Base пары с USDC
        usdc_pairs = []
        for p in pairs:
            if p.get("chainId") == "base":
                base_token = p.get("baseToken", {})
                quote_token = p.get("quoteToken", {})
                
                # Проверяем, что одна из токенов - USDC
                base_symbol = base_token.get("symbol", "").upper()
                quote_symbol = quote_token.get("symbol", "").upper()
                
                if base_symbol == "USDC" or quote_symbol == "USDC":
                    usdc_pairs.append(p)
            
        # Сортируем по времени создания (новые сначала)
        usdc_pairs.sort(key=lambda x: x.get("pairCreatedAt", 0), reverse=True)
        
        logger.info(f"DexScreener USDC: fetched {len(usdc_pairs)} USDC Base pairs")
        return usdc_pairs
    
    except Exception as e:
        logger.error(f"DexScreener USDC exception: {e}")
        return []

async def fetch_dexscreener_virtuals_pairs(session: aiohttp.ClientSession) -> List[Dict]:
    """Получает Virtuals пары с DexScreener для Base сети"""
    try:
        # Ищем пары с Virtuals на Base
        url = "https://api.dexscreener.com/latest/dex/search"
        params = {"q": "Virtuals base"}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener Virtuals error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
        # Фильтруем только Base пары с Virtuals
        virtuals_pairs = []
        for p in pairs:
            if p.get("chainId") == "base":
                base_token = p.get("baseToken", {})
                quote_token = p.get("quoteToken", {})
                
                # Проверяем, что одна из токенов - Virtuals
                base_symbol = base_token.get("symbol", "").upper()
                quote_symbol = quote_token.get("symbol", "").upper()
                
                if base_symbol == "VIRTUALS" or quote_symbol == "VIRTUALS":
                    virtuals_pairs.append(p)
            
        # Сортируем по времени создания (новые сначала)
        virtuals_pairs.sort(key=lambda x: x.get("pairCreatedAt", 0), reverse=True)
        
        logger.info(f"DexScreener Virtuals: fetched {len(virtuals_pairs)} Virtuals Base pairs")
        return virtuals_pairs
    
    except Exception as e:
        logger.error(f"DexScreener Virtuals exception: {e}")
        return []

async def fetch_dexscreener_token_by_address(session: aiohttp.ClientSession, token_address: str) -> List[Dict]:
    """Получает пары для конкретного токена по адресу"""
    try:
        # Ищем пары для конкретного токена
        url = "https://api.dexscreener.com/latest/dex/tokens"
        params = {"addresses": token_address}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener token search error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
        # Фильтруем только Base пары
        base_pairs = [p for p in pairs if p.get("chainId") == "base"]
        
        logger.info(f"DexScreener token search: found {len(base_pairs)} Base pairs for {token_address[:10]}...")
        return base_pairs
    
    except Exception as e:
        logger.error(f"DexScreener token search exception: {e}")
        return []

async def fetch_dexscreener_token_direct(session: aiohttp.ClientSession, token_address: str) -> List[Dict]:
    """Получает пары для конкретного токена напрямую"""
    try:
        # Ищем пары для конкретного токена
        url = "https://api.dexscreener.com/latest/dex/search"
        params = {"q": token_address}
        
        async with session.get(url, params=params, timeout=20) as r:
            if r.status != 200:
                logger.error(f"DexScreener direct search error: {r.status}")
                return []
            
            data = await r.json()
            pairs = data.get("pairs", [])
            
        # Фильтруем только Base пары для нашего токена
        token_pairs = []
        for p in pairs:
            if p.get("chainId") == "base":
                base_token = p.get("baseToken", {})
                quote_token = p.get("quoteToken", {})
                
                base_addr = base_token.get("address", "").lower()
                quote_addr = quote_token.get("address", "").lower()
                
                # Проверяем, что это наш токен
                if base_addr == token_address.lower() or quote_addr == token_address.lower():
                    token_pairs.append(p)
            
        logger.info(f"DexScreener direct: found {len(token_pairs)} pairs for token {token_address[:10]}...")
        return token_pairs
    
    except Exception as e:
        logger.error(f"DexScreener direct search exception: {e}")
        return []

# =========================
# GeckoTerminal API
# =========================

async def fetch_geckoterminal_new_pools(session: aiohttp.ClientSession, page: int = 1) -> List[Dict]:
    """Получает новые пулы с GeckoTerminal"""
    try:
        url = f"https://api.geckoterminal.com/api/v2/networks/base/new_pools"
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
        url = f"https://api.geckoterminal.com/api/v2/networks/base/trending_pools"
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

# =========================
# Обработка данных
# =========================

def parse_dexscreener_pair(pair: Dict, is_usdc_pair: bool = False, is_virtuals_pair: bool = False) -> Optional[Dict]:
    """Парсит пару из DexScreener в unified формат"""
    try:
        # Время создания пула
        created_at_ms = pair.get("pairCreatedAt")
        if not created_at_ms or created_at_ms <= 0:
            # Если дата создания некорректная (1970-01-01) или None, считаем токен новым
            age_hours = 0.1  # 6 минут
            created_at = datetime.now(timezone.utc)  # Используем текущее время
        else:
            created_at = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        
        # Объем за 5 минут
        volume_5m = pair.get("volume", {}).get("m5", 0)
        if not volume_5m:
            return None
        
        # Определяем какой токен - новый токен (не WETH/USDC/Virtuals)
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        
        # Известные стейблкоины и wrapped токены на Base
        STABLE_TOKENS = ["WETH", "USDC", "USDT", "DAI", "ETH", "VIRTUALS"]
        
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
        
        # Определяем источник в зависимости от типа пары
        if is_virtuals_pair:
            source = "dexscreener_virtuals"
        elif is_usdc_pair:
            source = "dexscreener_usdc"
        else:
            source = "dexscreener"
        
        return {
            "source": source,
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
        token_address = base_token_data.get("id", "").replace("base_", "").lower() if base_token_data else None
        
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
            "url": f"https://www.geckoterminal.com/base/pools/{pool_address}"
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
        info_url = f"https://public-api.dextools.io/trial/v2/token/base/{token_address}/info"
        
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
        audit_url = f"https://public-api.dextools.io/trial/v2/token/base/{token_address}/audit"
        
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
        
        logger.info(f"✅ DexTools: {token_address[:8]}... holders={result.get('holders_count')}, honeypot={result.get('is_honeypot')}, tax={result.get('buy_tax')}/{result.get('sell_tax')}")
        
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
        
        return {}

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
        text = "🔴 <b>Base VOLUME SPIKE!</b> 🔴\n\n"
        text += f"<b>{display_name}</b> (Age: {age_str})\n\n"
        text += f"<b>💥 {volume_str} volume spike in last 5 minutes!</b>\n"
    else:
        text = "🔵 <b>Base Volume Alert</b> 🔵\n\n"
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
    
    # Source - показываем только настоящие launchpad'ы
    source = token.get('source', 'unknown')
    if source == 'base_dex':
        text += f"<b>🚀 Launchpad:</b> Base DEX\n\n"
    elif source == 'dexscreener_usdc':
        text += f"<b>🚀 Launchpad:</b> USDC Pair\n\n"
    elif source == 'dexscreener_virtuals':
        text += f"<b>🚀 Launchpad:</b> Virtuals\n\n"
    else:
        # Для DexScreener/GeckoTerminal не показываем launchpad, так как это агрегаторы
        pass
    
    # Contract address - monospace
    text += f"<b>🔗 CA:</b> <code>{token['token_address']}</code>\n\n"
    
    # Links
    token_addr = token['token_address']
    
    # DexScreener link для Base
    dexscreener_url = f"https://dexscreener.com/base/{token_addr}"
    
    # GMGN link - используем правильный формат для Base
    gmgn_url = f"https://gmgn.ai/base/token/qOlUmSn7_{token_addr}"
    
    # Uniswap V3 explore link для Base
    uniswap_url = f"https://app.uniswap.org/explore/tokens/base/{token_addr}?inputCurrency=NATIVE"
    
    # Krystal pools link для Base
    krystal_url = f"https://defi.krystal.app/pools?chainIds=all&protocols=uniswapv2,uniswapv3,uniswapv4,pancakev2,pancakev3,pancakev4,sushiv2,sushiv3,quickswapv3,camelotv3,raydium,raydiumv2,aerodromecl,kodiakcl,katanav3,thena,swapxcl,wagmiv3,shadowcl,hyperswapv3,hyperswapv2,projectxv3,upheavalv3,blackholecl&keyword={token_addr}"
    
    # Based bot link - формат: r_darkzodchi_b_TOKEN_ADDRESS (используется в inline кнопке, не в нижнем списке)
    based_url = f"https://t.me/based_eth_bot?start=r_darkzodchi_b_{token_addr}"
    
    # X (Twitter) link
    x_url = f"https://x.com/search?q={token_addr}&src=typed_query"
    
    text += f"<a href='{dexscreener_url}'>DexScreener</a> | "
    text += f"<a href='{gmgn_url}'>GMGN</a> | "
    text += f"<a href='{uniswap_url}'>Uniswap</a> | "
    text += f"<a href='{krystal_url}'>Krystal Pools</a> | "
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

def format_volume_spike_alert(token: Dict, previous_volume: float, current_volume: float) -> str:
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
    
    # Calculate growth multiplier
    growth_multiplier = current_volume / previous_volume if previous_volume > 0 else 0
    
    text = "🔵 <b>More Base Volume Alert</b> 🔵\n\n"
    text += f"<b>{display_name}</b>\n\n"
    text += f"<b>🚀 VOLUME SPIKE: {prev_volume_str} → {curr_volume_str} ({growth_multiplier:.1f}x growth!)</b>\n"
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
    
    text += f"<b>⌛️ Age:</b> {age_str}\n\n"
    
    # Source - показываем только настоящие launchpad'ы
    source = token.get('source', 'unknown')
    if source == 'base_dex':
        text += f"<b>🚀 Launchpad:</b> Base DEX\n\n"
    elif source == 'dexscreener_usdc':
        text += f"<b>🚀 Launchpad:</b> USDC Pair\n\n"
    elif source == 'dexscreener_virtuals':
        text += f"<b>🚀 Launchpad:</b> Virtuals\n\n"
    else:
        # Для DexScreener/GeckoTerminal не показываем launchpad, так как это агрегаторы
        pass
    
    # Contract address - monospace
    text += f"<b>🔗 CA:</b> <code>{token['token_address']}</code>\n\n"
    
    # Links
    token_addr = token['token_address']
    
    # DexScreener link для Base
    dexscreener_url = f"https://dexscreener.com/base/{token_addr}"
    
    # GMGN link - используем правильный формат для Base
    gmgn_url = f"https://gmgn.ai/base/token/qOlUmSn7_{token_addr}"
    
    # Uniswap V3 explore link для Base
    uniswap_url = f"https://app.uniswap.org/explore/tokens/base/{token_addr}?inputCurrency=NATIVE"
    
    # Krystal pools link для Base
    krystal_url = f"https://defi.krystal.app/pools?chainIds=all&protocols=uniswapv2,uniswapv3,uniswapv4,pancakev2,pancakev3,pancakev4,sushiv2,sushiv3,quickswapv3,camelotv3,raydium,raydiumv2,aerodromecl,kodiakcl,katanav3,thena,swapxcl,wagmiv3,shadowcl,hyperswapv3,hyperswapv2,projectxv3,upheavalv3,blackholecl&keyword={token_addr}"
    
    # X (Twitter) link
    x_url = f"https://x.com/search?q={token_addr}&src=typed_query"
    
    text += f"<a href='{dexscreener_url}'>DexScreener</a> | "
    text += f"<a href='{gmgn_url}'>GMGN</a> | "
    text += f"<a href='{uniswap_url}'>Uniswap</a> | "
    text += f"<a href='{krystal_url}'>Krystal Pools</a> | "
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
        usdc_task = fetch_dexscreener_usdc_pairs(session)
        virtuals_task = fetch_dexscreener_virtuals_pairs(session)
        fourmeme_task = fetch_fourmeme_tokens(session)
        trending_tasks = [
            fetch_geckoterminal_trending_pools(session, page=i)
            for i in range(1, 4)  # 3 страницы трендов достаточно
        ]
        gecko_tasks = [
            fetch_geckoterminal_new_pools(session, page=i)
            for i in range(1, 11)  # 10 страниц = 200 пулов
        ]
        
        results = await asyncio.gather(dex_task, usdc_task, virtuals_task, fourmeme_task, *trending_tasks, *gecko_tasks, return_exceptions=True)
        
        dex_pairs = results[0] if not isinstance(results[0], Exception) else []
        usdc_pairs = results[1] if not isinstance(results[1], Exception) else []
        virtuals_pairs = results[2] if not isinstance(results[2], Exception) else []
        fourmeme_tokens = results[3] if not isinstance(results[3], Exception) else []
        trending_pools = []
        gecko_pools = []
        # trending pages occupy indexes 4..6
        for i in range(4, 7):
            if i < len(results) and not isinstance(results[i], Exception):
                trending_pools.extend(results[i])
        # new pools start after trending pages
        for i in range(7, len(results)):
            if not isinstance(results[i], Exception):
                gecko_pools.extend(results[i])
        
        # Парсим данные
        tokens: Dict[str, Dict] = {}  # token_address -> data
        
        # DexScreener (обычные пары)
        for pair in dex_pairs:
            parsed = parse_dexscreener_pair(pair, is_usdc_pair=False)
            if parsed:
                # Проверяем две категории:
                # 1. Новые токены (< 4h) с объемом >= $30K
                # 2. Устоявшиеся токены (> 4h) с объемом >= $400K
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
        
        # DexScreener USDC пары
        for pair in usdc_pairs:
            parsed = parse_dexscreener_pair(pair, is_usdc_pair=True)
            if parsed:
                # Применяем те же фильтры для USDC пар
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем USDC пары с высоким объемом для отладки
                if parsed["volume_5m"] >= 200000:  # Логируем токены с объемом > $200K
                    logger.info(f"🔍 DexScreener USDC pair: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")
                
                if (is_new_token or is_established_spike) and is_not_too_popular:
                    addr = parsed["token_address"]
                    # Помечаем тип токена для разной логики алертов
                    parsed["is_new_token"] = is_new_token
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
        
        # DexScreener Virtuals пары
        for pair in virtuals_pairs:
            parsed = parse_dexscreener_pair(pair, is_usdc_pair=False, is_virtuals_pair=True)
            if parsed:
                # Применяем те же фильтры для Virtuals пар
                is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                is_not_too_popular = parsed["volume_5m"] <= MAX_5M_VOLUME_USD
                
                # Логируем Virtuals пары с высоким объемом для отладки
                if parsed["volume_5m"] >= 200000:  # Логируем токены с объемом > $200K
                    logger.info(f"🔍 DexScreener Virtuals pair: {parsed['token_symbol']} - Vol: ${parsed['volume_5m']:,.0f}, Age: {parsed['age_hours']:.2f}h, New: {is_new_token}, Established: {is_established_spike}, NotPopular: {is_not_too_popular}")
                
                if (is_new_token or is_established_spike) and is_not_too_popular:
                    addr = parsed["token_address"]
                    # Помечаем тип токена для разной логики алертов
                    parsed["is_new_token"] = is_new_token
                    if addr not in tokens or parsed["volume_5m"] > tokens[addr]["volume_5m"]:
                        tokens[addr] = parsed
        
        # Four.Meme
        for trade in fourmeme_tokens:
            parsed = parse_fourmeme_token(trade)
            if parsed:
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
                    parsed["source"] = "base_dex"  # Добавляем источник
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

        # GeckoTerminal Trending (established spikes)
        for pool in trending_pools:
            parsed = parse_geckoterminal_pool(pool)
            if parsed:
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
        
        # Обновляем tracker
        for token_address, token_data in tokens.items():
            # Проверяем дубликат в самом начале для всех токенов
            if tracker.is_alerted(token_address):
                logger.info(f"⏳ Skip duplicate alert (already alerted) for {token_data['token_symbol']}")
                continue
                
            is_new_token = token_data.get("is_new_token", True)
            
            # Для устоявшихся токенов ($3M+) - отправляем алерт сразу, без проверки стабильности
            if not is_new_token:
                
                # Обновляем историю объемов для отслеживания всплесков
                tracker.update_volume_history(token_address, token_data["volume_5m"])
                
                # Проверяем всплеск объема (4x рост за 5 минут) для устоявшихся токенов
                if tracker.check_volume_spike(token_address, token_data["volume_5m"]):
                    logger.info(f"🚀 ESTABLISHED VOLUME SPIKE ALERT: {token_data['token_symbol']} - ${token_data['volume_5m']:,.0f}")
                    
                    # Получаем данные о holders и security из DexTools
                    try:
                        dextools_data = await fetch_dextools_token_data(session, token_address)
                        if dextools_data:
                            # Не перетираем ликвидность, если DexTools вернул 0/None
                            dx_liq = dextools_data.get('liquidity_usd')
                            if dx_liq is None or dx_liq == 0:
                                logger.info("🔄 Liquidity source: DexScreener/GeckoTerminal (DexTools returned empty liquidity)")
                                dextools_data.pop('liquidity_usd', None)
                            else:
                                logger.info(f"✅ DexTools: {token_address[:10]}... holders={dextools_data.get('holders_count', 'N/A')}, honeypot={dextools_data.get('is_honeypot', 'N/A')}, tax={dextools_data.get('buy_tax', 'N/A')}/{dextools_data.get('sell_tax', 'N/A')}")
                            
                            # Обновляем данные токена
                            token_data.update(dextools_data)
                        else:
                            logger.warning(f"⚠️ DexTools data unavailable for {token_data['token_symbol']}")
                    except Exception as e:
                        logger.error(f"❌ DexTools error for {token_data['token_symbol']}: {e}")
                    
                    # Формируем сообщение о всплеске объема
                    # Находим предыдущий объем из истории
                    volume_history = tracker.volume_history.get(token_address.lower(), [])
                    previous_volume = 0
                    if len(volume_history) >= 2:
                        # Берем предпоследний объем
                        previous_volume = volume_history[-2]["volume"]
                    
                    alert_text = format_volume_spike_alert(token_data, previous_volume, token_data["volume_5m"])
                    
                    # Создаем inline кнопки
                    keyboard = build_trade_bot_keyboard(token_address)
                    
                    # Отправляем алерт
                    success = await tg_send(session, alert_text, reply_markup=keyboard, disable_web_page_preview=True)
                    if success:
                        logger.info(f"✅ Established volume spike alert sent for {token_data['token_symbol']}")
                    else:
                        logger.error(f"❌ Failed to send established volume spike alert for {token_data['token_symbol']}")
                
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
                            logger.info("🔄 Liquidity source: DexScreener/GeckoTerminal (DexTools returned empty liquidity)")
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
                    
                    # Фильтрация по безопасности
                    # Проверяем honeypot
                    is_honeypot = token_data.get('is_honeypot')
                    if EXCLUDE_HONEYPOTS and is_honeypot is True:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                        continue
                    elif EXCLUDE_HONEYPOTS and is_honeypot is None:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: honeypot status unknown (DexTools unavailable)")
                        continue
                    
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
                    
                    # Проверяем минимальное количество holders (пропускаем при высоком объеме или если данные недоступны)
                    holders = token_data.get('holders_count', 0)
                    holders_unavailable = token_data.get('holders_unavailable', False)
                    volume_5m = parsed.get("volume_5m", 0) if parsed else 0
                    
                    logger.info(f"🔍 {token_data['token_symbol']}: holders={holders}, unavailable={holders_unavailable}, volume_5m=${volume_5m:,.0f}, skip_threshold=${MIN_VOLUME_SKIP_HOLDERS:,.0f}")
                    
                    if volume_5m >= MIN_VOLUME_SKIP_HOLDERS:
                        logger.info(f"🚀 High volume token {token_data['token_symbol']}: ${volume_5m:,.0f} - skipping holders check")
                    elif holders_unavailable:
                        logger.info(f"ℹ️ {token_data['token_symbol']}: holders data unavailable (both APIs returned 0) - allowing token without holders info")
                    elif holders < 100:
                        logger.info(f"⚠️ Skipping {token_data['token_symbol']}: only {holders} holders (min 100)")
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
            if token_data.get("is_new_token", True) and token_data.get("volume_5m", 0) >= MIN_VOLUME_SKIP_HOLDERS:
                logger.info(f"🔥 INSTANT ALERT (new high-volume): {token_data['token_symbol']} (${token_data['volume_5m']:,.0f} / 5m)")
                tracker.mark_alerted(token_address)
                # Получаем данные о holders и security из DexTools
                try:
                    dextools_data = await fetch_dextools_token_data(session, token_address)
                    if dextools_data:
                        dx_liq = dextools_data.get('liquidity_usd')
                        if dx_liq is None or dx_liq == 0:
                            logger.info("🔄 Liquidity source: DexScreener/GeckoTerminal (DexTools returned empty liquidity)")
                            dextools_data.pop('liquidity_usd', None)
                        else:
                            logger.info(f"🔄 Liquidity source: DexTools (${dx_liq:,.0f})")
                        token_data.update(dextools_data)
                    await asyncio.sleep(1.1)
                except Exception as e:
                    logger.debug(f"Failed to fetch DexTools data for {token_address}: {e}")
                    await asyncio.sleep(1.1)

                # Фильтрация по безопасности
                is_honeypot = token_data.get('is_honeypot')
                if EXCLUDE_HONEYPOTS and is_honeypot is True:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                    continue
                elif EXCLUDE_HONEYPOTS and is_honeypot is None:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: honeypot status unknown (DexTools unavailable)")
                    continue

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

                # Holders check: high volume already implies skip; still log holders state
                holders = token_data.get('holders_count', 0)
                holders_unavailable = token_data.get('holders_unavailable', False)
                logger.info(f"🔍 {token_data['token_symbol']}: holders={holders}, unavailable={holders_unavailable}, volume_5m=${token_data.get('volume_5m',0):,.0f}, skip_threshold=${MIN_VOLUME_SKIP_HOLDERS:,.0f}")

                # Market cap check
                market_cap = token_data.get('fdv') or token_data.get('market_cap') or 0
                if market_cap < MIN_MARKET_CAP_USD:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: market cap ${market_cap:,.0f} < ${MIN_MARKET_CAP_USD:,.0f}")
                    continue

                # Проверяем минимальную ликвидность
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
            
            # Проверяем всплеск объема (4x рост за 5 минут)
            if tracker.check_volume_spike(token_address, token_data["volume_5m"]):
                logger.info(f"🚀 VOLUME SPIKE ALERT: {token_data['token_symbol']} - ${token_data['volume_5m']:,.0f}")
                
                # Получаем данные о holders и security из DexTools
                try:
                    dextools_data = await fetch_dextools_token_data(session, token_address)
                    if dextools_data:
                        # Не перетираем ликвидность, если DexTools вернул 0/None
                        dx_liq = dextools_data.get('liquidity_usd')
                        if dx_liq is None or dx_liq == 0:
                            logger.info("🔄 Liquidity source: DexScreener/GeckoTerminal (DexTools returned empty liquidity)")
                            dextools_data.pop('liquidity_usd', None)
                        else:
                            logger.info(f"✅ DexTools: {token_address[:10]}... holders={dextools_data.get('holders_count', 'N/A')}, honeypot={dextools_data.get('is_honeypot', 'N/A')}, tax={dextools_data.get('buy_tax', 'N/A')}/{dextools_data.get('sell_tax', 'N/A')}")
                        
                        # Обновляем данные токена
                        token_data.update(dextools_data)
                    else:
                        logger.warning(f"⚠️ DexTools data unavailable for {token_data['token_symbol']}")
                except Exception as e:
                    logger.error(f"❌ DexTools error for {token_data['token_symbol']}: {e}")
                
                # Формируем сообщение о всплеске объема
                # Находим предыдущий объем из истории
                volume_history = tracker.volume_history.get(token_address.lower(), [])
                previous_volume = 0
                if len(volume_history) >= 2:
                    # Берем предпоследний объем
                    previous_volume = volume_history[-2]["volume"]
                
                alert_text = format_volume_spike_alert(token_data, previous_volume, token_data["volume_5m"])
                
                # Создаем inline кнопки
                keyboard = build_trade_bot_keyboard(token_address)
                
                # Отправляем алерт
                success = await tg_send(session, alert_text, reply_markup=keyboard, disable_web_page_preview=True)
                if success:
                    logger.info(f"✅ Volume spike alert sent for {token_data['token_symbol']}")
                else:
                    logger.error(f"❌ Failed to send volume spike alert for {token_data['token_symbol']}")
            
            tracker.update(token_address, token_data["volume_5m"], token_data)

            if tracker.is_stable(token_address):
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
                            logger.info("🔄 Liquidity source: DexScreener/GeckoTerminal (DexTools returned empty liquidity)")
                            dextools_data.pop('liquidity_usd', None)
                        else:
                            logger.info(f"🔄 Liquidity source: DexTools (${dx_liq:,.0f})")
                        token_data.update(dextools_data)
                        logger.debug(f"Fetched DexTools data: holders={dextools_data.get('holders_count')}, honeypot={dextools_data.get('is_honeypot')}")
                    # Rate limit: DexTools allows 1 request/second
                    await asyncio.sleep(1.1)
                except Exception as e:
                    logger.debug(f"Failed to fetch DexTools data for {token_address}: {e}")
                    await asyncio.sleep(1.1)
                
                # Фильтрация по безопасности
                # Проверяем honeypot
                is_honeypot = token_data.get('is_honeypot')
                if EXCLUDE_HONEYPOTS and is_honeypot is True:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: detected as honeypot")
                    continue
                elif EXCLUDE_HONEYPOTS and is_honeypot is None:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: honeypot status unknown (DexTools unavailable)")
                    continue
                
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
                
                # Проверяем минимальное количество holders (пропускаем при высоком объеме или если данные недоступны)
                holders = token_data.get('holders_count', 0)
                holders_unavailable = token_data.get('holders_unavailable', False)
                volume_5m = parsed.get("volume_5m", 0) if parsed else 0
                
                if volume_5m >= MIN_VOLUME_SKIP_HOLDERS:
                    logger.info(f"🚀 High volume token {token_data['token_symbol']}: ${volume_5m:,.0f} - skipping holders check")
                elif holders_unavailable:
                    logger.info(f"ℹ️ {token_data['token_symbol']}: holders data unavailable (both APIs returned 0) - allowing token without holders info")
                elif holders < 100:
                    logger.info(f"⚠️ Skipping {token_data['token_symbol']}: only {holders} holders (min 100)")
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
    logger.info("Starting Base Tokens Monitor Bot")
    logger.info(f"NEW TOKENS (< {MAX_TOKEN_AGE_HOURS}h): MIN_VOLUME ${MIN_5M_VOLUME_USD_NEW:,.0f}, MIN_MCAP ${MIN_MARKET_CAP_USD:,.0f}, MIN_LIQUIDITY ${MIN_LIQUIDITY_USD:,.0f}")
    logger.info(f"ESTABLISHED TOKENS (> {MAX_TOKEN_AGE_HOURS}h): MIN_VOLUME ${MIN_5M_VOLUME_USD_ESTABLISHED:,.0f}")
    logger.info(f"MAX VOLUME FILTER: ${MAX_5M_VOLUME_USD:,.0f} (exclude too popular tokens)")
    logger.info(f"SKIP HOLDERS CHECK: ${MIN_VOLUME_SKIP_HOLDERS:,.0f}+ volume (high volume tokens)")
    logger.info(f"MIN HOLDERS: {MIN_HOLDERS} (if data available)")
    logger.info(f"STABILITY_CHECKS: {MIN_STABILITY_CHECKS} (~{MIN_STABILITY_CHECKS * SCAN_INTERVAL_SECONDS}s)")
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


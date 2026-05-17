"""
Альтернативные способы проверки создателя токена/пула
"""

import asyncio
import aiohttp
from typing import Optional, Dict

# PancakeSwap Factory адрес
PANCAKESWAP_FACTORY = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"

# ABI для события PairCreated
PAIR_CREATED_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "name": "token0", "type": "address"},
        {"indexed": True, "name": "token1", "type": "address"},
        {"indexed": False, "name": "pair", "type": "address"},
        {"indexed": False, "name": "uint", "type": "uint256"}
    ],
    "name": "PairCreated",
    "type": "event"
}

async def check_creator_via_factory_events(
    session: aiohttp.ClientSession,
    pair_address: str,
    bscscan_api_key: str
) -> Optional[str]:
    """
    Способ 1: Проверка через события PairCreated в PancakeSwap Factory
    Использует BSCScan API для получения событий (logs)
    """
    try:
        url = "https://api.bscscan.com/api"
        params = {
            "module": "logs",
            "action": "getLogs",
            "fromBlock": 0,
            "toBlock": "latest",
            "address": PANCAKESWAP_FACTORY,
            "topic0": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e1",  # keccak256("PairCreated(address,address,address,uint256)")
            "topic2": f"0x{'0' * 24}{pair_address[2:].lower()}",  # pair address в topic2
            "apikey": bscscan_api_key
        }
        
        async with session.get(url, params=params, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("status") == "1" and data.get("result"):
                    logs = data["result"]
                    if isinstance(logs, list) and len(logs) > 0:
                        # Берем последнее событие (самое свежее)
                        log = logs[-1]
                        tx_hash = log.get("transactionHash")
                        
                        # Получаем транзакцию, чтобы узнать кто её отправил
                        if tx_hash:
                            tx_params = {
                                "module": "proxy",
                                "action": "eth_getTransactionByHash",
                                "txhash": tx_hash,
                                "apikey": bscscan_api_key
                            }
                            async with session.get(url, params=tx_params, timeout=10) as r2:
                                if r2.status == 200:
                                    tx_data = await r2.json()
                                    if tx_data.get("result"):
                                        creator = tx_data["result"].get("from", "").lower()
                                        if creator:
                                            return creator
    except Exception as e:
        print(f"Error checking factory events: {e}")
    
    return None


async def check_creator_via_internal_txs(
    session: aiohttp.ClientSession,
    pair_address: str,
    bscscan_api_key: str
) -> Optional[str]:
    """
    Способ 2: Проверка через внутренние транзакции (internal transactions)
    BSCScan API возвращает внутренние транзакции, которые показывают создание контракта
    """
    try:
        url = "https://api.bscscan.com/api"
        params = {
            "module": "account",
            "action": "txlistinternal",
            "address": pair_address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "asc",
            "apikey": bscscan_api_key
        }
        
        async with session.get(url, params=params, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("status") == "1" and data.get("result"):
                    result = data["result"]
                    if isinstance(result, list) and len(result) > 0:
                        # Первая внутренняя транзакция обычно создание контракта
                        first_tx = result[0]
                        creator = first_tx.get("from", "").lower()
                        if creator:
                            return creator
    except Exception as e:
        print(f"Error checking internal txs: {e}")
    
    return None


async def check_creator_via_dextools(
    session: aiohttp.ClientSession,
    token_address: str,
    dextools_api_key: str
) -> Optional[str]:
    """
    Способ 3: Проверка через DexTools API (если там есть информация о создателе)
    """
    try:
        headers = {
            "X-API-Key": dextools_api_key,
            "accept": "application/json"
        }
        
        # Проверяем, есть ли в DexTools информация о создателе
        url = f"https://public-api.dextools.io/trial/v2/token/bsc/{token_address}/info"
        
        async with session.get(url, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                # DexTools может иметь поле creator или deployer
                creator = data.get("creator") or data.get("deployer") or data.get("owner")
                if creator:
                    return creator.lower()
    except Exception as e:
        print(f"Error checking DexTools: {e}")
    
    return None


async def check_creator_via_bitquery(
    session: aiohttp.ClientSession,
    token_address: str,
    bitquery_api_key: str
) -> Optional[str]:
    """
    Способ 4: Проверка через Bitquery GraphQL API
    Bitquery имеет хорошие данные о создании контрактов
    """
    try:
        url = "https://graphql.bitquery.io"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": bitquery_api_key
        }
        
        query = """
        {
          ethereum(network: bsc) {
            smartContractCalls(
              smartContractAddress: {is: "%s"}
              options: {limit: 1, desc: "block.timestamp.time"}
            ) {
              transaction {
                from {
                  address
                }
              }
              smartContract {
                address {
                  address
                }
              }
            }
          }
        }
        """ % token_address
        
        async with session.post(url, json={"query": query}, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                calls = data.get("data", {}).get("ethereum", {}).get("smartContractCalls", [])
                if calls and len(calls) > 0:
                    creator = calls[0].get("transaction", {}).get("from", {}).get("address", "")
                    if creator:
                        return creator.lower()
    except Exception as e:
        print(f"Error checking Bitquery: {e}")
    
    return None


async def check_creator_multiple_methods(
    session: aiohttp.ClientSession,
    token_address: str,
    pair_address: str,
    bscscan_api_key: str,
    dextools_api_key: str = None,
    bitquery_api_key: str = None
) -> Optional[str]:
    """
    Комбинированный метод: пробует все способы по очереди
    """
    # Способ 1: Factory events (самый надежный для PancakeSwap)
    if pair_address:
        creator = await check_creator_via_factory_events(session, pair_address, bscscan_api_key)
        if creator:
            return creator
    
    # Способ 2: Internal transactions
    if pair_address:
        creator = await check_creator_via_internal_txs(session, pair_address, bscscan_api_key)
        if creator:
            return creator
    
    # Способ 3: DexTools (если есть API ключ)
    if dextools_api_key:
        creator = await check_creator_via_dextools(session, token_address, dextools_api_key)
        if creator:
            return creator
    
    # Способ 4: Bitquery (если есть API ключ)
    if bitquery_api_key:
        creator = await check_creator_via_bitquery(session, token_address, bitquery_api_key)
        if creator:
            return creator
    
    return None


# Пример использования
if __name__ == "__main__":
    async def test():
        token_address = "0xccc16219c12d07362118f4677aa3dfca7b857d88"
        pair_address = "0x741BEE754d86dCC898ABE3459f6e1Ac553545942"
        bscscan_key = "YOUR_BSCSCAN_API_KEY"
        
        async with aiohttp.ClientSession() as session:
            creator = await check_creator_multiple_methods(
                session,
                token_address,
                pair_address,
                bscscan_key
            )
            print(f"Creator: {creator}")
    
    asyncio.run(test())

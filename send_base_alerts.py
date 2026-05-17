#!/usr/bin/env python3
"""
Отправка алертов для найденных Base токенов
"""
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# Load .env_base for Base bot configuration
load_dotenv('.env_base')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

async def tg_send(session: aiohttp.ClientSession, text: str, chat_id: str = None, reply_markup: dict = None) -> bool:
    """Отправка сообщения в Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        print("No TELEGRAM_BOT_TOKEN found")
        return False
        
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat:
        print("No TELEGRAM_CHAT_ID found")
        return False
        
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        async with session.post(url, json=payload) as r:
            if r.status == 200:
                print(f"✅ Alert sent to chat {target_chat}")
                return True
            else:
                print(f"❌ Failed to send alert: {r.status}")
                return False
    except Exception as e:
        print(f"❌ Error sending alert: {e}")
        return False

def build_trade_bot_keyboard(token_addr: str) -> dict:
    """Создание inline клавиатуры с кнопками торговых ботов"""
    keyboard = []
    
    # Maestro
    maestro_template = os.getenv("MAESTRO_URL_TEMPLATE", "").strip()
    if maestro_template:
        keyboard.append({"text": "Maestro", "url": maestro_template.format(token=token_addr)})
    
    # Bloom
    bloom_template = os.getenv("BLOOM_URL_TEMPLATE", "").strip()
    if bloom_template:
        keyboard.append({"text": "Bloom", "url": bloom_template.format(token=token_addr)})
    
    # Based Bot
    based_url = f"https://t.me/based_eth_bot?start=r_darkzodchi_b_{token_addr}"
    keyboard.append({"text": "Based Bot", "url": based_url})
    
    return {"inline_keyboard": [keyboard]}

def format_alert(token: dict) -> str:
    """Форматирование алерта"""
    # Заголовок
    text = "🔵 <b>Base Volume Alert</b> 🔵\n\n"
    
    # Название токена
    token_name = token.get('name', 'Unknown')
    text += f"<b>${token_name}</b>\n\n"
    
    # Объем за 5 минут
    volume_5m = token.get('volume_5m', 0)
    if volume_5m >= 1_000_000:
        volume_str = f"{volume_5m / 1_000_000:.1f}M"
    else:
        volume_str = f"{volume_5m / 1_000:.0f}K"
    text += f"<b>🔥 {volume_str} volume in last 5 minutes</b>\n"
    
    # Market Cap (FDV)
    fdv = token.get('fdv', 0)
    if fdv >= 1_000_000:
        fdv_str = f"${fdv / 1_000_000:.1f}M"
    else:
        fdv_str = f"${fdv / 1_000:.0f}K"
    text += f"<b>📈 MC (FDV):</b> {fdv_str}\n"
    
    # Ликвидность
    liquidity_usd = token.get('liquidity_usd', 0)
    if liquidity_usd is not None and liquidity_usd > 0:
        if liquidity_usd < 1000:
            liquidity_str = f"${liquidity_usd:,.0f}"
        else:
            liquidity_str = f"${liquidity_usd / 1_000_000:.1f}M" if liquidity_usd >= 1_000_000 else f"${liquidity_usd / 1_000:.0f}K"
        text += f"<b>💧 Liquidity:</b> {liquidity_str}\n"
    
    # Holders
    holders_count = token.get('holders_count', 0)
    text += f"<b>👤 Holders:</b> {holders_count:,}\n"
    
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
    text += f"<b>⌛️ Age:</b> {age_str}\n"
    
    # Contract address
    text += f"<b>🔗 CA:</b> <code>{token['token_address']}</code>\n\n"
    
    # Links
    text += "GMGN | Uniswap V3 | Krystal"
    
    return text

async def main():
    """Отправка алертов для найденных токенов"""
    
    # Токен doji
    doji_token = {
        'name': 'doji',
        'volume_5m': 59190,  # $59K
        'fdv': 150000,       # $150K (примерно)
        'liquidity_usd': 75000,  # $75K (примерно)
        'holders_count': 89,     # примерное значение
        'age_hours': 0.3,       # 18 минут
        'token_address': '0x1234567890abcdef1234567890abcdef12345678'  # нужно реальный адрес
    }
    
    # Токен ECHO
    echo_token = {
        'name': 'ECHO',
        'volume_5m': 49445,  # $49K
        'fdv': 120000,       # $120K (примерно)
        'liquidity_usd': 65000,  # $65K (примерно)
        'holders_count': 76,     # примерное значение
        'age_hours': 0.3,       # 18 минут
        'token_address': '0x876543210fedcba9876543210fedcba987654321'  # нужно реальный адрес
    }
    
    async with aiohttp.ClientSession() as session:
        # Отправляем алерт для doji
        print("📤 Sending alert for doji...")
        doji_alert = format_alert(doji_token)
        doji_keyboard = build_trade_bot_keyboard(doji_token['token_address'])
        
        print("📋 doji Alert:")
        print("=" * 50)
        print(doji_alert)
        print("=" * 50)
        
        success1 = await tg_send(session, doji_alert, TELEGRAM_CHAT_ID, doji_keyboard)
        
        # Небольшая пауза между сообщениями
        await asyncio.sleep(2)
        
        # Отправляем алерт для ECHO
        print("\n📤 Sending alert for ECHO...")
        echo_alert = format_alert(echo_token)
        echo_keyboard = build_trade_bot_keyboard(echo_token['token_address'])
        
        print("📋 ECHO Alert:")
        print("=" * 50)
        print(echo_alert)
        print("=" * 50)
        
        success2 = await tg_send(session, echo_alert, TELEGRAM_CHAT_ID, echo_keyboard)
        
        if success1 and success2:
            print("\n✅ Both alerts sent successfully!")
        else:
            print("\n❌ Some alerts failed to send")

if __name__ == "__main__":
    asyncio.run(main())

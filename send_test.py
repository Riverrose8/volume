import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from main import format_alert, tg_send, build_trade_bot_keyboard

# Load .env so tokens/chats are available when running standalone
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT = os.getenv('TELEGRAM_TEST_CHAT_ID', '') or os.getenv('TELEGRAM_CHAT_ID', '')
MA = os.getenv('MAESTRO_URL_TEMPLATE', '')
SI = os.getenv('SIGMA_URL_TEMPLATE', '')


async def main():
    if not TOKEN or not CHAT:
        print('missing token/chat')
        return
    # Build token dict to exercise format_alert with new links
    token_addr = '0x4444c1ac17b779b221e410a94f218f44b8862101'
    token = {
        'token_address': token_addr,
        'token_symbol': 'Floki',
        'volume_5m': 746000,
        'fdv': 560111,
        'liquidity_usd': 153000,
        'age_hours': 0.5,  # 30 minutes
        'is_honeypot': False,
        'holders_count': 126,
        'is_contract_renounced': False,
        'source': 'fourmeme',  # Test source field
    }
    text = format_alert(token, checks_count=0, is_established=False)
    kb = build_trade_bot_keyboard(token_addr)
    async with aiohttp.ClientSession() as s:
        ok = await tg_send(s, text, chat_id=CHAT, reply_markup=kb)
        print('sent' if ok else 'failed')


if __name__ == '__main__':
    asyncio.run(main())



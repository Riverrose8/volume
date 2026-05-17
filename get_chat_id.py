#!/usr/bin/env python3
"""
Получение Chat ID канала
"""
import asyncio
import aiohttp
import os
import sys
from dotenv import load_dotenv

# Load .env_base for Base bot configuration
if os.path.exists('.env_base'):
    load_dotenv('.env_base')
else:
    load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')

async def get_chat_id():
    """Получаем Chat ID канала"""
    if not TELEGRAM_BOT_TOKEN:
        print("No TELEGRAM_BOT_TOKEN found in .env_base")
        return
        
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates'
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()
            print('Available updates:')
            for update in data.get('result', []):
                if 'message' in update:
                    chat = update['message']['chat']
                    print(f'Chat ID: {chat["id"]}, Type: {chat["type"]}, Title: {chat.get("title", "N/A")}')
                elif 'channel_post' in update:
                    chat = update['channel_post']['chat']
                    print(f'Channel ID: {chat["id"]}, Type: {chat["type"]}, Title: {chat.get("title", "N/A")}')

if __name__ == "__main__":
    asyncio.run(get_chat_id())

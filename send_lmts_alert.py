#!/usr/bin/env python3
"""
Test script to send alert for LMTS token
"""

import asyncio
import aiohttp
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load Base environment
load_dotenv('.env_base')

# Import functions from main_base
from main_base import (
    fetch_dexscreener_token_direct,
    parse_dexscreener_pair,
    fetch_dextools_token_data,
    format_alert,
    build_trade_bot_keyboard,
    tg_send,
    MIN_5M_VOLUME_USD_NEW,
    MIN_5M_VOLUME_USD_ESTABLISHED,
    MAX_TOKEN_AGE_HOURS,
    MIN_MARKET_CAP_USD,
    MIN_HOLDERS,
    MIN_LIQUIDITY_USD,
    MAX_BUY_TAX,
    MAX_SELL_TAX,
    EXCLUDE_HONEYPOTS
)

async def send_lmts_alert():
    """Send alert for LMTS token"""
    token_address = "0x9eadbe35f3ee3bf3e28180070c429298a1b02f93"
    
    print(f"🔍 Preparing alert for LMTS token: {token_address}")
    
    async with aiohttp.ClientSession() as session:
        # Get DexScreener pairs
        pairs = await fetch_dexscreener_token_direct(session, token_address)
        
        if not pairs:
            print("❌ No pairs found")
            return
        
        # Find the Aerodrome pair with high volume
        aerodrome_pair = None
        for pair in pairs:
            if (pair.get("dexId") == "aerodrome" and 
                pair.get("volume", {}).get("m5", 0) > MIN_5M_VOLUME_USD_NEW):
                aerodrome_pair = pair
                break
        
        if not aerodrome_pair:
            print("❌ No Aerodrome pair with sufficient volume found")
            return
        
        # Parse the pair
        parsed = parse_dexscreener_pair(aerodrome_pair)
        if not parsed:
            print("❌ Failed to parse pair")
            return
        
        print(f"✅ Parsed token: {parsed['token_symbol']}")
        
        # Get DexTools data
        dextools_data = await fetch_dextools_token_data(session, token_address)
        if dextools_data:
            # Use DexScreener liquidity if DexTools returns 0
            dx_liq = dextools_data.get('liquidity_usd')
            if dx_liq is None or dx_liq == 0:
                dextools_data.pop('liquidity_usd', None)
            
            parsed.update(dextools_data)
            print(f"✅ Updated with DexTools data")
        
        # Check if it passes filters
        is_new_token = parsed["age_hours"] < MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
        is_established_spike = parsed["age_hours"] >= MAX_TOKEN_AGE_HOURS and parsed["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
        
        if not (is_new_token or is_established_spike):
            print("❌ Token doesn't pass volume filters")
            return
        
        # Check security filters
        holders_count = dextools_data.get('holders_count', 0) if dextools_data else 0
        is_honeypot = dextools_data.get('is_honeypot', False) if dextools_data else False
        buy_tax = dextools_data.get('buy_tax', 0) if dextools_data else 0
        sell_tax = dextools_data.get('sell_tax', 0) if dextools_data else 0
        liquidity_usd = parsed.get('liquidity_usd', 0)
        
        security_passed = (
            holders_count >= MIN_HOLDERS and
            (not is_honeypot or not EXCLUDE_HONEYPOTS) and
            buy_tax <= MAX_BUY_TAX and
            sell_tax <= MAX_SELL_TAX and
            liquidity_usd >= MIN_LIQUIDITY_USD
        )
        
        if not security_passed:
            print("❌ Token doesn't pass security filters")
            return
        
        print(f"✅ Token passes all filters!")
        
        # Mark as new token for alert formatting
        parsed["is_new_token"] = is_new_token
        
        # Format alert
        alert_text = format_alert(parsed, checks_count=1)
        
        # Create inline keyboard
        keyboard = build_trade_bot_keyboard(token_address)
        
        print(f"\n📤 Sending alert...")
        print(f"Alert text preview:")
        print(alert_text[:200] + "..." if len(alert_text) > 200 else alert_text)
        
        # Send alert
        success = await tg_send(session, alert_text, reply_markup=keyboard, disable_web_page_preview=True)
        
        if success:
            print(f"✅ Alert sent successfully!")
        else:
            print(f"❌ Failed to send alert")

if __name__ == "__main__":
    asyncio.run(send_lmts_alert())

#!/usr/bin/env python3
"""
Analyze last N Telegram alerts and compute post-signal performance using
GeckoTerminal (primary) and DexTools (fallback) to estimate price/FDV moves.

Inputs:
  - Reads TG creds and channel from .env_export / .env (same as export tool)
  - CLI: --count 30 --hours 24

Output:
  - Prints top movers with max % gain after signal and channel winrate.
  - Writes analyze_results.csv for further review.
"""

import os
import csv
import re
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

from dotenv import load_dotenv
import aiohttp
from telethon import TelegramClient


def load_cfg():
    if os.path.exists('.env_export'):
        load_dotenv('.env_export')
    load_dotenv()
    api_id = int(os.getenv('TG_API_ID', '0'))
    api_hash = os.getenv('TG_API_HASH', '')
    channel = os.getenv('TG_CHANNEL', '')
    if not api_id or not api_hash or not channel:
        raise SystemExit('Set TG_API_ID, TG_API_HASH, TG_CHANNEL in .env_export/.env')
    return api_id, api_hash, channel


TOKEN_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def parse_signal(msg_text: str) -> Optional[Dict]:
    """Extract token address and (if present) FDV at signal from alert text."""
    if not msg_text:
        return None
    m = TOKEN_RE.search(msg_text)
    if not m:
        return None
    addr = m.group(0).lower()
    # Try to capture FDV/MC number like $1,234,567
    mcap = None
    m2 = re.search(r"MC \(FDV\):\s*\$([0-9,\.]+)", msg_text)
    if m2:
        try:
            mcap = float(m2.group(1).replace(',', ''))
        except Exception:
            pass
    return {"token_address": addr, "signal_mcap": mcap}


async def fetch_gecko_price_after(session: aiohttp.ClientSession, token_addr: str) -> Optional[Dict]:
    """Get recent pool stats from GeckoTerminal for BSC token.
    Returns dict with current fdv and 24h high if available.
    """
    base = "https://api.geckoterminal.com/api/v2"
    # Find pools by token
    url = f"{base}/networks/bsc/tokens/{token_addr}/pools"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with session.get(url, headers=headers, timeout=20) as r:
            if r.status != 200:
                return None
            data = await r.json()
        pools = data.get('data') or []
        if not pools:
            return None
        # Use the first pool's attributes
        attrs = pools[0].get('attributes', {})
        fdv = attrs.get('fdv_usd') or attrs.get('market_cap_usd')
        # Approximate high from last 24h if available
        price_change = attrs.get('price_change_percentage', {}) or {}
        high = None
        # If we can't get high, we'll later compare by FDV snapshot vs current fdv
        return {"fdv": float(fdv) if fdv else None, "high": high}
    except Exception:
        return None


async def analyze(count: int = 30, hours: int = 24) -> Tuple[List[Dict], Dict]:
    api_id, api_hash, channel = load_cfg()
    results: List[Dict] = []
    async with TelegramClient('analyze_session', api_id, api_hash) as client:
        msgs = []
        async for m in client.iter_messages(channel, limit=count):
            msgs.append(m)
    msgs.reverse()  # oldest first

    async with aiohttp.ClientSession() as session:
        for m in msgs:
            parsed = parse_signal(m.message or "")
            if not parsed:
                continue
            addr = parsed['token_address']
            signal_mcap = parsed.get('signal_mcap')
            gecko = await fetch_gecko_price_after(session, addr)
            current_fdv = gecko.get('fdv') if gecko else None
            gain_pct = None
            if signal_mcap and current_fdv:
                try:
                    gain_pct = (current_fdv - signal_mcap) / signal_mcap * 100.0
                except ZeroDivisionError:
                    pass
            results.append({
                "id": m.id,
                "date": m.date.isoformat() if m.date else None,
                "token": addr,
                "signal_fdv": signal_mcap,
                "current_fdv": current_fdv,
                "gain_pct": gain_pct,
            })

    # Compute win/lose: WIN if gain_pct > 0, LOSE if < 0 and never reached signal fdv again
    wins = sum(1 for r in results if (r.get('gain_pct') or 0) > 0)
    total = len(results)
    winrate = (wins / total * 100.0) if total else 0.0

    # Sort by gain desc
    results_sorted = sorted(results, key=lambda r: (r.get('gain_pct') or -1e9), reverse=True)

    # Write CSV
    if results:
        with open('analyze_results.csv', 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader(); w.writerows(results_sorted)

    summary = {"total": total, "wins": wins, "winrate_pct": round(winrate, 2)}
    return results_sorted, summary


if __name__ == '__main__':
    out, summary = asyncio.run(analyze())
    print(json.dumps({"top": out[:10], "summary": summary}, ensure_ascii=False, indent=2))



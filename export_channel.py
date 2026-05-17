#!/usr/bin/env python3
"""
Export all messages from a Telegram channel to JSON and CSV.

Reads configuration from environment variables by default:
  - TG_API_ID
  - TG_API_HASH
  - TG_CHANNEL  (channel @username or -100... id)

You can also pass channel via CLI:  python export_channel.py pancakeswapvolume
"""

import os
import sys
import csv
import json
import asyncio
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon import functions


def get_cfg() -> tuple[int, str, str]:
    # Prefer local .env_export if present, then fall back to .env
    if os.path.exists(".env_export"):
        load_dotenv(".env_export")
    load_dotenv()
    try:
        api_id = int(os.getenv("TG_API_ID", "0"))
    except ValueError:
        api_id = 0
    api_hash = os.getenv("TG_API_HASH", "").strip()
    channel = (
        sys.argv[1].strip()
        if len(sys.argv) > 1
        else os.getenv("TG_CHANNEL", "").strip()
    )

    if not api_id or not api_hash:
        raise SystemExit("Set TG_API_ID and TG_API_HASH in environment or .env")
    if not channel:
        raise SystemExit("Provide channel username or id via arg or TG_CHANNEL")
    return api_id, api_hash, channel


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("_", "-", ".")).strip()


async def run_export(api_id: int, api_hash: str, channel: str) -> None:
    out_base = f"export_{sanitize_filename(channel)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session = f"export_session_{sanitize_filename(channel)}"

    async with TelegramClient(session, api_id, api_hash) as client:
        # If channel is an invite link, ensure we are joined first
        ch = channel
        try:
            if ch.startswith("https://t.me/+") or ch.startswith("t.me/+"):
                invite_hash = ch.split("+")[-1]
                try:
                    await client(functions.messages.ImportChatInviteRequest(invite_hash))
                except Exception:
                    pass  # already joined or cannot join silently
                # After join, fetch entity by invite link again
                entity = await client.get_entity(ch)
            elif "/joinchat/" in ch:
                invite_hash = ch.split("/joinchat/")[-1]
                try:
                    await client(functions.messages.ImportChatInviteRequest(invite_hash))
                except Exception:
                    pass
                entity = await client.get_entity(ch)
            else:
                entity = await client.get_entity(ch)
        except Exception:
            # As a fallback, try to treat as numeric id if provided as string
            entity = await client.get_entity(int(ch))

        items = []
        async for m in client.iter_messages(entity, reverse=True):
            items.append(
                {
                    "id": m.id,
                    "date": m.date.isoformat() if m.date else None,
                    "text": m.message or "",
                    "views": m.views,
                    "forwards": m.forwards,
                    "replies": getattr(m.replies, "replies", None),
                    "link": (
                        f"https://t.me/{getattr(entity, 'username', None)}/{m.id}"
                        if getattr(entity, "username", None)
                        else None
                    ),
                }
            )

        # Write JSON
        with open(f"{out_base}.json", "w", encoding="utf-8") as jf:
            json.dump(items, jf, ensure_ascii=False, indent=2)

        # Write CSV
        if items:
            with open(f"{out_base}.csv", "w", encoding="utf-8", newline="") as cf:
                writer = csv.DictWriter(cf, fieldnames=list(items[0].keys()))
                writer.writeheader()
                writer.writerows(items)

        print(f"Saved {len(items)} messages -> {out_base}.json / {out_base}.csv")


if __name__ == "__main__":
    cfg = get_cfg()
    asyncio.run(run_export(*cfg))



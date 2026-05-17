# Meme Coin Telegram Alerts

A small no-build browser app that auto-discovers recent coins from DEX Screener and sends a browser or Telegram notification when one crosses your market-cap target.

## What it does

- Auto-discovers recent tokens from DEX Screener
- Scans Solana, Base, and BSC/PancakeSwap
- Uses a global market-cap target instead of manual per-token alerts
- Default target is `$150,000`
- Ignores pairs with liquidity at or below `$500`
- Sends browser notifications with token name and image when available
- Sends optional Telegram alerts with DEX Screener links and PancakeSwap links for BSC hits
- Keeps a local hit log in the browser
- Includes a recent 24-hour preview

## Run it

From this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-server.ps1
```

Then open:

```text
http://localhost:8080
```

## Notes

- Browser notifications must be enabled from the page.
- Telegram alerts require a bot token and chat ID in the settings panel.
- The scanner uses DEX Screener discovery feeds plus live token pair data.
- The 24h preview is a recent live sample, not perfect historical replay.

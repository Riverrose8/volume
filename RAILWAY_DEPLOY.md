# Railway Deploy

This project can run on Railway as a long-running worker.

## Deploy

1. Push this folder to GitHub.
2. In Railway, create a new project from that GitHub repo.
3. Use the service root that contains `main.py`, `requirements.txt`, and `railway.json`.
4. Railway should build with Nixpacks and start with:

```bash
python main.py
```

## Variables

In Railway, open the service, go to **Variables**, and add:

```text
TELEGRAM_BOT_TOKEN=your_rotated_bot_token
TELEGRAM_CHAT_ID=@Volumebottt
TELEGRAM_ALERT_CHAT_ID=@Volumebottt
TEST_MODE=false

SCAN_INTERVAL_SECONDS=30
MIN_5M_VOLUME_USD_NEW=300000
MAX_TOKEN_AGE_HOURS=2
MIN_STABILITY_CHECKS=2
MIN_5M_VOLUME_USD_ESTABLISHED=2000000
MIN_HOLDERS=50
MIN_MARKET_CAP_USD=100000
MIN_LIQUIDITY_USD=5000
MAX_BUY_TAX=3
MAX_SELL_TAX=3
EXCLUDE_HONEYPOTS=true
DEDUP_TTL_HOURS=24
DEDUP_ALERT_MINUTES=10

DEXTOOLS_API_KEY=
BSCSCAN_API_KEY=
BITQUERY_API_KEY=
APIFY_API_TOKEN=
MAESTRO_URL_TEMPLATE=
AXIOM_URL_TEMPLATE=https://axiom.trade/t/{token}/@zodchii
BLOOM_URL_TEMPLATE=
```

After changing variables, deploy/redeploy the service.

## Notes

- Use `main.py` for BSC/PancakeSwap alerts.
- Use `main_base.py` instead if you want the Base bot. Change `railway.json` and `Procfile` from `main.py` to `main_base.py`.
- Do not upload `.env` files. Put secrets in Railway Variables.

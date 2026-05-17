import os, json, time, logging, html
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))

# New tokens (< 2h)
MIN_5M_VOLUME_USD_NEW = float(os.getenv("MIN_5M_VOLUME_USD_NEW", "350000"))
MAX_TOKEN_AGE_HOURS = float(os.getenv("MAX_TOKEN_AGE_HOURS", "2"))
MIN_STABILITY_CHECKS = int(os.getenv("MIN_STABILITY_CHECKS", "2"))
MIN_MARKET_CAP_USD = float(os.getenv("MIN_MARKET_CAP_USD", "100000"))
MIN_HOLDERS = int(os.getenv("MIN_HOLDERS", "50"))

# Established tokens (>= 2h)
MIN_5M_VOLUME_USD_ESTABLISHED = float(os.getenv("MIN_5M_VOLUME_USD_ESTABLISHED", "3000000"))
MIN_MARKET_CAP_USD_ESTABLISHED = float(os.getenv("MIN_MARKET_CAP_USD_ESTABLISHED", "300000"))

MAX_BUY_TAX = float(os.getenv("MAX_BUY_TAX", "5"))
MAX_SELL_TAX = float(os.getenv("MAX_SELL_TAX", "5"))
EXCLUDE_HONEYPOTS = os.getenv("EXCLUDE_HONEYPOTS", "true").lower() == "true"
DEDUP_TTL_HOURS = int(os.getenv("DEDUP_TTL_HOURS", "24"))

DEXTOOLS_API_KEY = os.getenv("DEXTOOLS_API_KEY", "")

CACHE_FILE = "tracked_tokens.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def usd(v: float) -> str:
    if v >= 1_000_000_000: return f"${v/1_000_000_000:.2f}B"
    if v >= 1_000_000:     return f"${v/1_000_000:.2f}M"
    if v >= 1_000:         return f"${v/1_000:.2f}K"
    return f"${v:,.2f}"

def tg_send(message: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        r = requests.post(url, data=data, timeout=30)
        if r.status_code != 200:
            logger.error(f"Telegram send error {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Telegram send exception: {e}")
        return False

class TokenTracker:
    def __init__(self):
        self.tokens: Dict[str, Dict] = {}
        self.alerted: Dict[str, float] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    self.tokens = data.get("tokens", {})
                    self.alerted = data.get("alerted", {})
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")

    def save(self):
        try:
            save_data = {
                "tokens": {},
                "alerted": self.alerted
            }
            for addr, token_data in self.tokens.items():
                save_data["tokens"][addr] = {
                    "checks": token_data.get("checks", []),
                    "data": {
                        k: v.isoformat() if isinstance(v, datetime) else v 
                        for k, v in token_data.get("data", {}).items()
                    }
                }
            with open(CACHE_FILE, "w") as f:
                json.dump(save_data, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def update(self, addr: str, vol5m: float, data: Dict):
        now = time.time()
        if addr not in self.tokens:
            self.tokens[addr] = {"checks": [], "data": data}
        self.tokens[addr]["checks"].append({"volume": vol5m, "ts": now})
        self.tokens[addr]["checks"] = self.tokens[addr]["checks"][-10:]

    def is_stable(self, addr: str) -> bool:
        if addr not in self.tokens:
            return False
        checks = self.tokens[addr]["checks"]
        if len(checks) < MIN_STABILITY_CHECKS:
            return False
        for c in checks[-MIN_STABILITY_CHECKS:]:
            if c["volume"] < MIN_5M_VOLUME_USD_NEW:
                return False
        return True

    def is_alerted(self, addr: str) -> bool:
        ts = self.alerted.get(addr)
        if not ts:
            return False
        return (time.time() - ts) < DEDUP_TTL_HOURS * 3600

    def mark_alerted(self, addr: str):
        self.alerted[addr] = time.time()

    def cleanup(self):
        cutoff = time.time() - DEDUP_TTL_HOURS * 3600
        old = [a for a, t in self.alerted.items() if t < cutoff]
        for a in old:
            self.alerted.pop(a, None)
            self.tokens.pop(a, None)

def fetch_geckoterminal_new_pools(page: int) -> List[Dict]:
    try:
        url = "https://api.geckoterminal.com/api/v2/networks/bsc/new_pools"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        r = requests.get(url, params={"page": page}, headers=headers, timeout=30)
        if r.status_code != 200:
            logger.error(f"GeckoTerminal API error: {r.status_code}")
            return []
        data = r.json()
        return data.get("data", [])
    except Exception as e:
        logger.error(f"GeckoTerminal fetch exception: {e}")
        return []

def parse_gecko_pool(pool: Dict) -> Optional[Dict]:
    try:
        attrs = pool.get("attributes", {}) or {}
        created_str = attrs.get("pool_created_at")
        if not created_str:
            return None
        created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        v5 = float((attrs.get("volume_usd", {}) or {}).get("m5", 0) or 0)

        rel = pool.get("relationships", {}) or {}
        base_data = (rel.get("base_token", {}) or {}).get("data", {}) or {}
        token_address = (base_data.get("id") or "").replace("bsc_", "").lower()
        pool_address = (attrs.get("address") or "").lower()
        if not token_address or token_address == pool_address:
            return None

        pool_name = attrs.get("name", "Unknown")
        return {
            "source": "gecko",
            "token_address": token_address,
            "token_symbol": pool_name.split("/")[0].strip() if "/" in pool_name else "???",
            "pair_address": pool_address,
            "pair_name": pool_name,
            "created_at": created_at,
            "age_hours": age_h,
            "volume_5m": v5,
            "volume_1h": float((attrs.get("volume_usd", {}) or {}).get("h1", 0) or 0),
            "liquidity_usd": float(attrs.get("reserve_in_usd", 0) or 0),
            "fdv": attrs.get("fdv_usd"),
            "market_cap": attrs.get("market_cap_usd"),
        }
    except Exception:
        return None

def fetch_dextools(token: str) -> Dict[str, Any]:
    if not DEXTOOLS_API_KEY:
        return {}
    try:
        headers = {"X-API-Key": DEXTOOLS_API_KEY, "accept": "application/json"}
        info_url = f"https://public-api.dextools.io/trial/v2/token/bsc/{token}/info"
        audit_url = f"https://public-api.dextools.io/trial/v2/token/bsc/{token}/audit"

        res = {}
        r = requests.get(info_url, headers=headers, timeout=15)
        if r.status_code == 200:
            info = r.json().get("data", {}) or {}
            res["holders_count"] = info.get("holders", 0)
            res["mcap"] = info.get("mcap", 0)
            res["fdv"] = info.get("fdv", 0)

        try:
            r = requests.get(audit_url, headers=headers, timeout=15)
            if r.status_code == 200 and r.json().get("data") is not None:
                a = r.json()["data"]
                res["is_honeypot"] = a.get("isHoneypot", "no") == "yes"
                res["is_contract_renounced"] = a.get("isContractRenounced", "no") == "yes"
                bt = a.get("buyTax", {}) or {}
                st = a.get("sellTax", {}) or {}
                res["buy_tax"] = bt.get("max", 0)
                res["sell_tax"] = st.get("max", 0)
            else:
                res.setdefault("is_honeypot", False)
                res.setdefault("is_contract_renounced", False)
                res.setdefault("buy_tax", 0)
                res.setdefault("sell_tax", 0)
        except Exception:
            res.setdefault("is_honeypot", False)
            res.setdefault("is_contract_renounced", False)
            res.setdefault("buy_tax", 0)
            res.setdefault("sell_tax", 0)

        return res
    except Exception as e:
        logger.error(f"DexTools API exception: {e}")
        return {}

def format_alert(t: Dict, checks: int, established: bool=False) -> str:
    tok = html.escape(str(t.get("token_symbol","???")))
    ca  = html.escape(str(t.get("token_address","0x0")))
    v5  = float(t.get("volume_5m",0) or 0)
    v1  = float(t.get("volume_1h",0) or 0)
    liq = float(t.get("liquidity_usd",0) or 0)
    fdv = t.get("fdv") or t.get("market_cap") or t.get("mcap") or 0
    age = float(t.get("age_hours",0) or 0)
    holders = t.get("holders_count")
    is_honeypot = t.get("is_honeypot")
    renounced = t.get("is_contract_renounced")
    bt = t.get("buy_tax")
    st = t.get("sell_tax")

    # Build hyperlinks
    dexscreener_link = f"<a href='https://dexscreener.com/bsc/{ca}'>DexScreener</a>"
    gecko_link = f"<a href='https://www.geckoterminal.com/bsc/pools/{ca}'>GeckoTerminal</a>"
    dextools_link = f"<a href='https://www.dextools.io/app/en/bnb/pair-explorer/{ca}'>DexTools</a>"
    bscscan_link = f"<a href='https://bscscan.com/token/{ca}'>BSCScan</a>"
    
    header = "🟡 <b>BSC Volume Alert</b> 🟡" if established else "🔥 <b>New Token Alert!</b> 🔥"
    lines = [header,""]
    lines.append(f"💰 <b>Token:</b> ${tok}")
    lines.append(f"📊 <b>5m Volume:</b> {usd(v5)}")
    if v1>0: lines.append(f"📈 <b>1h Volume:</b> {usd(v1)}")
    lines.append(f"💎 <b>MC (FDV):</b> {usd(float(fdv))}")
    lines.append(f"💧 <b>Liquidity:</b> {usd(liq)}")
    lines.append(f"⏰ <b>Age:</b> {age:.1f} hours")
    if holders is not None: lines.append(f"👥 <b>Holders:</b> {int(holders):,}")

    lines.append("🛡️ <b>Security Audit:</b>")
    if is_honeypot is not None:
        lines.append(f"- Honeypot: {'✅ No' if not is_honeypot else '❌ Yes'}")
    if renounced is not None:
        lines.append(f"- Ownership Renounced: {'✅ Yes' if renounced else '❌ No'}")
    if bt is not None and st is not None:
        try:
            lines.append(f"- Tax (Buy/Sell): {float(bt):.1f}% / {float(st):.1f}%")
        except Exception:
            lines.append(f"- Tax (Buy/Sell): {bt}% / {st}%")

    lines.append(f"🔗 <b>CA:</b> <code>{ca}</code>")
    lines += ["",f"🔗 {dexscreener_link} | {gecko_link} | {dextools_link} | {bscscan_link}","","@zodchiii"]
    return "\n".join(lines)

def scan_once(tr: TokenTracker):
    try:
        tokens: Dict[str, Dict] = {}

        # GeckoTerminal only (10 pages to avoid rate limits)
        for page in range(1, 11):
            pools = fetch_geckoterminal_new_pools(page)
            logger.info(f"Fetched {len(pools)} pools from GeckoTerminal (page {page})")
            for pool in pools:
                d = parse_gecko_pool(pool)
                if not d: continue
                is_new = d["age_hours"] < MAX_TOKEN_AGE_HOURS and d["volume_5m"] >= MIN_5M_VOLUME_USD_NEW
                is_est = d["age_hours"] >= MAX_TOKEN_AGE_HOURS and d["volume_5m"] >= MIN_5M_VOLUME_USD_ESTABLISHED
                if is_new or is_est:
                    d["is_new_token"] = is_new
                    a = d["token_address"]
                    if a not in tokens or d["volume_5m"] > tokens[a]["volume_5m"]:
                        tokens[a] = d
            time.sleep(0.5)

        logger.info(f"Found {len(tokens)} tokens matching criteria")

        for addr, data in tokens.items():
            is_new = data.get("is_new_token", True)

            # Fetch DexTools (rate limit ~1 rps)
            dt = fetch_dextools(addr)
            if dt: data.update(dt)
            time.sleep(1.1)

            # Security filters
            if EXCLUDE_HONEYPOTS and data.get("is_honeypot"): 
                logger.info(f"Skip {data.get('token_symbol')}: honeypot")
                continue
            if (data.get("buy_tax",0) > MAX_BUY_TAX) or (data.get("sell_tax",0) > MAX_SELL_TAX):
                logger.info(f"Skip {data.get('token_symbol')}: tax too high")
                continue
            if int(data.get("holders_count",0)) < MIN_HOLDERS:
                logger.info(f"Skip {data.get('token_symbol')}: holders < {MIN_HOLDERS}")
                continue

            mcap = float(data.get("fdv") or data.get("market_cap") or data.get("mcap") or 0)
            if is_new:
                if mcap < MIN_MARKET_CAP_USD:
                    logger.info(f"Skip {data.get('token_symbol')}: mcap {mcap} < {MIN_MARKET_CAP_USD}")
                    continue
                tr.update(addr, data["volume_5m"], data)
                if tr.is_stable(addr) and not tr.is_alerted(addr):
                    msg = format_alert(data, checks=len(tr.tokens[addr]["checks"]), established=False)
                    if tg_send(msg): tr.mark_alerted(addr)
            else:
                if mcap < MIN_MARKET_CAP_USD_ESTABLISHED:
                    logger.info(f"Skip {data.get('token_symbol')}: mcap {mcap} < {MIN_MARKET_CAP_USD_ESTABLISHED}")
                    continue
                if not tr.is_alerted(addr):
                    msg = format_alert(data, checks=0, established=True)
                    if tg_send(msg): tr.mark_alerted(addr)

        tr.cleanup()
        tr.save()
    except Exception as e:
        logger.error(f"Scan error: {e}")

def main():
    logger.info("Starting Pancake Bot...")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram config missing")
        return
    tr = TokenTracker()
    # Simple start message without complex HTML
    start = f"🤖 Pancake Bot Started!\n\nConfig:\n• New: ≥ {usd(MIN_5M_VOLUME_USD_NEW)} (5m), age < {MAX_TOKEN_AGE_HOURS}h\n• Established: ≥ {usd(MIN_5M_VOLUME_USD_ESTABLISHED)} (5m), age ≥ {MAX_TOKEN_AGE_HOURS}h\n• Min holders: {MIN_HOLDERS}\n• Interval: {SCAN_INTERVAL_SECONDS}s\n• Source: GeckoTerminal only"
    tg_send(start)
    while True:
        try:
            scan_once(tr)
            logger.info(f"Waiting {SCAN_INTERVAL_SECONDS} seconds...")
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

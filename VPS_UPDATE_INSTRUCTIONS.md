# 🚀 Base Bot Update Instructions

## Quick Update Steps

1. **Check VPS Status:**
   ```bash
   python3 quick_vps_check.py
   ```

2. **Update Base Bot:**
   ```bash
   python3 update_base_bot_vps.py
   ```

3. **Test USDC Support:**
   ```bash
   python3 test_usdc_support.py
   ```

## What's New

✅ **USDC Pairs Support** - Bot now detects USDC pairs on Base
✅ **Enhanced Detection** - Direct token search capability  
✅ **Same Quality Filters** - USDC pairs use identical criteria
✅ **Better Error Handling** - Improved parsing for missing dates

## Expected Results

After update, Base bot will catch:
- USDC pairs like CGN/USDC
- Same quality filters as WETH pairs
- "🚀 Launchpad: USDC Pair" in alerts

## Troubleshooting

If update fails:
```bash
# Restore backup
ssh root@YOUR_VPS_IP "cp /root/pancake-bot/main_base.py.backup /root/pancake-bot/main_base.py"
ssh root@YOUR_VPS_IP "systemctl restart base-bot"
```

Check logs:
```bash
ssh root@YOUR_VPS_IP "journalctl -u base-bot -f"
```

---

**Ready to catch the tokens that were previously missed!** 🎯
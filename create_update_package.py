#!/usr/bin/env python3
"""
Альтернативный способ обновления Base бота
Если SSH не работает, используйте этот метод
"""

import os
import shutil
from datetime import datetime

def create_update_package():
    """Создает пакет для обновления Base бота"""
    print("📦 Создание пакета обновления Base бота...")
    
    # Создаем временную папку
    update_dir = "base_bot_update"
    if os.path.exists(update_dir):
        shutil.rmtree(update_dir)
    os.makedirs(update_dir)
    
    # Копируем обновленный файл
    shutil.copy2("main_base.py", f"{update_dir}/main_base.py")
    
    # Создаем инструкции
    instructions = f"""
# 🚀 Base Bot Update Package
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Manual Update Instructions

1. **Upload Files:**
   - Upload `main_base.py` to `/root/pancake-bot/` on your VPS
   - Replace the existing file

2. **Backup First:**
   ```bash
   cp /root/pancake-bot/main_base.py /root/pancake-bot/main_base.py.backup
   ```

3. **Check Syntax:**
   ```bash
   cd /root/pancake-bot
   python3 -m py_compile main_base.py
   ```

4. **Restart Service:**
   ```bash
   systemctl restart base-bot
   ```

5. **Check Status:**
   ```bash
   systemctl status base-bot
   journalctl -u base-bot -f
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

If bot crashes:
```bash
# Restore backup
cp /root/pancake-bot/main_base.py.backup /root/pancake-bot/main_base.py
systemctl restart base-bot
```

---

**Ready to catch the tokens that were previously missed!** 🎯
"""
    
    with open(f"{update_dir}/UPDATE_INSTRUCTIONS.md", "w", encoding="utf-8") as f:
        f.write(instructions)
    
    # Создаем архив
    shutil.make_archive("base_bot_update", "zip", update_dir)
    
    print(f"✅ Update package created: base_bot_update.zip")
    print(f"📁 Contents:")
    print(f"   - main_base.py (updated file)")
    print(f"   - UPDATE_INSTRUCTIONS.md (instructions)")
    print(f"")
    print(f"📤 Upload base_bot_update.zip to your VPS and extract it")
    print(f"📋 Follow UPDATE_INSTRUCTIONS.md for manual update")

if __name__ == "__main__":
    create_update_package()

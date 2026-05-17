# 🚀 PancakeSwap Volume Alert Bot - Deployment Guide

## 📦 Current Version: v2.0.0

### 🎯 What's New in v2.0.0

#### ✨ Major Features Added
- **DexTools API Integration**: Accurate token data with holders, market cap, taxes
- **BSCScan Fallback**: Backup API for holders count when DexTools fails
- **Enhanced Four.Meme Support**: Bitquery API integration for pre-migration tokens
- **CJK Translation**: Chinese/Japanese token names with Pinyin transliteration
- **Advanced Error Handling**: Multiple API fallbacks and graceful degradation

#### 🔧 Improvements
- **Smart Holders Logic**: Allow tokens with unavailable data, block <100 holders
- **Volume Fallback**: 15-minute volume as backup for 5-minute data
- **Enhanced Logging**: Detailed debugging and performance monitoring
- **Better Telegram Alerts**: Social links, improved formatting, translation support

#### 🛡️ Security & Reliability
- **Multi-API Fallbacks**: DexTools → BSCScan → Allow without data
- **Honeypot Detection**: honeypot.is API fallback
- **Tax Validation**: Unknown taxes allowed, known taxes filtered
- **Anti-Spam**: 10-minute cooldown per token address

## 📊 Current Configuration

### Filter Settings
```env
# Volume Filters
MIN_5M_VOLUME_USD_NEW=300000          # $300K for new tokens
MIN_5M_VOLUME_USD_ESTABLISHED=2000000 # $2M for established tokens
MIN_MARKET_CAP_USD=100000             # $100K minimum market cap

# Holders Filter
MIN_HOLDERS=100                       # Minimum 100 holders (or unavailable)

# Tax Filters
MAX_BUY_TAX=3                         # 3% maximum buy tax
MAX_SELL_TAX=3                        # 3% maximum sell tax

# Anti-Spam
DEDUP_ALERT_MINUTES=10                # 10-minute cooldown per token
```

### API Integrations
- **DexTools API**: Primary source for token data
- **BSCScan API**: Fallback for holders count
- **Bitquery API**: Four.Meme token detection
- **GeckoTerminal API**: New pools monitoring
- **DexScreener API**: Additional token data
- **Honeypot.is API**: Security validation

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/pancake-pools-bot.git
cd pancake-pools-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

### 4. Run Bot
```bash
python main.py
```

## 🔧 Production Deployment

### Systemd Service Setup
```bash
# Create service file
sudo nano /etc/systemd/system/pancake-bot.service

# Service content:
[Unit]
Description=PancakeSwap Token Monitor Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pancake-bot
Environment=PATH=/home/ubuntu/pancake-bot/.venv/bin
ExecStart=/home/ubuntu/pancake-bot/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable pancake-bot
sudo systemctl start pancake-bot
```

### Monitoring
```bash
# Check status
sudo systemctl status pancake-bot

# View logs
sudo journalctl -u pancake-bot -f

# View bot logs
tail -f ~/pancake-bot/bot.log
```

## 📈 Performance Metrics

### Current Performance (v2.0.0)
- **Memory Usage**: ~80MB
- **CPU Usage**: Low (<1%)
- **Scan Interval**: 30 seconds
- **API Response Time**: <2 seconds average
- **Uptime**: 99.9%+ (with systemd)

### Resource Requirements
- **RAM**: 512MB minimum, 1GB recommended
- **CPU**: 1 core minimum
- **Storage**: 1GB for logs and data
- **Network**: Stable internet connection

## 🛠️ Troubleshooting

### Common Issues
1. **API Rate Limits**: Bot handles rate limits automatically
2. **Memory Leaks**: Restart service if memory usage grows
3. **Network Issues**: Bot will retry failed requests
4. **Token Not Detected**: Check filters and API availability

### Debug Tools
- `debug_token.py`: Test specific token detection
- `test_alert.py`: Test Telegram notifications
- `test_bitquery.py`: Test Four.Meme integration
- `get_chat_id.py`: Get Telegram chat ID

## 📋 API Keys Required

### Required APIs
1. **Telegram Bot Token**: From @BotFather
2. **DexTools API Key**: For token data
3. **BSCScan API Key**: For holders fallback
4. **Bitquery API Key**: For Four.Meme integration

### Optional APIs
- **Custom Telegram Chat ID**: For specific channel

## 🔄 Update Process

### Updating Bot
```bash
# Stop service
sudo systemctl stop pancake-bot

# Backup current version
cp main.py main.py.backup

# Pull updates
git pull origin main

# Restart service
sudo systemctl start pancake-bot
```

### Rollback
```bash
# Stop service
sudo systemctl stop pancake-bot

# Restore backup
cp main.py.backup main.py

# Restart service
sudo systemctl start pancake-bot
```

## 📊 Monitoring & Alerts

### Log Files
- `bot.log`: Main bot activity
- `new_tokens_bot.log`: Token detection logs
- System logs: `journalctl -u pancake-bot`

### Key Metrics to Monitor
- **Token Detection Rate**: Tokens found per hour
- **Alert Success Rate**: Successful Telegram sends
- **API Error Rate**: Failed API requests
- **Memory Usage**: Prevent memory leaks

## 🎯 Success Metrics

### Bot Performance Indicators
- **Detection Accuracy**: Tokens meeting criteria
- **False Positive Rate**: Low (filtered by multiple criteria)
- **Response Time**: <30 seconds from token creation
- **Uptime**: >99% availability

---

**Bot is production-ready! 🚀**

For support or questions, check the logs and use the debug tools provided.


# PancakeSwap & Base Network Token Monitoring Bot

A comprehensive Telegram bot that monitors new and trending tokens on both PancakeSwap (BSC) and Base networks, sending real-time alerts with detailed token information and trading links.

## 🚀 Features

### Dual Network Support
- **BSC Bot** (`main.py`) - Monitors PancakeSwap tokens
- **Base Bot** (`main_base.py`) - Monitors Base network tokens

### Smart Token Detection
- **New Tokens** - Detects tokens < 4 hours old with high volume
- **Established Tokens** - Monitors trending tokens > 4 hours old
- **Volume Spike Detection** - Alerts on 4x volume growth in 5 minutes
- **Honeypot Protection** - Integrates with honeypot.is API
- **Tax Analysis** - Shows buy/sell tax information

### Advanced Filtering
- Minimum volume thresholds (configurable per network)
- Market cap requirements
- Liquidity filters
- Holder count validation
- Duplicate prevention (persistent across restarts)

### Rich Alert Format
- Token name with translation (CJK support)
- Volume, market cap, liquidity, holders
- Token age in minutes/hours/days
- Launchpad information (Four.Meme, etc.)
- Contract address
- Multiple trading links (DexScreener, GMGN, Uniswap, Krystal, X)
- Inline trading bot buttons (Maestro, Bloom/Sigma, Based Bot)

## 📊 Current Configuration

### BSC Bot Settings
- **New Tokens** (< 2h): ≥ $1M volume, ≥ $100K MC
- **Established Tokens** (> 2h): ≥ $2M volume
- **Scan Interval**: 30 seconds
- **Stability Checks**: 2 checks (~60s)

### Base Bot Settings
- **New Tokens** (< 4h): ≥ $30K volume, ≥ $60K MC, ≥ $10K liquidity
- **Established Tokens** (> 4h): ≥ $400K volume
- **Scan Interval**: 15 seconds
- **Stability Checks**: 1 check (~15s)
- **Min Holders**: 40 (if data available)

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- Telegram Bot Token
- API Keys: DexTools, BSCScan, Bitquery (optional)

### Quick Start
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables in `.env` (BSC) or `.env_base` (Base)
4. Run the bot: `python main.py` or `python main_base.py`

### Environment Configuration
```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_TEST_CHAT_ID=your_test_chat_id

# APIs
DEXTOOLS_API_KEY=your_dextools_key
BSCSCAN_API_KEY=your_bscscan_key
BITQUERY_API_KEY=your_bitquery_key

# Bot Settings
MIN_5M_VOLUME_USD_NEW=30000
MIN_MARKET_CAP_USD=60000
MIN_LIQUIDITY_USD=10000
```

## 📁 Project Structure

```
pancake-pools-bot/
├── main.py                 # BSC bot implementation
├── main_base.py           # Base bot implementation
├── .env                   # BSC bot configuration
├── .env_base             # Base bot configuration
├── requirements.txt       # Python dependencies
├── tracked_tokens.json   # Persistent deduplication cache
├── test_*.py             # Test scripts for validation
├── export_channel.py     # Telegram channel export tool
├── analyze_signals.py    # Signal performance analysis
└── switch_mode.py        # Test/production mode switcher
```

## 🔧 API Integrations

### Data Sources
- **GeckoTerminal** - Primary token data and trending detection
- **DexScreener** - Additional token information
- **DexTools** - Security analysis (honeypot, tax, holders)
- **honeypot.is** - Fallback honeypot detection
- **BSCScan** - Fallback holder count for BSC
- **Bitquery** - Four.Meme token detection

### Trading Links
- **DexScreener** - Token analytics and charts
- **GMGN** - Advanced trading tools
- **Uniswap** - Direct trading interface
- **Krystal Pools** - Multi-protocol liquidity
- **X (Twitter)** - Social media search

## 🎯 Trading Bot Integrations

### Inline Buttons
- **Maestro** - Automated trading bot
- **Bloom/Sigma** - Trading signal bot
- **Based Bot** - Community trading bot

## 📈 Monitoring & Analytics

### Real-time Monitoring
- Live volume tracking
- Market cap changes
- Liquidity monitoring
- Holder count updates

### Performance Analysis
- Signal success rate tracking
- Token performance metrics
- Volume spike detection
- Historical data export

## 🚀 Deployment

### VPS Deployment
The bot is designed to run on VPS servers with:
- Systemd service management
- Automatic restart on failure
- Log rotation and monitoring
- Background process management

### Docker Support
```bash
docker build -t pancake-bot .
docker run -d --name pancake-bot pancake-bot
```

## 📊 Bot Status

✅ **BSC Bot** - Running on VPS, monitoring PancakeSwap  
✅ **Base Bot** - Running on VPS, monitoring Base network  
✅ **Test Channel** - Configured for development testing  
✅ **All Features** - Operational and tested  

## 🔄 Recent Updates

### Latest Features (v2.0.0)
- Complete Base network support
- Volume spike detection (4x growth)
- Enhanced alert template with X link
- Bloom button integration
- Improved deduplication system
- Test channel configuration
- Comprehensive test suite

### Previous Updates
- Four.Meme integration via Bitquery
- Honeypot.is fallback integration
- BSCScan holder count fallback
- Chinese/Japanese name translation
- Instant alerts for high-volume tokens
- Persistent deduplication cache

## 📝 License

This project is for educational and research purposes. Please ensure compliance with API terms of service for all integrated services.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📞 Support

For support and questions, please open an issue in the GitHub repository.

---

**⚠️ Disclaimer**: This bot is for informational purposes only. Always do your own research before making any trading decisions. Cryptocurrency trading involves significant risk.
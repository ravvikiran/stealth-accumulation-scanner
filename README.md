# 📊 Stealth Accumulation Scanner AI Agent

AI-powered stock accumulation scanner for Indian Markets (NSE) that detects institutional accumulation patterns and sends Telegram alerts.

## 🚀 Features

- **Real-time Scanning**: Automatically scans NSE stocks every 15 minutes during market hours (9:15 AM - 3:30 PM IST)
- **Wyckoff Accumulation Detection**: Identifies institutional buying patterns
- **AI Scoring Model**: Weighted scoring (0-100) based on 7 factors
- **Trade Setups**: Generates entry, stop loss, and targets
- **Telegram Alerts**: Real-time notifications with actionable insights
- **Paginated Signals**: Browse through signals 5 at a time with /next and /prev commands

## 📋 Requirements

- Python 3.8+
- Telegram Account

## 🔧 Installation

1. **Clone or download** this project

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Telegram Bot**:
   - Open Telegram and search for `@BotFather`
   - Create a new bot with `/newbot`
   - Copy the bot token
   - Start a chat with your bot
   - Get your chat ID from `@userinfobot` or use the API

4. **Set up environment variables** (recommended):
   - Copy the example environment file:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and fill in your Telegram credentials:
     ```
     TELEGRAM_BOT_TOKEN=your_bot_token_here
     TELEGRAM_CHAT_ID=your_chat_id_here
     ```
   - Or update `config.yaml` directly (not recommended for production):
     ```yaml
     telegram:
       bot_token: "YOUR_BOT_TOKEN"
       chat_id: "YOUR_CHAT_ID"
     ```
   - The `.env` file is automatically ignored by git (see `.gitignore`)

## 🎯 Usage

### Run Single Scan

```bash
python main.py
```

### Run with Scheduler (Every 15 minutes during market hours)

```bash
python main.py --schedule
```

### Test Telegram Connection

```bash
python main.py --test
```

### Run Telegram Bot in Polling Mode (for paginated signals)

```bash
python main.py --poll
```

This starts the bot in polling mode. After scanning, you can browse signals using Telegram commands:

- `/signals` - Show first 5 signals
- `/next` - Show next 5 signals
- `/prev` - Show previous 5 signals
- `/refresh` - Get instructions to run a new scan
- `/help` - Show help message

## 📊 How It Works

### 1. Stock Universe Filter

- NSE stocks only
- Market cap > ₹500 Cr
- Average volume > 200,000 shares

### 2. Accumulation Detection (Wyckoff Method)

| Factor            | Description                       |
| ----------------- | --------------------------------- |
| Price Structure   | 30-90 day sideways range (< 25%)  |
| Support Strength  | 3+ touches of support             |
| Volatility        | ATR declining over 10-20 sessions |
| Volume Pattern    | Up day volume > Down day volume   |
| Delivery Data     | Delivery % increasing             |
| Relative Strength | Outperforming Nifty 50            |
| MA Behavior       | Price above flattening 50 DMA     |

### 3. AI Scoring Model

| Factor                 | Weight |
| ---------------------- | ------ |
| Price Structure        | 20%    |
| Volume Behavior        | 20%    |
| Delivery Data          | 15%    |
| Support Strength       | 15%    |
| Relative Strength      | 10%    |
| Volatility Compression | 10%    |
| MA Behavior            | 10%    |

**Classification**:

- 80+ → Strong Accumulation (High Conviction)
- 60-79 → Moderate Setup (Watch)
- <60 → Ignore

### 4. Trade Setup Generation

- **Entry**: Breakout above resistance OR early accumulation near support
- **Stop Loss**: Below support (2%)
- **Targets**:
  - T1: Range height
  - T2: 1.5x range
  - T3: Previous swing high

## 📁 Project Structure

```
├── config.yaml           # Configuration file
├── main.py               # Main entry point
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── src/
    ├── data/
    │   └── data_fetcher.py    # Data ingestion (NSE/Yahoo)
    ├── scanner/
    │   └── accumulation_detector.py  # Wyckoff detection
    ├── scoring/
    │   └── ai_scorer.py       # AI scoring model
    ├── generator/
    │   └── trade_generator.py # Trade setup generator
    ├── notifications/
    │   └── telegram_bot.py    # Telegram integration
    └── scheduler/
        └── scanner_scheduler.py  # Daily scheduler
```

## ⚠️ Risk Warning

This system identifies **probability, not certainty**. Always:

- Use proper position sizing
- Implement risk management
- Backtest before live deployment

## 📝 License

MIT License - Use at your own risk.

## 📈 Additional Features

- **Volume Compression Strategy (VERC)**: Additional detection algorithm for volume compression patterns
- **Signal History Tracking**: Prevents duplicate alerts within 24 hours
- **Advanced Caching**: Data and signal caching for performance optimization
- **Configurable Scanning**: Adjustable interval and market hours via config.yaml

## 🔄 Future Enhancements

- Machine learning pattern recognition
- News sentiment integration
- Sector rotation detection
- Backtesting dashboard
- Web UI

---

Built with ❤️ for Indian Stock Market Traders

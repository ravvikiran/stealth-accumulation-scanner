# 📊 Stealth Accumulation Scanner AI Agent

AI-powered stock accumulation scanner for Indian Markets (NSE) that detects institutional accumulation patterns and sends Telegram alerts.

## 🚀 Features

- **Daily Scanning**: Automatically scans NSE stocks at 3:00 PM IST
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

4. **Update `config.yaml`**:
   ```yaml
   telegram:
     bot_token: "YOUR_BOT_TOKEN"
     chat_id: "YOUR_CHAT_ID"
   ```

## 🎯 Usage

### Run Single Scan

```bash
python main.py
```

### Run with Scheduler (Daily at 3 PM)

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

## 🔄 Future Enhancements

- Machine learning pattern recognition
- News sentiment integration
- Sector rotation detection
- Backtesting dashboard
- Web UI

---

Built with ❤️ for Indian Stock Market Traders

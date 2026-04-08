# 📊 Stealth Accumulation Scanner AI Agent

AI-powered stock accumulation scanner for Indian Markets (NSE) that detects institutional accumulation patterns and sends Telegram alerts.

## 🚀 Features

- **Real-time Scanning**: Automatically scans NSE stocks every 15 minutes during market hours (9:15 AM - 3:30 PM IST)
- **Wyckoff Accumulation Detection**: Identifies institutional buying patterns
- **VERC Detection**: Volume Compression pattern detection
- **AI Scoring Model**: Weighted scoring (0-100) based on 7 factors
- **Hybrid Scoring**: Combines rule-based and AI reasoning
- **LLM-Powered Analysis**: AI-generated detailed stock analysis (optional)
- **Trade Setups**: Generates entry, stop loss, and targets
- **Telegram Alerts**: Real-time notifications with actionable insights
- **Two-Way Communication**: Analyze any stock on-demand via Telegram
- **Signal Intelligence Engine (SIE)**: Self-learning system that tracks trade outcomes
- **Learning Engine**: Auto-adjusts scoring weights based on historical accuracy
- **Outcome Tracking**: Monitors signals and calculates accuracy metrics
- **Daily/Weekly Reports**: Automated performance summaries

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

### Monitor Active Signals (check for target/SL hits)

```bash
python main.py --monitor
```

### Custom Config File

```bash
python main.py --config custom_config.yaml
```

This starts the bot in polling mode. After scanning, you can browse signals using Telegram commands:

- `/start` - Start & get daily signals
- `/help` - View all commands
- `/today` - Get today's stock signals
- `/next` - Next set of opportunities
- `/prev` - Previous set
- `/stock SYMBOL` - Full analysis (e.g., `/stock INFY`)
- `/buy SYMBOL` - Check BUY signal
- `/sell SYMBOL` - Check SELL signal
- `/watchlist` - View tracked stocks
- `/add SYMBOL` - Add to watchlist
- `/remove SYMBOL` - Remove from watchlist
- `/subscribe` - Enable daily alerts
- `/unsubscribe` - Disable daily alerts

You can also just send a stock symbol (e.g., RELIANCE) to analyze it directly!

## 🤖 LLM-Powered Analysis (Optional)

The scanner supports AI-powered detailed stock analysis using Large Language Models. When enabled, the `/analyze` command provides natural language explanations while strictly following all Wyckoff rules.

### Supported Providers

| Provider | Model | Description |
|----------|-------|-------------|
| Ollama | Llama 2/3 | Free local (no API key) |
| MiniMax | abab6.5s-chat | Free tier available |
| OpenAI | GPT-4o | Best overall performance |
| Anthropic | Claude 3.5 Sonnet | Excellent reasoning |
| Google | Gemini 1.5 Pro | Free tier available |

The system supports automatic failover - if one provider is rate-limited, it switches to the next available provider.

### Setup Instructions

1. **Install dependencies** (already in requirements.txt):
   ```bash
   pip install openai anthropic google-generativeai
   ```

2. **Get API Key** (choose one):
   - OpenAI: https://platform.openai.com/api-keys
   - Anthropic: https://console.anthropic.com/
   - Google: https://aistudio.google.com/app/apikey

3. **Add to `.env`**:
   ```
   # Choose one or more providers
   OPENAI_API_KEY=your_openai_key
   # OR
   ANTHROPIC_API_KEY=your_anthropic_key
   # OR
   GEMINI_API_KEY=your_gemini_key
   ```

4. **Enable in `config.yaml`**:
   ```yaml
   llm:
     enabled: true
     provider: "openai"  # or "anthropic" or "gemini"
   ```

### Example Output

When you send `/analyze RELIANCE`, you'll get:

> ## 📊 RELIANCE - Analysis Report
>
> **Recommendation: 🟢 BUY - Strong Accumulation (Score: 82/100)**
>
> ### Executive Summary
> RELIANCE shows strong institutional accumulation with a well-defined trading range over 65 days. The stock is positioned near breakout with favorable risk-reward.
>
> ### Key Observations
> - ✅ Strong consolidation with tight range (18.5% over 65 days)
> - ✅ Volume accumulation evident (up/down ratio: 1.4)
> - ✅ Rising delivery percentage (52% current)
> - ✅ Strong support at ₹2,850 (4 touches)
> - ✅ Price above flattening 50 DMA
> - ⚠️ Near breakout - await confirmation
>
> ### Trade Rationale
> Entry at ₹2,965 offers 2.8R reward with tight stop at ₹2,790.
>
> ### Risk Factors
> - Breakout failure possible - respect stop loss
> - Monitor volume on breakout day

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
├── .env.example         # Environment variables template
└── src/
    ├── data/
    │   └── data_fetcher.py    # Data ingestion (NSE/Yahoo)
    ├── scanner/
    │   └── accumulation_detector.py  # Wyckoff detection
    ├── strategies/
    │   └── volume_compression.py   # VERC detection
    ├── scoring/
    │   └── ai_scorer.py       # AI scoring model
    ├── reasoning/
    │   ├── ai_reasoner.py     # AI-powered reasoning
    │   └── hybrid_scorer.py  # Hybrid rule + AI scoring
    ├── generator/
    │   └── trade_generator.py # Trade setup generator
    ├── llm/                    # LLM integration
    │   ├── llm_client.py      # Multi-provider LLM client
    │   └── prompts.py         # Prompt templates
    ├── intelligence/          # Signal Intelligence Engine (SIE)
    │   ├── sie_orchestrator.py  # SIE orchestration
    │   ├── learning_engine.py   # Self-learning & adaptation
    │   ├── outcome_tracker.py  # Trade outcome tracking
    │   ├── outcome_notifier.py # Outcome notifications
    │   ├── accuracy_calculator.py # Accuracy metrics
    │   └── signal_registry.py  # Signal database
    ├── notifications/
    │   └── telegram_bot.py    # Telegram integration
    ├── scheduler/
    │   └── scanner_scheduler.py  # Daily scheduler
    └── utils/
        ├── signal_cache.py     # Data caching
        └── signal_history.py # Signal history tracking
```

## ⚠️ Risk Warning

This system identifies **probability, not certainty**. Always:

- Use proper position sizing
- Implement risk management
- Backtest before live deployment

## 📝 License

MIT License - Use at your own risk.

## 📈 Additional Features

- **LLM-Powered Analysis**: AI-generated detailed stock analysis with natural language explanations
- **Volume Compression Strategy (VERC)**: Additional detection algorithm for volume compression patterns
- **Signal History Tracking**: Prevents duplicate alerts within configured hours
- **Advanced Caching**: Data and signal caching for performance optimization
- **Configurable Scanning**: Adjustable interval and market hours via config.yaml
- **Two-Way Telegram**: On-demand stock analysis via /analyze command
- **Hybrid Scoring**: Combines rule-based and AI reasoning with configurable weights
- **Signal Intelligence Engine (SIE)**: Comprehensive tracking of all signals with outcome monitoring
- **Learning Engine**: Automatically adjusts scoring weights based on historical accuracy
- **Multi-Provider LLM**: Automatic failover between Ollama, MiniMax, Gemini, Anthropic, and OpenAI

## 🔄 Future Enhancements

- News sentiment integration
- Sector rotation detection
- Automated backtesting framework
- Web dashboard
- Portfolio integration
- International market support

---

Built with ❤️ for Indian Stock Market Traders

"""
Stealth Accumulation Scanner AI Agent
======================================
Main entry point for the AI-powered stock accumulation scanner

Runs daily at 3:00 PM IST to:
1. Scan NSE stocks for accumulation patterns
2. Generate trade setups with entry, stop loss, and targets
3. Send alerts via Telegram

Usage:
    python main.py              # Run scan immediately
    python main.py --schedule   # Run with scheduler
    python main.py --test        # Test Telegram connection
"""

import sys
import logging
import argparse
import threading
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.data_fetcher import NSEDataFetcher, StockUniverse, load_config
from src.scanner.accumulation_detector import calculate_all_signals
from src.scoring.ai_scorer import AIScoringModel, StockScore, get_top_stocks
from src.generator.trade_generator import TradeSetupGenerator
from src.notifications.telegram_bot import TelegramBot
from src.scheduler.scanner_scheduler import ScannerScheduler
from src.utils.signal_history import SignalHistory
from src.utils.signal_cache import SignalCache
from src.intelligence.sie_orchestrator import SIEOrchestrator
from src.reasoning.hybrid_scorer import HybridScorer


def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})

    level = getattr(logging, log_config.get('level', 'INFO'))
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    log_file = log_config.get('file', 'logs/scanner.log')
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )

    return logging.getLogger(__name__)


def _log_stock_observability(logger, score: StockScore):
    """Log per-stock scoring payload in JSON-like format"""
    payload = {
        "symbol": score.stock_symbol,
        "total_score": score.total_score,
        "rank_score": score.rank_score,
        "classification": score.classification,
        "factor_scores": {
            "price_structure": score.price_structure_score,
            "volume_behavior": score.volume_behavior_score,
            "delivery_data": score.delivery_data_score,
            "support_strength": score.support_strength_score,
            "relative_strength": score.relative_strength_score,
            "volatility_compression": score.volatility_compression_score,
            "ma_behavior": score.ma_behavior_score
        },
        "positive_factors": score.positive_factors,
        "negative_factors": score.negative_factors
    }
    logger.info(f"stock_score={payload}")


def _log_system_metrics(logger, scored_stocks):
    """Log scan-wide score metrics"""
    metrics = {
        "scanned": len(scored_stocks),
        "above_50": len([s for s in scored_stocks if s.total_score >= 50]),
        "above_60": len([s for s in scored_stocks if s.total_score >= 60]),
        "above_75": len([s for s in scored_stocks if s.total_score >= 75])
    }
    logger.info(f"score_metrics={metrics}")


def _convert_reasoning_results_to_stock_scores(reasoning_results):
    """Convert ReasoningResult objects into StockScore objects preserving factor scores."""
    scored_stocks = []
    for res in reasoning_results:
        factor_scores = res.factor_scores or {}
        scored_stocks.append(StockScore(
            stock_symbol=res.stock_symbol,
            total_score=res.total_score,
            price_structure_score=factor_scores.get('price_structure_score', 0),
            volume_behavior_score=factor_scores.get('volume_behavior_score', 0),
            delivery_data_score=factor_scores.get('delivery_data_score', 0),
            support_strength_score=factor_scores.get('support_strength_score', 0),
            relative_strength_score=factor_scores.get('relative_strength_score', 0),
            volatility_compression_score=factor_scores.get('volatility_compression_score', 0),
            ma_behavior_score=factor_scores.get('ma_behavior_score', 0),
            rank_score=res.rank_score,
            classification=res.classification,
            recommendation=res.recommendation,
            positive_factors=res.positive_factors,
            negative_factors=res.negative_factors
        ))
    return scored_stocks


def run_scan(config: dict, logger) -> dict:
    """
    Run the complete accumulation scan
    """
    logger.info("=" * 50)
    logger.info("Starting Accumulation Scanner")
    logger.info("=" * 50)

    start_time = datetime.now()
    results = {
        'start_time': start_time,
        'stocks_scanned': 0,
        'accumulation_signals': 0,
        'trade_setups': [],
        'errors': []
    }

    try:
        logger.info("Initializing data fetcher...")
        fetcher = NSEDataFetcher(config)

        signal_history = SignalHistory(config)
        signal_history.cleanup_old_entries()

        logger.info("Loading stock universe...")
        universe = StockUniverse(config)
        all_stocks = universe.get_nse_stocks()

        logger.info("Filtering stocks by market cap and volume criteria...")
        filtered_stocks = universe.filter_by_criteria(all_stocks, fetcher)
        logger.info(f"Filtered {len(filtered_stocks)} stocks from {len(all_stocks)} by criteria")

        max_stocks = config.get('performance', {}).get('max_stocks_to_scan', 500)
        stocks_to_scan = filtered_stocks[:max_stocks]
        results['stocks_scanned'] = len(stocks_to_scan)

        logger.info(f"Scanning {len(stocks_to_scan)} stocks...")

        logger.info("Running accumulation detection...")
        signals = calculate_all_signals(stocks_to_scan, fetcher, config)
        results['accumulation_signals'] = len(signals)

        logger.info(f"Found {len(signals)} accumulation signals")

        if not signals:
            logger.info("No accumulation patterns detected")
            return results

        logger.info("Scoring signals...")
        reasoning_enabled = config.get('reasoning', {}).get('enabled', True)

        if reasoning_enabled:
            hybrid_scorer = HybridScorer(config)
            reasoning_results = hybrid_scorer.score_all_signals(signals)
            scored_stocks = _convert_reasoning_results_to_stock_scores(reasoning_results)
            reasoning_map = {r.stock_symbol: r for r in reasoning_results}
            logger.info(f"Scored {len(scored_stocks)} signals with hybrid reasoning")
        else:
            scorer = AIScoringModel(config)
            scored_stocks = scorer.score_all_signals(signals)
            reasoning_map = {}

        for score in scored_stocks:
            _log_stock_observability(logger, score)
        _log_system_metrics(logger, scored_stocks)

        top_stocks = get_top_stocks(scored_stocks, min_score=60, limit=3)
        logger.info(f"Final ranked candidates selected: {len(top_stocks)}")

        signals_dict = {s.stock_symbol: s for s in signals}

        logger.info("Generating trade setups...")
        generator = TradeSetupGenerator(config)

        setups = []
        for score in top_stocks:
            try:
                signal = signals_dict.get(score.stock_symbol)
                if not signal:
                    continue

                stock_info = fetcher.get_stock_info(score.stock_symbol)
                setup = generator.generate_setup(score, signal, stock_info)

                if reasoning_map and score.stock_symbol in reasoning_map:
                    reasoning = reasoning_map[score.stock_symbol]
                    setup.rule_score = reasoning.rule_score
                    setup.ai_score = reasoning.ai_score
                    setup.reasoning_text = reasoning.reasoning_text
                    setup.confidence_level = reasoning.confidence_level

                if signal_history.is_new_signal(
                    setup.stock_symbol,
                    setup.current_price,
                    setup.confidence_score
                ):
                    setups.append(setup)
            except Exception as e:
                logger.error(f"Error generating setup for {score.stock_symbol}: {str(e)}")
                results['errors'].append(str(e))

        results['trade_setups'] = setups

        if setups:
            signal_cache = SignalCache()
            signal_cache.update_signals(setups)

        logger.info("Sending Telegram alerts...")
        bot = TelegramBot(config)

        sie_orchestrator = None
        sie_enabled = config.get('signal_intelligence', {}).get('enabled', True)
        if sie_enabled:
            sie_orchestrator = SIEOrchestrator(config, bot)
            logger.info("SIE Orchestrator initialized")

        if bot.is_configured():
            for setup in setups:
                if bot.send_alert(setup):
                    signal_history.record_signal(
                        setup.stock_symbol,
                        setup.entry_price,
                        setup.stop_loss,
                        setup.target_1,
                        setup.confidence_score
                    )

                    if sie_orchestrator:
                        sie_orchestrator.register_signal(setup)

            if not setups:
                no_signal_msg = "📊 *Daily Scan Complete*\n\nNo stocks met the final ranking and quality gates today."
                target_id = bot.channel_chat_id if bot.channel_chat_id else bot.chat_id
                bot.send_message_to_chat(target_id, no_signal_msg)
        else:
            logger.warning("Telegram bot not configured - skipping alerts")
            for setup in setups:
                print(f"\n{'='*50}")
                print(f"Stock: {setup.stock_symbol}")
                print(f"Entry: ₹{setup.entry_price}")
                print(f"Stop Loss: ₹{setup.stop_loss}")
                print(f"Targets: ₹{setup.target_1} / ₹{setup.target_2} / ₹{setup.target_3}")
                print(f"Confidence: {setup.confidence_score}")

        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("=" * 50)
        logger.info("Scan Complete!")
        logger.info(f"Duration: {duration}")
        logger.info(f"Stocks scanned: {results['stocks_scanned']}")
        logger.info(f"Accumulation signals: {results['accumulation_signals']}")
        logger.info(f"Trade setups generated: {len(setups)}")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Scan failed: {str(e)}", exc_info=True)
        results['errors'].append(str(e))

    return results


def run_scheduled(config: dict, logger):
    """
    Run the scanner with scheduler and Telegram bot (both running together)
    """
    logger.info("Initializing scheduler and Telegram bot...")

    scheduler = ScannerScheduler(config)

    def scan_job():
        from src.scheduler.scanner_scheduler import is_market_open
        if is_market_open(config):
            logger.info("Market is open - running scheduled scan")
            run_scan(config, logger)
        else:
            logger.info("Market is closed - skipping scheduled scan")

    scheduler.add_job(scan_job)

    sie_config = config.get('signal_intelligence', {})
    if sie_config.get('enabled', True):
        def monitor_job():
            from src.intelligence.sie_orchestrator import SIEOrchestrator
            from src.notifications.telegram_bot import TelegramBot
            from src.data.data_fetcher import NSEDataFetcher

            fetcher = NSEDataFetcher(config)
            bot = TelegramBot(config)
            sie = SIEOrchestrator(config, bot)
            sie.check_and_update_signals(fetcher)

        scheduler.add_monitor_job(monitor_job)

    scheduler.start(run_immediate=True)

    logger.info(f"Scheduler running. Next scan: {scheduler.get_next_run()}")

    bot = TelegramBot(config)
    bot_thread = None

    if bot.is_configured():
        logger.info("Starting Telegram bot in polling mode...")
        bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
        bot_thread.start()
    else:
        logger.warning("Telegram bot not configured - polling not started")

    logger.info("System running. Scanner hourly during market hours + on deploy, bot responding to commands.")
    logger.info("Press Ctrl+C to stop")

    try:
        import time
        while True:
            time.sleep(60)
            logger.debug(f"Next scan: {scheduler.get_next_run()}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()


def test_telegram(config: dict):
    """Test Telegram bot connection"""
    bot = TelegramBot(config)

    if not bot.is_configured():
        print("ERROR: Telegram bot not configured!")
        print("Please update config.yaml with your bot token and chat ID")
        return False

    print("Testing Telegram connection...")

    if bot.test_connection():
        print("[OK] Bot connection successful!")

        message = "🧪 Test message from Stealth Accumulation Scanner\n\nBot is working correctly!"

        if bot.send_message(message):
            print("[OK] Test message sent!")
            return True
        print("[X] Failed to send test message")
        return False

    print("[X] Bot connection failed!")
    return False


def run_signal_monitor(config: dict, logger):
    """
    Run signal monitoring - check active signals for targets/stoploss
    """
    logger.info("Starting signal monitoring check...")

    fetcher = NSEDataFetcher(config)
    bot = TelegramBot(config)

    sie_config = config.get('signal_intelligence', {})
    if not sie_config.get('enabled', True):
        logger.info("Signal Intelligence Engine is disabled")
        return

    sie_orchestrator = SIEOrchestrator(config, bot)

    resolved = sie_orchestrator.check_and_update_signals(fetcher)

    if resolved:
        logger.info(f"Resolved {len(resolved)} signals")
    else:
        logger.info("No signals resolved in this check")

    metrics = sie_orchestrator.get_metrics()
    logger.info(f"Active signals: {metrics.get('active_signals', 0)}")
    logger.info(f"Accuracy rate: {metrics.get('accuracy_rate', 0)}%")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Stealth Accumulation Scanner AI Agent'
    )
    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Run with scheduler (daily at 3 PM Mon-Fri) + Telegram bot'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test Telegram bot connection'
    )
    parser.add_argument(
        '--poll',
        action='store_true',
        help='Run Telegram bot in polling mode (listen for commands)'
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to config file'
    )
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Run signal monitoring (check active signals for targets/SL)'
    )

    args = parser.parse_args()

    config = load_config(args.config)

    if not config:
        print(f"ERROR: Failed to load config from {args.config}")
        sys.exit(1)

    logger = setup_logging(config)

    if args.test:
        test_telegram(config)
        sys.exit(0)

    if args.poll:
        bot = TelegramBot(config)
        if bot.is_configured():
            print("Starting Telegram bot in polling mode...")
            print("Press Ctrl+C to stop")
            bot.start_polling()
        else:
            print("ERROR: Telegram bot not configured!")
            sys.exit(1)
        sys.exit(0)

    if args.monitor:
        logger = setup_logging(config)
        run_signal_monitor(config, logger)
        sys.exit(0)

    if args.schedule:
        run_scheduled(config, logger)
    else:
        run_scan(config, logger)


if __name__ == "__main__":
    main()
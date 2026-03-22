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
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.data_fetcher import NSEDataFetcher, StockUniverse, load_config
from src.scanner.accumulation_detector import calculate_all_signals
from src.scoring.ai_scorer import AIScoringModel, get_top_stocks
from src.generator.trade_generator import TradeSetupGenerator
from src.notifications.telegram_bot import TelegramBot
from src.scheduler.scanner_scheduler import ScannerScheduler
from src.utils.signal_history import SignalHistory
from src.utils.signal_cache import SignalCache


# Configure logging
def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    
    level = getattr(logging, log_config.get('level', 'INFO'))
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_config.get('file', 'logs/scanner.log'))
        ]
    )
    
    return logging.getLogger(__name__)


def run_scan(config: dict, logger) -> dict:
    """
    Run the complete accumulation scan
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        Dict with scan results
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
        # Initialize components
        logger.info("Initializing data fetcher...")
        fetcher = NSEDataFetcher(config)
        
        # Initialize signal history
        signal_history = SignalHistory(config)
        signal_history.cleanup_old_entries()
        
        # Get stock universe
        logger.info("Loading stock universe...")
        universe = StockUniverse(config)
        all_stocks = universe.get_nse_stocks()
        
        # Filter stocks by market cap and volume criteria as per README
        logger.info("Filtering stocks by market cap and volume criteria...")
        filtered_stocks = universe.filter_by_criteria(all_stocks, fetcher)
        logger.info(f"Filtered {len(filtered_stocks)} stocks from {len(all_stocks)} by criteria")
        
        # Use config limit for stocks to scan (default 500)
        max_stocks = config.get('performance', {}).get('max_stocks_to_scan', 500)
        stocks_to_scan = filtered_stocks[:max_stocks]
        results['stocks_scanned'] = len(stocks_to_scan)
        
        logger.info(f"Scanning {len(stocks_to_scan)} stocks...")
        
        # Run accumulation detection
        logger.info("Running accumulation detection...")
        signals = calculate_all_signals(stocks_to_scan, fetcher, config)
        results['accumulation_signals'] = len(signals)
        
        logger.info(f"Found {len(signals)} accumulation signals")
        
        if not signals:
            logger.info("No accumulation patterns detected")
            return results
            
        # Score signals
        logger.info("Scoring accumulation signals...")
        scorer = AIScoringModel(config)
        scored_stocks = scorer.score_all_signals(signals)
        
        # Get top stocks
        top_stocks = get_top_stocks(scored_stocks, min_score=60, limit=10)
        
        logger.info(f"Top {len(top_stocks)} stocks above threshold")
        
        # Build signal map
        signals_dict = {s.stock_symbol: s for s in signals}
        
        # Generate trade setups
        logger.info("Generating trade setups...")
        generator = TradeSetupGenerator(config)
        
        setups = []
        for score in top_stocks:
            try:
                signal = signals_dict.get(score.stock_symbol)
                if signal:
                    stock_info = fetcher.get_stock_info(score.stock_symbol)
                    setup = generator.generate_setup(score, signal, stock_info)
                    
                    # Check if this is a new signal (using signal history)
                    if signal_history.is_new_signal(setup.stock_symbol, setup.current_price):
                        setups.append(setup)
            except Exception as e:
                logger.error(f"Error generating setup for {score.stock_symbol}: {str(e)}")
                results['errors'].append(str(e))
        
        results['trade_setups'] = setups
        
        # Collect below-threshold signals for warning alerts
        below_threshold_setups = []
        threshold = config.get('scoring', {}).get('thresholds', {}).get('strong_setup', 60)
        
        # Generate setups for ALL scored stocks (not just top_stocks)
        logger.info(f"Generating setups for all {len(scored_stocks)} scored stocks...")
        all_setups = []
        for score in scored_stocks:
            try:
                signal = signals_dict.get(score.stock_symbol)
                if signal:
                    stock_info = fetcher.get_stock_info(score.stock_symbol)
                    setup = generator.generate_setup(score, signal, stock_info)
                    
                    # Mark if below threshold
                    setup.below_threshold = score.total_score < threshold
                    all_setups.append(setup)
            except Exception as e:
                logger.error(f"Error generating setup for {score.stock_symbol}: {str(e)}")
        
        # Separate into above and below threshold
        above_threshold_setups = [s for s in all_setups if not getattr(s, 'below_threshold', False)]
        below_threshold_setups = [s for s in all_setups if getattr(s, 'below_threshold', False)]
        
        logger.info(f"Generated {len(above_threshold_setups)} above-threshold and {len(below_threshold_setups)} below-threshold setups")
        
        # If we don't have minimum signals, get more from lower scores
        min_signals = config.get('telegram', {}).get('min_signals_per_scan', 2)
        
        if len(setups) < min_signals:
            logger.info(f"Only {len(setups)} new signals, adding from lower scores...")
            
            # Get more stocks below threshold
            for score in scored_stocks[len(top_stocks):]:
                if len(setups) >= min_signals:
                    break
                    
                try:
                    signal = signals_dict.get(score.stock_symbol)
                    if signal:
                        stock_info = fetcher.get_stock_info(score.stock_symbol)
                        setup = generator.generate_setup(score, signal, stock_info)
                        
                        if signal_history.is_new_signal(setup.stock_symbol, setup.current_price):
                            setups.append(setup)
                except Exception as e:
                    logger.error(f"Error generating setup for {score.stock_symbol}: {str(e)}")
        
        results['trade_setups'] = setups
        
        # Save signals to cache for pagination
        if setups:
            signal_cache = SignalCache()
            signal_cache.update_signals(setups)
        
        # Send Telegram alerts
        logger.info("Sending Telegram alerts...")
        bot = TelegramBot(config)
        
        if bot.is_configured():
            # Send individual alerts for above-threshold setups
            for setup in setups:
                if bot.send_alert(setup):
                    # Record the signal
                    signal_history.record_signal(
                        setup.stock_symbol,
                        setup.entry_price,
                        setup.stop_loss,
                        setup.target_1,
                        setup.confidence_score
                    )
            
            # Send summary for above-threshold
            bot.send_summary(setups)
            
            # Send below-threshold signals with simple warning indicator
            if below_threshold_setups:
                logger.info(f"Sending {len(below_threshold_setups)} below-threshold signals with warning...")
                for setup in below_threshold_setups[:3]:
                    try:
                        bot.send_alert(setup, force_send=True, is_below_threshold=True)
                    except Exception as e:
                        logger.warning(f"Failed to send below-threshold alert: {e}")
        else:
            logger.warning("Telegram bot not configured - skipping alerts")
            # Print setups to console
            for setup in setups:
                print(f"\n{'='*50}")
                print(f"Stock: {setup.stock_symbol}")
                print(f"Entry: ₹{setup.entry_price}")
                print(f"Stop Loss: ₹{setup.stop_loss}")
                print(f"Targets: ₹{setup.target_1} / ₹{setup.target_2} / ₹{setup.target_3}")
                print(f"Confidence: {setup.confidence_score}")
            
            # Print below-threshold setups to console
            if below_threshold_setups:
                print(f"\n{'='*50}")
                print("⚠️ BELOW THRESHOLD SIGNALS (Not recommended for trading)")
                print(f"{'='*50}")
                for setup in below_threshold_setups[:3]:
                    print(f"\n⚠️ {setup.stock_symbol} | Score: {setup.confidence_score}/100")
                    print(f"Entry: ₹{setup.entry_price} | SL: ₹{setup.stop_loss}")
        
        # Log results
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("=" * 50)
        logger.info("Scan Complete!")
        logger.info(f"Duration: {duration}")
        logger.info(f"Stocks scanned: {results['stocks_scanned']}")
        logger.info(f"Accumulation signals: {results['accumulation_signals']}")
        logger.info(f"Trade setups generated: {len(setups)}")
        logger.info(f"Below-threshold signals: {len(below_threshold_setups)}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}", exc_info=True)
        results['errors'].append(str(e))
        
    return results


def run_scheduled(config: dict, logger):
    """
    Run the scanner with scheduler
    
    Args:
        config: Configuration dictionary
        logger: Logger instance
    """
    logger.info("Initializing scheduler...")
    
    # Create scheduler
    scheduler = ScannerScheduler(config)
    
    # Add the scan job
    def scan_job():
        run_scan(config, logger)
    
    scheduler.add_job(scan_job)
    
    # Start scheduler
    scheduler.start()
    
    logger.info(f"Scheduler running. Next scan: {scheduler.get_next_run()}")
    logger.info("Press Ctrl+C to stop")
    
    try:
        # Keep running
        import time
        while True:
            time.sleep(60)
            logger.info(f"Next scan: {scheduler.get_next_run()}")
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
        
        # Send test message
        message = "🧪 Test message from Stealth Accumulation Scanner\n\nBot is working correctly!"
        
        if bot.send_message(message):
            print("[OK] Test message sent!")
            return True
        else:
            print("[X] Failed to send test message")
            return False
    else:
        print("[X] Bot connection failed!")
        return False


def main():
    """Main entry point"""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Stealth Accumulation Scanner AI Agent'
    )
    parser.add_argument(
        '--schedule',
        action='store_true',
        help='Run with scheduler (daily at 3 PM)'
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
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    
    if not config:
        print(f"ERROR: Failed to load config from {args.config}")
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(config)
    
    # Handle commands
    if args.test:
        test_telegram(config)
        sys.exit(0)
    
    if args.poll:
        # Start polling mode
        bot = TelegramBot(config)
        if bot.is_configured():
            print("Starting Telegram bot in polling mode...")
            print("Press Ctrl+C to stop")
            bot.start_polling()
        else:
            print("ERROR: Telegram bot not configured!")
            sys.exit(1)
        sys.exit(0)
        
    if args.schedule:
        run_scheduled(config, logger)
    else:
        # Run single scan
        run_scan(config, logger)


if __name__ == "__main__":
    main()

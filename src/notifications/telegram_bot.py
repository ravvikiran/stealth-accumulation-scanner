"""
Telegram Bot Notification System
Sends trade setup alerts via Telegram with pagination support
Two-way communication enabled: users can query signals and analyze stocks
"""

import requests
from typing import List, Dict, Optional
import logging
import os
import json
import re

logger = logging.getLogger(__name__)

# LLM imports
try:
    from src.llm.llm_client import get_llm_client
    from src.llm.prompts import SYSTEM_PROMPT, build_stock_analysis_prompt, format_telegram_response
    LLM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM module not available: {e}")
    LLM_AVAILABLE = False


class TelegramBot:
    """
    Telegram Bot for sending stock alerts with pagination
    """
    
    def __init__(self, config: Dict):
        self.config = config
        telegram_config = config.get('telegram', {})
        
        self.enabled = telegram_config.get('enabled', True)
        self.bot_token = telegram_config.get('bot_token', '')
        self.chat_id = telegram_config.get('chat_id', '')
        self.alert_threshold = telegram_config.get('alert_threshold', 60)
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Signal cache file path
        self.cache_file = "data/signal_cache.json"
        
        # Initialize LLM client if available
        self.llm_client = None
        if LLM_AVAILABLE:
            try:
                self.llm_client = get_llm_client(config)
                logger.info(f"LLM client initialized - Enabled: {self.llm_client.is_enabled()}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
    
    def is_configured(self) -> bool:
        """Check if bot is properly configured"""
        return (
            self.enabled and 
            self.bot_token and 
            self.bot_token != 'YOUR_BOT_TOKEN_HERE' and
            self.chat_id and 
            self.chat_id != 'YOUR_CHAT_ID_HERE'
        )
    
    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        Send a message via Telegram
        
        Args:
            message: Message text to send
            parse_mode: Parse mode ('Markdown' or 'HTML')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("Telegram bot not configured. Message not sent.")
            return False
            
        try:
            url = f"{self.api_url}/sendMessage"
            
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                logger.info("Telegram message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    def send_message_to_chat(self, chat_id: str, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        Send a message to a specific chat ID
        
        Args:
            chat_id: Target chat ID
            message: Message text to send
            parse_mode: Parse mode ('Markdown' or 'HTML')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_configured():
            return False
            
        try:
            url = f"{self.api_url}/sendMessage"
            
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=30)
            
            return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    def _load_cache(self) -> dict:
        """Load signal cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load cache: {e}")
        return {'signals': [], 'current_page': 0, 'scan_time': None}
    
    def _save_cache(self, data: dict):
        """Save signal cache to file"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save cache: {e}")
    
    def format_signal_message(self, signals: List[dict], page_info: dict) -> str:
        """Format signals into a Telegram message with pagination info"""
        if not signals:
            return "No signals available. Run a scan first using: python main.py"
        
        message = f"📊 *Accumulation Signals - Page {page_info['current_page']}/{page_info['total_pages']}*\n"
        message += f"_Scanned: {page_info.get('scan_time', 'N/A')}_\n\n"
        
        for i, sig in enumerate(signals, 1):
            score = sig.get('confidence_score', 0)
            score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
            
            message += f"*{i}. {sig['stock_symbol']}* {score_emoji} _{score}_\n"
            message += f"   Entry: ₹{sig['entry_price']:.2f} | SL: ₹{sig['stop_loss']:.2f}\n"
            message += f"   Targets: ₹{sig['target_1']:.2f} → ₹{sig['target_2']:.2f} → ₹{sig['target_3']:.2f}\n"
            message += f"   Action: *{sig.get('action', 'BUY')}*\n\n"
        
        # Add navigation help
        message += "───\n"
        message += "📱 *Commands:*\n"
        message += "/next - Next 5 signals\n"
        message += "/prev - Previous 5 signals\n"
        message += "/refresh - Rescan and get new signals\n"
        message += "/help - Show this help message"
        
        return message
    
    def _is_stock_query(self, text: str) -> Optional[str]:
        """
        Check if the text is a stock query (stock symbol or name)
        
        Args:
            text: User input text
            
        Returns:
            Stock symbol if detected, None otherwise
        """
        # Clean the input
        text = text.strip().upper()
        
        # Check if it's a command (starts with /)
        if text.startswith('/'):
            return None
        
        # Common stock symbols patterns (2-10 uppercase letters)
        # Also allow names like "RELIANCE", "TCS", etc.
        stock_pattern = re.compile(r'^[A-Z]{2,10}$')
        
        # Check if it matches a stock symbol pattern
        if stock_pattern.match(text):
            return text
        
        # Check if it's a query for signals (various phrasings)
        signal_keywords = ['SIGNALS', 'SHOW SIGNALS', 'GET SIGNALS', 'TODAY SIGNALS', 
                          'CURRENT SIGNALS', 'LATEST SIGNALS', 'WHAT ARE THE SIGNALS',
                          'NEXT SIGNALS', 'MORE SIGNALS', 'ALL SIGNALS']
        
        if text in signal_keywords:
            return '__SIGNALS__'
        
        return None
    
    def analyze_stock(self, symbol: str) -> Optional[str]:
        """
        Analyze a single stock on-demand
        
        Args:
            symbol: Stock symbol to analyze
            
        Returns:
            Formatted analysis message or None if failed
        """
        try:
            # Import required modules
            from src.data.data_fetcher import NSEDataFetcher, load_config
            from src.scanner.accumulation_detector import AccumulationDetector
            from src.scoring.ai_scorer import AIScoringModel
            from src.generator.trade_generator import TradeSetupGenerator
            
            # Load config
            config = load_config("config.yaml")
            
            # Initialize components
            fetcher = NSEDataFetcher(config)
            detector = AccumulationDetector(config)
            scorer = AIScoringModel(config)
            generator = TradeSetupGenerator(config)
            
            # Get stock data
            price_data = fetcher.get_stock_data(symbol, period="1y", interval="1d")
            
            if price_data is None or len(price_data) < 60:
                return None
            
            # Get delivery data
            delivery_data = fetcher.get_delivery_data(symbol, days=20)
            
            # Get index data for relative strength
            index_data = fetcher.get_index_data("^NSEI", period="3mo")
            
            # Analyze the stock
            signal = detector.analyze(symbol, price_data, delivery_data, index_data)
            
            # Score the signal
            score = scorer.score_signal(signal)
            
            # Get stock info
            stock_info = fetcher.get_stock_info(symbol)
            
            # Generate trade setup
            setup = generator.generate_setup(score, signal, stock_info)
            
            # Try to get LLM analysis if available
            llm_response = None
            if self.llm_client and self.llm_client.is_available():
                try:
                    # Build LLM prompt
                    stock_name = stock_info.get('name', symbol) if stock_info else symbol
                    user_prompt = build_stock_analysis_prompt(
                        symbol=symbol,
                        stock_name=stock_name,
                        score=score,
                        signal=signal,
                        setup=setup,
                        stock_info=stock_info
                    )
                    
                    # Get LLM response
                    llm_response = self.llm_client.generate_analysis(
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=user_prompt
                    )
                    
                    if llm_response:
                        logger.info(f"LLM analysis generated for {symbol}")
                        # Format with header and footer
                        return format_telegram_response(llm_response, symbol, score, setup)
                except Exception as e:
                    logger.error(f"LLM analysis failed for {symbol}: {e}")
            
            # Fallback to original formatted response
            return self._format_stock_analysis(setup, score, stock_info)
            
        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {str(e)}")
            return None
    
    def _format_stock_analysis(self, setup, score, stock_info) -> str:
        """
        Format stock analysis as Telegram message
        
        Args:
            setup: TradeSetup object
            score: StockScore object
            stock_info: Stock info dict
            
        Returns:
            Formatted message string
        """
        # Determine action based on recommendation
        rec = score.recommendation.upper()
        if rec == 'BUY':
            action_emoji = '🟢'
            action_text = 'BUY - Strong Accumulation'
        elif rec == 'WATCH':
            action_emoji = '🟡'
            action_text = 'WATCH - Moderate Setup'
        else:
            action_emoji = '🔴'
            action_text = 'SKIP - Weak Setup'
        
        # Build message
        lines = []
        
        # Header
        stock_name = stock_info.get('name', setup.stock_symbol) if stock_info else setup.stock_symbol
        lines.append(f"📊 *Stock Analysis: {setup.stock_symbol}*")
        if stock_name != setup.stock_symbol:
            lines.append(f"   {stock_name}")
        
        lines.append("")
        
        # Action
        lines.append(f"{action_emoji} *Recommendation: {action_text}*")
        lines.append(f"   Confidence Score: {setup.confidence_score}/100")
        
        lines.append("")
        
        # Current Price
        lines.append(f"💰 *Current Price: ₹{setup.current_price:.2f}*")
        
        lines.append("")
        
        # Trade Setup
        lines.append("📈 *Trade Setup:*")
        lines.append(f"   Entry: ₹{setup.entry_price:.2f}")
        lines.append(f"   Stop Loss: ₹{setup.stop_loss:.2f} (-{setup.stop_loss_pct:.1f}%)")
        lines.append(f"   Targets: ₹{setup.target_1:.2f} → ₹{setup.target_2:.2f} → ₹{setup.target_3:.2f}")
        lines.append(f"   Risk/Reward: {setup.risk_reward_1:.1f}R : {setup.risk_reward_2:.1f}R : {setup.risk_reward_3:.1f}R")
        
        lines.append("")
        
        # Technical Levels
        lines.append("📍 *Technical Levels:*")
        lines.append(f"   Support: ₹{setup.support_level:.2f}")
        lines.append(f"   Resistance: ₹{setup.resistance_level:.2f}")
        lines.append(f"   Range: ₹{setup.range_low:.2f} - ₹{setup.range_high:.2f}")
        
        if setup.near_breakout:
            lines.append(f"   ⚡ Near Breakout ({setup.breakout_distance_pct:.1f}% away)")
        
        lines.append("")
        
        # Analysis Factors
        lines.append("📋 *Analysis Factors:*")
        
        # Positive factors
        if score.positive_factors:
            for factor in score.positive_factors[:5]:
                lines.append(f"   ✅ {factor}")
        
        # Negative factors
        if score.negative_factors:
            for factor in score.negative_factors[:3]:
                lines.append(f"   ❌ {factor}")
        
        lines.append("")
        
        # Additional info
        if stock_info:
            sector = stock_info.get('sector')
            if sector:
                lines.append(f"🏢 *Sector:* {sector}")
            
            pe = stock_info.get('pe_ratio')
            if pe:
                lines.append(f"📊 *P/E Ratio:* {pe:.2f}")
            
            week52_high = stock_info.get('52w_high')
            week52_low = stock_info.get('52w_low')
            if week52_high and week52_low:
                lines.append(f"📈 *52W Range:* ₹{week52_low:.2f} - ₹{week52_high:.2f}")
        
        lines.append("")
        
        # Duration
        lines.append(f"⏳ *Expected Duration:* {setup.expected_duration}")
        lines.append(f"⚠️ *Risk Level:* {setup.risk_level}")
        
        lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("🔄 *Commands:*")
        lines.append("/signals - Show current signals")
        lines.append("/next - Next 5 signals")
        lines.append("/analyze SYMBOL - Analyze a stock")
        lines.append("/help - Show all commands")
        
        return "\n".join(lines)
    
    def _handle_signals_request(self, chat_id: str, page: int = 0) -> bool:
        """
        Handle signals request with pagination
        
        Args:
            chat_id: Chat ID to respond to
            page: Page number (0-indexed)
            
        Returns:
            True if response was sent
        """
        cache = self._load_cache()
        signals = cache.get('signals', [])
        page_size = 5
        
        if not signals:
            return self.send_message_to_chat(chat_id, 
                "📊 *No Signals Available*\n\nThere are no signals to display.\n\nPlease run `python main.py` first to scan for signals!")
        
        # Reset to requested page
        cache['current_page'] = page
        self._save_cache(cache)
        
        start = page * page_size
        page_signals = signals[start:start + page_size]
        
        total_pages = (len(signals) - 1) // page_size + 1
        
        page_info = {
            'current_page': page + 1,
            'total_pages': total_pages,
            'scan_time': cache.get('scan_time')
        }
        
        message = self.format_signal_message(page_signals, page_info)
        return self.send_message_to_chat(chat_id, message)
    
    def handle_command(self, text: str, chat_id: str) -> bool:
        """
        Handle Telegram commands and stock queries
        
        Args:
            text: The command or message to handle
            chat_id: Chat ID to respond to
            
        Returns:
            True if response was sent
        """
        if not chat_id:
            logger.warning("handle_command called without chat_id")
            return False
        
        target_chat = chat_id
        
        # Check if it's a stock query
        stock_query = self._is_stock_query(text)
        
        # Handle signals query
        if stock_query == '__SIGNALS__':
            return self._handle_signals_request(target_chat, page=0)
        
        # Handle stock analysis request
        if stock_query and stock_query != '__SIGNALS__':
            # Check if it's an /analyze command with symbol
            if text.strip().upper().startswith('/ANALYZE'):
                # Extract symbol from command
                parts = text.strip().split()
                if len(parts) > 1:
                    stock_query = parts[1].upper()
            
            # Analyze the stock
            message = self.analyze_stock(stock_query)
            
            if message:
                return self.send_message_to_chat(target_chat, message)
            else:
                error_msg = f"❌ Could not analyze {stock_query}.\n\nPlease check:\n• Symbol is correct (e.g., RELIANCE, TCS)\n• Stock has sufficient data\n\nTry: /analyze RELIANCE"
                return self.send_message_to_chat(target_chat, error_msg)
        
        # Handle regular commands
        command = text.strip()
        
        cache = self._load_cache()
        signals = cache.get('signals', [])
        current_page = cache.get('current_page', 0)
        page_size = 5
        
        if command == '/start' or command == '/help':
            message = """🤖 *Stealth Accumulation Scanner*

I send you stock accumulation signals daily. Use these commands:

• /signals - Show current signals (5 at a time)
• /next - Next 5 signals
• /prev - Previous 5 signals
• /analyze SYMBOL - Analyze a specific stock
• /refresh - Run a new scan
• /help - Show this help

*Examples:*
• Send `RELIANCE` to analyze that stock
• Send `TCS` to get analysis
• Send `signals` to see current signals

*Note:* Run `python main.py` first to generate signals!"""
            return self.send_message_to_chat(target_chat, message)
        
        elif command == '/signals' or command == '/current':
            return self._handle_signals_request(target_chat, page=0)
        
        elif command == '/next':
            if not signals:
                return self.send_message_to_chat(target_chat, "No signals available.")
            
            total_pages = (len(signals) - 1) // page_size + 1
            
            if current_page < total_pages - 1:
                current_page += 1
                cache['current_page'] = current_page
                self._save_cache(cache)
            
            start = current_page * page_size
            page_signals = signals[start:start + page_size]
            
            page_info = {
                'current_page': current_page + 1,
                'total_pages': total_pages,
                'scan_time': cache.get('scan_time')
            }
            
            message = self.format_signal_message(page_signals, page_info)
            return self.send_message_to_chat(target_chat, message)
        
        elif command == '/prev':
            if not signals:
                return self.send_message_to_chat(target_chat, "No signals available.")
            
            if current_page > 0:
                current_page -= 1
                cache['current_page'] = current_page
                self._save_cache(cache)
            
            start = current_page * page_size
            page_signals = signals[start:start + page_size]
            
            total_pages = (len(signals) - 1) // page_size + 1
            page_info = {
                'current_page': current_page + 1,
                'total_pages': total_pages,
                'scan_time': cache.get('scan_time')
            }
            
            message = self.format_signal_message(page_signals, page_info)
            return self.send_message_to_chat(target_chat, message)
        
        elif command == '/refresh':
            message = "🔄 To refresh signals, please run `python main.py` on your server/PC.\n\nThis bot receives signals after each scan completes."
            return self.send_message_to_chat(target_chat, message)
        
        elif command.startswith('/analyze '):
            # Extract symbol from /analyze command
            parts = command.split()
            if len(parts) > 1:
                symbol = parts[1].upper()
                message = self.analyze_stock(symbol)
                
                if message:
                    return self.send_message_to_chat(target_chat, message)
                else:
                    error_msg = f"❌ Could not analyze {symbol}.\n\nPlease check:\n• Symbol is correct (e.g., RELIANCE, TCS)\n• Stock has sufficient data\n\nTry: /analyze RELIANCE"
                    return self.send_message_to_chat(target_chat, error_msg)
            else:
                return self.send_message_to_chat(target_chat, "Usage: /analyze SYMBOL\nExample: /analyze RELIANCE")
        
        else:
            message = f"Unknown command: {command}\n\nUse /help for available commands.\n\nYou can also send a stock symbol (e.g., RELIANCE) to analyze it!"
            return self.send_message_to_chat(target_chat, message)
    
    def start_polling(self):
        """Start polling for Telegram messages"""
        if not self.is_configured():
            logger.error("Telegram bot not configured for polling")
            return
        
        logger.info("Starting Telegram bot polling...")
        
        # Get last update ID to avoid processing old messages
        try:
            url = f"{self.api_url}/getUpdates?timeout=60"
            response = requests.get(url, timeout=70)
            
            if response.status_code == 200:
                updates = response.json()
                if updates.get('ok'):
                    results = updates.get('result', [])
                    if results:
                        last_update_id = results[-1].get('update_id', 0)
                        logger.info(f"Starting from update ID: {last_update_id}")
        except Exception as e:
            logger.warning(f"Could not get initial updates: {e}")
        
        last_update_id = 0
        
        while True:
            try:
                url = f"{self.api_url}/getUpdates?offset={last_update_id + 1}&timeout=60"
                response = requests.get(url, timeout=70)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        results = data.get('result', [])
                        
                        for update in results:
                            last_update_id = update.get('update_id', 0)
                            
                            # Check if it's a message
                            if 'message' in update:
                                message = update['message']
                                chat_id = str(message['chat']['id'])
                                text = message.get('text', '')
                                
                                # Only respond to our configured chat
                                if chat_id == self.chat_id:
                                    logger.info(f"Received command: {text}")
                                    self.handle_command(text, chat_id)
                                    
                else:
                    logger.error(f"Poll error: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Polling error: {e}")
                import time
                time.sleep(5)
    
    def send_alert(self, setup, force_send: bool = False, is_below_threshold: bool = False) -> bool:
        """
        Send a trade setup alert
        
        Args:
            setup: TradeSetup object
            force_send: If True, send even if below threshold
            is_below_threshold: If True, add warning prefix to message
            
        Returns:
            True if successful, False otherwise
        """
        if setup.confidence_score < self.alert_threshold and not force_send:
            logger.info(f"Skipping {setup.stock_symbol} - score below threshold")
            return False
            
        from src.generator.trade_generator import format_telegram_alert
        
        message = format_telegram_alert(setup)
        
        # Add reasoning information if available
        reasoning_config = self.config.get('reasoning', {})
        if reasoning_config.get('explanation', {}).get('include_in_telegram', True):
            if hasattr(setup, 'reasoning_text') and setup.reasoning_text:
                message += "\n\n🧠 Reasoning:\n" + setup.reasoning_text[:300]
            
            # Add confidence level indicator
            if hasattr(setup, 'confidence_level') and setup.confidence_level:
                level_emoji = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}
                level = level_emoji.get(setup.confidence_level, '🟡')
                message += f"\n\n{level} Confidence Level: {setup.confidence_level.upper()}"
            
            # Add AI score if available
            if hasattr(setup, 'ai_score') and setup.ai_score:
                message += f"\n🤖 AI Score: {setup.ai_score}/100"
        
        # Add simple warning indicator for below-threshold signals
        if is_below_threshold:
            message = message.replace(
                "📊 Stock Alert:",
                "📊 Stock Alert: ⚠️ BELOW THRESHOLD",
                1
            )
        
        return self.send_message(message)
    
    def send_alerts(self, setups: List) -> Dict:
        """
        Send multiple trade setup alerts
        
        Args:
            setups: List of TradeSetup objects
            
        Returns:
            Dict with success/failure counts
        """
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        if not setups:
            logger.info("No setups to send")
            return results
            
        # Send individual alerts
        for setup in setups:
            if setup.confidence_score >= self.alert_threshold:
                if self.send_alert(setup):
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            else:
                results['skipped'] += 1
        
        logger.info(f"Alerts: {results['sent']} sent, {results['failed']} failed, {results['skipped']} skipped")
        
        return results
    
    def send_summary(self, setups: List, scan_time: str = None) -> bool:
        """
        Send a summary of all scans
        
        Args:
            setups: List of TradeSetup objects
            scan_time: Optional scan timestamp
            
        Returns:
            True if successful, False otherwise
        """
        if not setups:
            message = "📊 Daily Accumulation Scanner\n\nNo accumulation setups found today."
        else:
            from src.generator.trade_generator import format_summary_alert
            message = format_summary_alert(setups)
            
        return self.send_message(message)
    
    def test_connection(self) -> bool:
        """
        Test the bot connection
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("Telegram bot not configured")
            return False
            
        try:
            url = f"{self.api_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    logger.info(f"Bot connected: {bot_info['result']['first_name']}")
                    return True
                    
            logger.error(f"Bot connection failed: {response.text}")
            return False
            
        except Exception as e:
            logger.error(f"Error testing bot connection: {str(e)}")
            return False
    
    def get_updates(self) -> List[Dict]:
        """
        Get recent bot updates (for debugging)
        
        Returns:
            List of update dicts
        """
        if not self.is_configured():
            return []
            
        try:
            url = f"{self.api_url}/getUpdates"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data.get('result', [])
                    
            return []
            
        except Exception as e:
            logger.error(f"Error getting updates: {str(e)}")
            return []


def create_bot(config: Dict) -> TelegramBot:
    """
    Factory function to create a Telegram bot
    
    Args:
        config: Configuration dictionary
        
    Returns:
        TelegramBot instance
    """
    return TelegramBot(config)

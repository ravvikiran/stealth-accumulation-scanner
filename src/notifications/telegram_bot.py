"""
Telegram Bot Notification System
Sends trade setup alerts via Telegram with pagination support
"""

import requests
from typing import List, Dict, Optional
import logging
import os
import json

logger = logging.getLogger(__name__)


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
    
    def handle_command(self, command: str, chat_id: str = None) -> bool:
        """
        Handle Telegram commands
        
        Args:
            command: The command to handle
            chat_id: Chat ID to respond to
            
        Returns:
            True if response was sent
        """
        target_chat = chat_id or self.chat_id
        
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
• /refresh - Run a new scan
• /help - Show this help

*Note:* Run `python main.py` first to generate signals!"""
            return self.send_message_to_chat(target_chat, message)
        
        elif command == '/signals' or command == '/current':
            if not signals:
                return self.send_message_to_chat(target_chat, 
                    "No signals available. Please run `python main.py` first to scan for signals!")
            
            current_page = 0
            cache['current_page'] = 0
            self._save_cache(cache)
            
            start = current_page * page_size
            page_signals = signals[start:start + page_size]
            
            page_info = {
                'current_page': current_page + 1,
                'total_pages': (len(signals) - 1) // page_size + 1 if signals else 0,
                'scan_time': cache.get('scan_time')
            }
            
            message = self.format_signal_message(page_signals, page_info)
            return self.send_message_to_chat(target_chat, message)
        
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
        
        else:
            message = f"Unknown command: {command}\n\nUse /help for available commands."
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
    
    def send_alert(self, setup) -> bool:
        """
        Send a trade setup alert
        
        Args:
            setup: TradeSetup object
            
        Returns:
            True if successful, False otherwise
        """
        if setup.confidence_score < self.alert_threshold:
            logger.info(f"Skipping {setup.stock_symbol} - score below threshold")
            return False
            
        from src.generator.trade_generator import format_telegram_alert
        
        message = format_telegram_alert(setup)
        
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

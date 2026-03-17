"""
Telegram Bot Notification System
Sends trade setup alerts via Telegram
"""

import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram Bot for sending stock alerts
    """
    
    def __init__(self, config: Dict):
        self.config = config
        telegram_config = config.get('telegram', {})
        
        self.enabled = telegram_config.get('enabled', True)
        self.bot_token = telegram_config.get('bot_token', '')
        self.chat_id = telegram_config.get('chat_id', '')
        self.alert_threshold = telegram_config.get('alert_threshold', 60)
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
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

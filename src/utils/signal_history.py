"""
Signal History Manager
Prevents duplicate alerts by tracking sent signals
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SignalHistory:
    """
    Manages signal history to prevent duplicate alerts
    """
    
    def __init__(self, config: Dict):
        self.config = config
        history_config = config.get('signal_history', {})
        
        self.enabled = history_config.get('enabled', True)
        self.max_age_hours = history_config.get('max_age_hours', 24)
        self.file_path = history_config.get('file_path', 'data/signal_history.json')
        
        # Ensure data directory exists
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing history
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """Load signal history from file"""
        if not os.path.exists(self.file_path):
            return {}
        
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load signal history: {str(e)}")
            return {}
    
    def _save_history(self) -> None:
        """Save signal history to file"""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save signal history: {str(e)}")
    
    def is_new_signal(self, stock_symbol: str, current_price: float) -> bool:
        """
        Check if this is a new signal that should be alerted
        
        Args:
            stock_symbol: Stock symbol
            current_price: Current stock price
            
        Returns:
            True if this is a new signal worth alerting
        """
        if not self.enabled:
            return True
        
        now = datetime.now()
        
        # Check if we have a previous signal for this stock
        if stock_symbol in self.history:
            prev_signal = self.history[stock_symbol]
            
            # Check when it was last sent - with error handling
            try:
                last_sent_str = prev_signal.get('last_sent')
                if last_sent_str:
                    last_sent = datetime.fromisoformat(last_sent_str)
                else:
                    # No valid timestamp, treat as new signal
                    return True
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp for {stock_symbol}, treating as new signal: {e}")
                return True
            
            age = (now - last_sent).total_seconds() / 3600  # hours
            
            # If sent within max_age_hours, check if anything changed
            if age < self.max_age_hours:
                # Check if key parameters changed significantly
                prev_price = prev_signal.get('entry_price', 0)
                price_change_pct = abs(current_price - prev_price) / prev_price * 100 if prev_price > 0 else 0
                
                # If price changed by more than 3%, consider it a new signal
                if price_change_pct > 3:
                    logger.info(f"{stock_symbol}: Price changed {price_change_pct:.1f}%, sending new alert")
                    return True
                
                logger.info(f"{stock_symbol}: Signal already sent {age:.1f}h ago, skipping")
                return False
            else:
                # Older than max_age_hours, send new alert
                logger.info(f"{stock_symbol}: Previous signal was {age:.1f}h ago, sending new alert")
                return True
        
        # No previous signal, this is new
        return True
    
    def record_signal(
        self,
        stock_symbol: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        confidence_score: int
    ) -> None:
        """
        Record a sent signal
        
        Args:
            stock_symbol: Stock symbol
            entry_price: Entry price
            stop_loss: Stop loss
            target_1: First target
            confidence_score: Confidence score
        """
        if not self.enabled:
            return
        
        self.history[stock_symbol] = {
            'last_sent': datetime.now().isoformat(),
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'target_1': target_1,
            'confidence_score': confidence_score
        }
        
        self._save_history()
    
    def cleanup_old_entries(self) -> None:
        """Remove entries older than max_age_hours"""
        if not self.enabled:
            return
        
        now = datetime.now()
        cutoff = now - timedelta(hours=self.max_age_hours)
        
        cleaned = {}
        for symbol, data in self.history.items():
            try:
                last_sent_str = data.get('last_sent')
                if last_sent_str:
                    last_sent = datetime.fromisoformat(last_sent_str)
                    if last_sent > cutoff:
                        cleaned[symbol] = data
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp for {symbol} during cleanup: {e}")
        
        if len(cleaned) != len(self.history):
            self.history = cleaned
            self._save_history()
            logger.info(f"Cleaned up {len(self.history) - len(cleaned)} old signal entries")
    
    def get_active_signals(self) -> List[str]:
        """Get list of symbols with recent signals"""
        if not self.enabled:
            return []
        
        now = datetime.now()
        cutoff = now - timedelta(hours=self.max_age_hours)
        
        active = []
        for symbol, data in self.history.items():
            last_sent = datetime.fromisoformat(data.get('last_sent', '2020-01-01'))
            if last_sent > cutoff:
                active.append(symbol)
        
        return active


def create_signal_history(config: Dict) -> SignalHistory:
    """
    Factory function to create signal history manager
    
    Args:
        config: Configuration dictionary
        
    Returns:
        SignalHistory instance
    """
    return SignalHistory(config)

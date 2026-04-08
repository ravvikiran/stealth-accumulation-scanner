"""
Signal History Manager
Prevents duplicate alerts by tracking sent signals
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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
        self.max_age_hours = history_config.get('max_age_hours', 12)
        self.file_path = history_config.get('file_path', 'data/signal_history.json')

        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
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

    def is_new_signal(self, stock_symbol: str, current_price: float, confidence_score: Optional[int] = None) -> bool:
        """
        Check if this is a new signal that should be alerted.

        Re-alert rules within 12h window:
        - score increases by >= 10, OR
        - price changes by >= 3%
        """
        if not self.enabled:
            return True

        now = datetime.now()

        if stock_symbol not in self.history:
            return True

        prev_signal = self.history[stock_symbol]

        try:
            last_sent_str = prev_signal.get('last_sent')
            if not last_sent_str:
                return True
            last_sent = datetime.fromisoformat(last_sent_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid timestamp for {stock_symbol}, treating as new signal: {e}")
            return True

        age = (now - last_sent).total_seconds() / 3600

        if age >= self.max_age_hours:
            logger.info(f"{stock_symbol}: Previous signal was {age:.1f}h ago, sending new alert")
            return True

        prev_price = prev_signal.get('entry_price', 0)
        price_change_pct = abs(current_price - prev_price) / prev_price * 100 if prev_price > 0 else 0

        prev_score = prev_signal.get('confidence_score')
        score_delta = 0
        if confidence_score is not None and prev_score is not None:
            score_delta = confidence_score - prev_score

        if score_delta >= 10:
            logger.info(f"{stock_symbol}: Score improved by {score_delta:.1f}, sending re-alert")
            return True

        if price_change_pct >= 3:
            logger.info(f"{stock_symbol}: Price changed {price_change_pct:.1f}%, sending re-alert")
            return True

        logger.info(f"{stock_symbol}: Signal already sent {age:.1f}h ago, skipping")
        return False

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

        original_count = len(self.history)
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

        if len(cleaned) != original_count:
            removed = original_count - len(cleaned)
            self.history = cleaned
            self._save_history()
            logger.info(f"Cleaned up {removed} old signal entries")

    def get_active_signals(self) -> List[str]:
        """Get list of symbols with recent signals"""
        if not self.enabled:
            return []

        now = datetime.now()
        cutoff = now - timedelta(hours=self.max_age_hours)

        active = []
        for symbol, data in self.history.items():
            try:
                last_sent = datetime.fromisoformat(data.get('last_sent', '2020-01-01'))
                if last_sent > cutoff:
                    active.append(symbol)
            except (ValueError, TypeError):
                continue

        return active


def create_signal_history(config: Dict) -> SignalHistory:
    """
    Factory function to create signal history manager
    """
    return SignalHistory(config)
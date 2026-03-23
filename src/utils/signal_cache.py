"""
Signal Cache - Stores scanned signals for pagination
Allows users to browse through signals page by page
"""

import json
import os
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SIGNAL_CACHE_FILE = "data/signal_cache.json"

class SignalCache:
    """
    Stores scanned signals for paginated access via Telegram
    """
    
    def __init__(self):
        self.signals: List[dict] = []
        self.scan_time: Optional[str] = None
        self.current_page: int = 0
        self.page_size: int = 5
        self.load()
    
    def save(self):
        """Save signals to file"""
        os.makedirs(os.path.dirname(SIGNAL_CACHE_FILE), exist_ok=True)
        data = {
            'signals': self.signals,
            'scan_time': self.scan_time,
            'current_page': self.current_page
        }
        with open(SIGNAL_CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self):
        """Load signals from file"""
        try:
            if os.path.exists(SIGNAL_CACHE_FILE):
                with open(SIGNAL_CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    self.signals = data.get('signals', [])
                    self.scan_time = data.get('scan_time')
                    self.current_page = data.get('current_page', 0)
        except Exception as e:
            logger.warning(f"Could not load signal cache: {e}")
    
    def update_signals(self, signals: List, scan_time: str = None):
        """
        Update the stored signals
        
        Args:
            signals: List of TradeSetup objects
            scan_time: Timestamp of the scan
        """
        self.signals = []
        for setup in signals:
            self.signals.append({
                'stock_symbol': setup.stock_symbol,
                'entry_price': setup.entry_price,
                'stop_loss': setup.stop_loss,
                'target_1': setup.target_1,
                'target_2': setup.target_2,
                'target_3': setup.target_3,
                'confidence_score': setup.confidence_score,
                'current_price': setup.current_price,
                'action': getattr(setup, 'action', 'BUY'),
                'rationale': getattr(setup, 'rationale', '')
            })
        
        self.scan_time = scan_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.current_page = 0
        self.save()
        
        logger.info(f"Signal cache updated with {len(self.signals)} signals")
    
    def get_page(self, page: int = None) -> List[dict]:
        """
        Get signals for a specific page
        
        Args:
            page: Page number (0-indexed), None for current page
            
        Returns:
            List of signal dictionaries
        """
        if page is not None:
            # Validate and clamp page number to valid range
            total_pages = (len(self.signals) - 1) // self.page_size + 1 if self.signals else 0
            if total_pages > 0:
                self.current_page = max(0, min(page, total_pages - 1))
            else:
                self.current_page = 0
        
        start = self.current_page * self.page_size
        end = start + self.page_size
        
        return self.signals[start:end]
    
    def next_page(self) -> List[dict]:
        """Get the next page of signals"""
        total_pages = (len(self.signals) - 1) // self.page_size + 1 if self.signals else 0
        
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.save()
        
        return self.get_page()
    
    def prev_page(self) -> List[dict]:
        """Get the previous page of signals"""
        if self.current_page > 0:
            self.current_page -= 1
            self.save()
        
        return self.get_page()
    
    def get_page_info(self) -> dict:
        """
        Get information about current pagination state
        
        Returns:
            Dict with page info
        """
        total = len(self.signals)
        total_pages = (total - 1) // self.page_size + 1 if total > 0 else 0
        
        return {
            'current_page': self.current_page + 1,  # 1-indexed for display
            'total_pages': total_pages,
            'total_signals': total,
            'has_next': self.current_page < total_pages - 1,
            'has_prev': self.current_page > 0,
            'scan_time': self.scan_time
        }
    
    def clear(self):
        """Clear the cache"""
        self.signals = []
        self.current_page = 0
        self.scan_time = None
        self.save()


def get_signal_cache() -> SignalCache:
    """Get the signal cache instance"""
    return SignalCache()

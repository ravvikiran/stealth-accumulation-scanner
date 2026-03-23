"""
Signal Registry - Active signal tracking
Part of Signal Intelligence Engine (SIE)
"""

import json
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ActiveSignal:
    """Active signal being tracked"""
    signal_id: str
    stock_symbol: str
    stock_name: str
    
    # Trade parameters
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    target_3: float
    
    # Metadata
    signal_date: str
    confidence_score: int
    rule_score: int
    ai_score: Optional[int]
    reasoning_text: str
    
    # Status
    status: str = "active"  # active, hit_target_1, hit_target_2, hit_target_3, stoploss_hit, expired


class SignalRegistry:
    """
    Manages active signals and tracks their status until resolution
    """
    
    def __init__(self, config: Dict):
        self.config = config
        sie_config = config.get('signal_intelligence', {})
        
        self.enabled = sie_config.get('enabled', True)
        self.max_signal_age_days = sie_config.get('monitoring', {}).get('max_signal_age_days', 30)
        
        # File paths
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.active_signals_file = self.data_dir / "active_signals.json"
        
        # Load existing signals
        self.signals: Dict[str, ActiveSignal] = {}
        self._load_signals()
    
    def _load_signals(self):
        """Load active signals from file"""
        if not self.active_signals_file.exists():
            return
        
        try:
            with open(self.active_signals_file, 'r') as f:
                data = json.load(f)
                
            for sig_data in data.get('signals', []):
                signal = ActiveSignal(**sig_data)
                # Only keep active signals
                if signal.status == "active":
                    self.signals[signal.signal_id] = signal
                    
            logger.info(f"Loaded {len(self.signals)} active signals")
            
        except Exception as e:
            logger.error(f"Failed to load signals: {e}")
    
    def _save_signals(self):
        """Save signals to file"""
        try:
            data = {
                'signals': [asdict(s) for s in self.signals.values()],
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.active_signals_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save signals: {e}")
    
    def register_signal(
        self,
        stock_symbol: str,
        stock_name: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        target_2: float,
        target_3: float,
        confidence_score: int,
        rule_score: int,
        ai_score: Optional[int] = None,
        reasoning_text: str = ""
    ) -> str:
        """
        Register a new signal for tracking
        
        Returns:
            signal_id of the registered signal
        """
        if not self.enabled:
            return ""
        
        # Generate unique signal ID
        signal_id = f"SIG-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        
        signal = ActiveSignal(
            signal_id=signal_id,
            stock_symbol=stock_symbol,
            stock_name=stock_name,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            signal_date=datetime.now().isoformat(),
            confidence_score=confidence_score,
            rule_score=rule_score,
            ai_score=ai_score,
            reasoning_text=reasoning_text,
            status="active"
        )
        
        self.signals[signal_id] = signal
        self._save_signals()
        
        logger.info(f"Registered signal {signal_id} for {stock_symbol}")
        return signal_id
    
    def update_signal_status(self, signal_id: str, new_status: str) -> bool:
        """
        Update the status of a signal
        
        Args:
            signal_id: Signal to update
            new_status: New status (hit_target_1, hit_target_2, hit_target_3, stoploss_hit, expired)
        """
        if signal_id not in self.signals:
            logger.warning(f"Signal {signal_id} not found")
            return False
        
        self.signals[signal_id].status = new_status
        self._save_signals()
        
        logger.info(f"Updated {signal_id} status to {new_status}")
        return True
    
    def get_active_signals(self) -> List[ActiveSignal]:
        """Get all active signals"""
        return [s for s in self.signals.values() if s.status == "active"]
    
    def get_signal(self, signal_id: str) -> Optional[ActiveSignal]:
        """Get a specific signal"""
        return self.signals.get(signal_id)
    
    def check_outcomes(self, current_prices: Dict[str, float]) -> List[Dict]:
        """
        Check all active signals against current prices
        
        Args:
            current_prices: Dict of symbol -> current price
            
        Returns:
            List of resolved signals with outcome details
        """
        resolved = []
        
        for signal_id, signal in list(self.signals.items()):
            if signal.status != "active":
                continue
            
            current_price = current_prices.get(signal.stock_symbol)
            if current_price is None:
                continue
            
            # Check if target hit
            if current_price >= signal.target_1:
                new_status = "hit_target_1"
                if current_price >= signal.target_2:
                    new_status = "hit_target_2"
                if current_price >= signal.target_3:
                    new_status = "hit_target_3"
                
                self.update_signal_status(signal_id, new_status)
                
                resolved.append({
                    'signal_id': signal_id,
                    'stock_symbol': signal.stock_symbol,
                    'outcome': new_status,
                    'exit_price': current_price,
                    'pnl_pct': (current_price - signal.entry_price) / signal.entry_price * 100
                })
                
            # Check if stop loss hit
            elif current_price <= signal.stop_loss:
                self.update_signal_status(signal_id, "stoploss_hit")
                
                resolved.append({
                    'signal_id': signal_id,
                    'stock_symbol': signal.stock_symbol,
                    'outcome': "stoploss_hit",
                    'exit_price': current_price,
                    'pnl_pct': (current_price - signal.entry_price) / signal.entry_price * 100
                })
        
        return resolved
    
    def check_expired(self) -> List[Dict]:
        """Check for expired signals"""
        expired = []
        cutoff = datetime.now() - timedelta(days=self.max_signal_age_days)
        
        for signal_id, signal in list(self.signals.items()):
            if signal.status != "active":
                continue
            
            signal_date = datetime.fromisoformat(signal.signal_date)
            if signal_date < cutoff:
                self.update_signal_status(signal_id, "expired")
                
                expired.append({
                    'signal_id': signal_id,
                    'stock_symbol': signal.stock_symbol,
                    'outcome': "expired"
                })
        
        return expired
    
    def get_stats(self) -> Dict:
        """Get statistics about signals"""
        active = self.get_active_signals()
        
        status_counts = {}
        for signal in self.signals.values():
            status_counts[signal.status] = status_counts.get(signal.status, 0) + 1
        
        return {
            'total_tracked': len(self.signals),
            'active_count': len(active),
            'status_breakdown': status_counts
        }


def create_signal_registry(config: Dict) -> SignalRegistry:
    """Factory function to create signal registry"""
    return SignalRegistry(config)
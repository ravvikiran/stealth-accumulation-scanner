"""
Outcome Tracker - Records signal outcomes
Part of Signal Intelligence Engine (SIE)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SignalOutcome:
    """Recorded outcome of a resolved signal"""
    signal_id: str
    stock_symbol: str
    stock_name: str
    
    # Trade details
    entry_price: float
    exit_price: float
    stop_loss: float
    target_1: float
    
    # Outcome
    outcome: str  # target_1_hit, target_2_hit, target_3_hit, stoploss_hit, expired
    pnl_percent: float
    days_to_resolution: int
    
    # Signal metadata
    confidence_score: int
    rule_score: int
    ai_score: Optional[int]
    
    # Timestamps
    signal_date: str
    resolution_date: str


class OutcomeTracker:
    """
    Records outcomes of resolved signals for historical analysis
    """
    
    def __init__(self, config: Dict):
        self.config = config
        sie_config = config.get('signal_intelligence', {})
        
        self.enabled = sie_config.get('enabled', True)
        
        # File paths
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.outcomes_file = self.data_dir / "signal_outcomes.json"
        
        # Load existing outcomes
        self.outcomes: List[SignalOutcome] = []
        self._load_outcomes()
    
    def _load_outcomes(self):
        """Load outcomes from file"""
        if not self.outcomes_file.exists():
            return
        
        try:
            with open(self.outcomes_file, 'r') as f:
                data = json.load(f)
                
            for outcome_data in data.get('outcomes', []):
                outcome = SignalOutcome(**outcome_data)
                self.outcomes.append(outcome)
                
            logger.info(f"Loaded {len(self.outcomes)} historical outcomes")
            
        except Exception as e:
            logger.error(f"Failed to load outcomes: {e}")
    
    def _save_outcomes(self):
        """Save outcomes to file"""
        try:
            data = {
                'outcomes': [asdict(o) for o in self.outcomes],
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.outcomes_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save outcomes: {e}")
    
    def record_outcome(
        self,
        signal_id: str,
        stock_symbol: str,
        stock_name: str,
        entry_price: float,
        exit_price: float,
        stop_loss: float,
        target_1: float,
        outcome: str,
        confidence_score: int,
        rule_score: int,
        ai_score: Optional[int],
        signal_date: str
    ) -> SignalOutcome:
        """
        Record the outcome of a resolved signal
        """
        if not self.enabled:
            return None
        
        # Calculate PnL percentage
        pnl_percent = (exit_price - entry_price) / entry_price * 100
        
        # Calculate days to resolution - with error handling
        try:
            signal_dt = datetime.fromisoformat(signal_date)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid signal_date format: {signal_date}, using current time")
            signal_dt = datetime.now()
        
        resolution_dt = datetime.now()
        days_to_resolution = (resolution_dt - signal_dt).days
        
        outcome_record = SignalOutcome(
            signal_id=signal_id,
            stock_symbol=stock_symbol,
            stock_name=stock_name,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=stop_loss,
            target_1=target_1,
            outcome=outcome,
            pnl_percent=pnl_percent,
            days_to_resolution=days_to_resolution,
            confidence_score=confidence_score,
            rule_score=rule_score,
            ai_score=ai_score,
            signal_date=signal_date,
            resolution_date=resolution_dt.isoformat()
        )
        
        self.outcomes.append(outcome_record)
        self._save_outcomes()
        
        logger.info(f"Recorded outcome for {signal_id}: {outcome} ({pnl_percent:.2f}%)")
        return outcome_record
    
    def get_recent_outcomes(self, limit: int = 50) -> List[SignalOutcome]:
        """Get recent outcomes"""
        return self.outcomes[-limit:] if len(self.outcomes) <= limit else self.outcomes[-limit:][::-1]
    
    def get_outcomes_by_symbol(self, symbol: str) -> List[SignalOutcome]:
        """Get all outcomes for a specific symbol"""
        return [o for o in self.outcomes if o.stock_symbol == symbol]
    
    def get_winning_outcomes(self) -> List[SignalOutcome]:
        """Get all winning trades (hit any target)"""
        return [o for o in self.outcomes if 'target' in o.outcome]
    
    def get_losing_outcomes(self) -> List[SignalOutcome]:
        """Get all losing trades (stoploss or expired)"""
        return [o for o in self.outcomes if o.outcome in ['stoploss_hit', 'expired']]
    
    def calculate_win_rate(self) -> float:
        """Calculate overall win rate"""
        if not self.outcomes:
            return 0.0
        
        wins = len(self.get_winning_outcomes())
        return (wins / len(self.outcomes)) * 100
    
    def get_stats(self) -> Dict:
        """Get outcome statistics"""
        if not self.outcomes:
            return {
                'total_outcomes': 0,
                'win_rate': 0.0,
                'avg_return': 0.0,
                'avg_loss': 0.0
            }
        
        wins = self.get_winning_outcomes()
        losses = self.get_losing_outcomes()
        
        avg_return = sum(o.pnl_percent for o in wins) / len(wins) if wins else 0
        avg_loss = sum(o.pnl_percent for o in losses) / len(losses) if losses else 0
        
        return {
            'total_outcomes': len(self.outcomes),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': self.calculate_win_rate(),
            'avg_return': round(avg_return, 2),
            'avg_loss': round(avg_loss, 2),
            'target_1_hits': len([o for o in self.outcomes if o.outcome == 'hit_target_1']),
            'target_2_hits': len([o for o in self.outcomes if o.outcome == 'hit_target_2']),
            'target_3_hits': len([o for o in self.outcomes if o.outcome == 'hit_target_3']),
            'stoploss_hits': len([o for o in self.outcomes if o.outcome == 'stoploss_hit']),
            'expired': len([o for o in self.outcomes if o.outcome == 'expired'])
        }


def create_outcome_tracker(config: Dict) -> OutcomeTracker:
    """Factory function to create outcome tracker"""
    return OutcomeTracker(config)
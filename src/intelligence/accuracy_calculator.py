"""
Accuracy Calculator - Calculate accuracy metrics
Part of Signal Intelligence Engine (SIE)
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
    """Calculated accuracy metrics"""
    total_signals: int
    targets_hit: int
    stoploss_hit: int
    expired: int
    
    accuracy_rate: float  # % signals that hit any target
    target_1_rate: float
    target_2_rate: float
    target_3_rate: float
    stoploss_rate: float
    expired_rate: float
    
    avg_return: float
    avg_loss: float
    risk_adjusted_return: float
    
    avg_days_to_resolution: float
    confidence_correlation: float


class AccuracyCalculator:
    """
    Calculates accuracy metrics from signal outcomes
    """
    
    def __init__(self, config: Dict):
        self.config = config
    
    def calculate_metrics(self, outcomes: List) -> AccuracyMetrics:
        """
        Calculate accuracy metrics from outcomes
        """
        if not outcomes:
            return self._empty_metrics()
        
        total = len(outcomes)
        
        # Count by outcome type
        target_hits = [o for o in outcomes if 'target' in o.outcome]
        t1_hits = [o for o in outcomes if o.outcome == 'hit_target_1']
        t2_hits = [o for o in outcomes if o.outcome == 'hit_target_2']
        t3_hits = [o for o in outcomes if o.outcome == 'hit_target_3']
        sl_hits = [o for o in outcomes if o.outcome == 'stoploss_hit']
        expired = [o for o in outcomes if o.outcome == 'expired']
        
        # Calculate rates
        accuracy_rate = (len(target_hits) / total * 100) if total > 0 else 0
        t1_rate = (len(t1_hits) / total * 100) if total > 0 else 0
        t2_rate = (len(t2_hits) / total * 100) if total > 0 else 0
        t3_rate = (len(t3_hits) / total * 100) if total > 0 else 0
        sl_rate = (len(sl_hits) / total * 100) if total > 0 else 0
        exp_rate = (len(expired) / total * 100) if total > 0 else 0
        
        # Calculate returns
        if target_hits:
            avg_return = sum(o.pnl_percent for o in target_hits) / len(target_hits)
        else:
            avg_return = 0.0
            
        if sl_hits or expired:
            losing = sl_hits + expired
            avg_loss = sum(o.pnl_percent for o in losing) / len(losing)
        else:
            avg_loss = 0.0
        
        # Risk adjusted return
        risk_adj = (accuracy_rate / 100) * avg_return if avg_return > 0 else 0
        
        # Average days to resolution
        if outcomes:
            avg_days = sum(o.days_to_resolution for o in outcomes) / len(outcomes)
        else:
            avg_days = 0.0
        
        # Confidence correlation
        corr = self._calculate_confidence_correlation(outcomes)
        
        return AccuracyMetrics(
            total_signals=total,
            targets_hit=len(target_hits),
            stoploss_hit=len(sl_hits),
            expired=len(expired),
            accuracy_rate=round(accuracy_rate, 2),
            target_1_rate=round(t1_rate, 2),
            target_2_rate=round(t2_rate, 2),
            target_3_rate=round(t3_rate, 2),
            stoploss_rate=round(sl_rate, 2),
            expired_rate=round(exp_rate, 2),
            avg_return=round(avg_return, 2),
            avg_loss=round(avg_loss, 2),
            risk_adjusted_return=round(risk_adj, 2),
            avg_days_to_resolution=round(avg_days, 1),
            confidence_correlation=round(corr, 2)
        )
    
    def _calculate_confidence_correlation(self, outcomes: List) -> float:
        """
        Calculate correlation between confidence score and positive outcomes
        """
        if not outcomes:
            return 0.0
        
        # Group by confidence ranges
        high_conf = [o for o in outcomes if o.confidence_score >= 75]
        mid_conf = [o for o in outcomes if 60 <= o.confidence_score < 75]
        low_conf = [o for o in outcomes if o.confidence_score < 60]
        
        # Calculate win rate for each group
        def calc_win_rate(group):
            if not group:
                return 0.0
            wins = len([o for o in group if 'target' in o.outcome])
            return (wins / len(group)) * 100
        
        high_win = calc_win_rate(high_conf)
        mid_win = calc_win_rate(mid_conf)
        low_win = calc_win_rate(low_conf)
        
        # If higher confidence leads to higher win rate, correlation is positive
        if high_win >= mid_win >= low_win:
            return 75.0  # Strong positive correlation
        elif high_win >= mid_win or mid_win >= low_win:
            return 50.0  # Moderate correlation
        elif high_win < mid_win < low_win:
            return -50.0  # Negative correlation (confidence not predictive)
        else:
            return 0.0  # No clear correlation
    
    def _empty_metrics(self) -> AccuracyMetrics:
        """Return empty metrics"""
        return AccuracyMetrics(
            total_signals=0,
            targets_hit=0,
            stoploss_hit=0,
            expired=0,
            accuracy_rate=0.0,
            target_1_rate=0.0,
            target_2_rate=0.0,
            target_3_rate=0.0,
            stoploss_rate=0.0,
            expired_rate=0.0,
            avg_return=0.0,
            avg_loss=0.0,
            risk_adjusted_return=0.0,
            avg_days_to_resolution=0.0,
            confidence_correlation=0.0
        )
    
    def calculate_factor_accuracy(self, outcomes: List, factor_scores: Dict) -> Dict:
        """
        Calculate accuracy by scoring factor to see which factors predict success
        
        Args:
            outcomes: List of SignalOutcome
            factor_scores: Dict of factor_name -> score
            
        Returns:
            Dict of factor -> accuracy percentage
        """
        factor_accuracy = {}
        
        for factor, score in factor_scores.items():
            # Get outcomes where this factor was positive
            # This is a simplified version - in production you'd track which factors each signal had
            relevant = [o for o in outcomes if o.confidence_score >= score]
            
            if relevant:
                wins = len([o for o in relevant if 'target' in o.outcome])
                factor_accuracy[factor] = round((wins / len(relevant)) * 100, 1)
        
        return factor_accuracy


def create_accuracy_calculator(config: Dict) -> AccuracyCalculator:
    """Factory function to create accuracy calculator"""
    return AccuracyCalculator(config)
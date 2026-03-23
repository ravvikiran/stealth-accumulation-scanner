"""
Learning Engine - Weight adjustment based on accuracy
Part of Signal Intelligence Engine (SIE)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class LearningEngine:
    """
    Automatically adjusts scoring weights based on historical accuracy data
    """
    
    # Default weights (from config)
    DEFAULT_WEIGHTS = {
        'price_structure': 20,
        'volume_behavior': 20,
        'delivery_data': 15,
        'support_strength': 15,
        'relative_strength': 10,
        'volatility_compression': 10,
        'ma_behavior': 10
    }
    
    def __init__(self, config: Dict):
        self.config = config
        sie_config = config.get('signal_intelligence', {})
        
        self.enabled = sie_config.get('learning', {}).get('auto_adjust_weights', True)
        
        learning_config = sie_config.get('learning', {})
        self.min_signals = learning_config.get('min_signals_for_adjustment', 20)
        self.max_monthly_adjustment = learning_config.get('max_monthly_adjustment', 5)
        self.dampening = learning_config.get('dampening_factor', 0.5)
        
        # Load current weights and history
        self.data_dir = Path("data")
        self.weights_file = self.data_dir / "learning_weights.json"
        
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self.historical_accuracy = {}
        self.last_adjusted = None
        self.adjustment_count = 0
        
        self._load_weights()
    
    def _load_weights(self):
        """Load weights from file"""
        if not self.weights_file.exists():
            return
        
        try:
            with open(self.weights_file, 'r') as f:
                data = json.load(f)
                
            self.weights = data.get('current_weights', self.DEFAULT_WEIGHTS.copy())
            self.historical_accuracy = data.get('historical_accuracy', {})
            self.last_adjusted = data.get('last_adjusted')
            self.adjustment_count = data.get('adjustment_count', 0)
            
            logger.info(f"Loaded weights: {self.weights}")
            
        except Exception as e:
            logger.error(f"Failed to load weights: {e}")
    
    def _save_weights(self):
        """Save weights to file"""
        try:
            data = {
                'current_weights': self.weights,
                'historical_accuracy': self.historical_accuracy,
                'last_adjusted': self.last_adjusted,
                'adjustment_count': self.adjustment_count
            }
            
            with open(self.weights_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save weights: {e}")
    
    def get_weights(self) -> Dict[str, int]:
        """Get current scoring weights"""
        return self.weights.copy()
    
    def update_weights(self, factor_scores: Dict[str, int], outcomes: List) -> Dict[str, int]:
        """
        Update weights based on factor performance
        
        Args:
            factor_scores: Dict of factor -> score for each signal
            outcomes: List of resolved SignalOutcome
            
        Returns:
            Updated weights dict
        """
        if not self.enabled:
            return self.weights
        
        if len(outcomes) < self.min_signals:
            logger.info(f"Not enough outcomes ({len(outcomes)}) to adjust weights (need {self.min_signals})")
            return self.weights
        
        # Calculate historical accuracy per factor
        # (Simplified - in production you'd track which factors each signal had)
        factor_accuracy = self._calculate_factor_accuracy(outcomes)
        
        if not factor_accuracy:
            return self.weights
        
        # Calculate weight adjustments
        new_weights = self.weights.copy()
        
        # Find factors with high accuracy (above average)
        avg_accuracy = sum(factor_accuracy.values()) / len(factor_accuracy) if factor_accuracy else 0
        
        for factor, accuracy in factor_accuracy.items():
            if factor not in self.weights:
                continue
            
            # Calculate adjustment
            diff = accuracy - avg_accuracy
            
            # Apply dampening
            adjustment = (diff * self.dampening) / 10  # Normalize to max ~5% change
            
            # Apply max monthly limit
            adjustment = max(-self.max_monthly_adjustment, min(self.max_monthly_adjustment, adjustment))
            
            # Apply change
            new_weights[factor] = max(5, min(40, self.weights[factor] + int(adjustment)))
        
        # Normalize weights to sum to 100
        new_weights = self._normalize_weights(new_weights)
        
        # Check if weights actually changed
        if new_weights != self.weights:
            self.weights = new_weights
            self.last_adjusted = datetime.now().isoformat()
            self.adjustment_count += 1
            self.historical_accuracy = factor_accuracy
            self._save_weights()
            
            logger.info(f"Adjusted weights: {self.weights}")
        
        return self.weights
    
    def _calculate_factor_accuracy(self, outcomes: List) -> Dict[str, float]:
        """
        Calculate accuracy percentage for each scoring factor
        This is a simplified estimation based on confidence score correlations
        """
        factor_accuracy = {}
        
        if not outcomes:
            return factor_accuracy
        
        # Split outcomes by confidence ranges
        high_conf = [o for o in outcomes if o.confidence_score >= 75]
        mid_conf = [o for o in outcomes if 60 <= o.confidence_score < 75]
        low_conf = [o for o in outcomes if o.confidence_score < 60]
        
        # Estimate factor accuracy based on win rates in different confidence ranges
        # This is a heuristic - in production you'd track actual factors per signal
        logger.warning(
            "Learning Engine: Using heuristic-based factor accuracy estimation. "
            "For production use, implement proper factor tracking per signal."
        )

        def calc_win_rate(group):
            if not group:
                return 50.0  # Default
            wins = len([o for o in group if 'target' in o.outcome])
            return (wins / len(group)) * 100
        
        high_rate = calc_win_rate(high_conf)
        mid_rate = calc_win_rate(mid_conf)
        low_rate = calc_win_rate(low_conf)
        
        # Factors typically associated with high confidence signals
        # (This is a simplified heuristic)
        factor_accuracy['price_structure'] = high_rate if high_conf else 60
        factor_accuracy['volume_behavior'] = high_rate if high_conf else 65
        factor_accuracy['support_strength'] = high_rate if len(high_conf) > 3 else 60
        factor_accuracy['delivery_data'] = mid_rate if len(mid_conf) > 3 else 55
        factor_accuracy['relative_strength'] = high_rate if len(high_conf) > 2 else 60
        factor_accuracy['volatility_compression'] = mid_rate if len(mid_conf) > 2 else 55
        factor_accuracy['ma_behavior'] = low_rate if len(low_conf) > 5 else 55
        
        return factor_accuracy
    
    def _normalize_weights(self, weights: Dict[str, int]) -> Dict[str, int]:
        """Normalize weights to sum to 100"""
        total = sum(weights.values())
        
        if total == 0:
            return self.DEFAULT_WEIGHTS.copy()
        
        # Normalize
        normalized = {}
        for k, v in weights.items():
            normalized[k] = int((v / total) * 100)
        
        # Adjust for rounding errors
        diff = 100 - sum(normalized.values())
        if diff != 0:
            # Add/subtract from largest weight
            max_key = max(normalized, key=normalized.get)
            normalized[max_key] += diff
        
        return normalized
    
    def reset_to_defaults(self):
        """Reset weights to defaults"""
        self.weights = self.DEFAULT_WEIGHTS.copy()
        self.historical_accuracy = {}
        self.last_adjusted = None
        self.adjustment_count = 0
        self._save_weights()
        logger.info("Weights reset to defaults")


def create_learning_engine(config: Dict) -> LearningEngine:
    """Factory function to create learning engine"""
    return LearningEngine(config)
"""
AI Scoring Model
Assigns confidence scores (0-100) to stocks based on accumulation factors
"""

from typing import Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class StockScore:
    """Scored stock with confidence metrics"""
    stock_symbol: str
    total_score: int
    
    # Component scores
    price_structure_score: int
    volume_behavior_score: int
    delivery_data_score: int
    support_strength_score: int
    relative_strength_score: int
    volatility_compression_score: int
    ma_behavior_score: int
    
    # Classification
    classification: str  # 'Strong', 'Moderate', 'Weak'
    recommendation: str  # 'Buy', 'Watch', 'Skip'
    
    # Details
    positive_factors: List[str]
    negative_factors: List[str]


class AIScoringModel:
    """
    AI-powered scoring model for accumulation detection
    Uses weighted scoring based on the PRD specification
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.scoring_config = config.get('scoring', {})
        self.weights = self.scoring_config.get('weights', {
            'price_structure': 20,
            'volume_behavior': 20,
            'delivery_data': 15,
            'support_strength': 15,
            'relative_strength': 10,
            'volatility_compression': 10,
            'ma_behavior': 10
        })
        
        thresholds = self.scoring_config.get('thresholds', {})
        self.strong_threshold = thresholds.get('strong_setup', 80)
        self.moderate_threshold = thresholds.get('moderate_setup', 60)
    
    def score_signal(self, signal) -> StockScore:
        """
        Score an AccumulationSignal
        
        Args:
            signal: AccumulationSignal from detector
            
        Returns:
            StockScore with detailed scoring
        """
        scores = {}
        positive_factors = []
        negative_factors = []
        
        # 1. Price Structure Score (0-20)
        scores['price_structure'] = self._score_price_structure(signal)
        if scores['price_structure'] >= 15:
            positive_factors.append("Strong consolidation phase")
        elif scores['price_structure'] < 10:
            negative_factors.append("No clear consolidation")
        
        # 2. Volume Behavior Score (0-20)
        scores['volume_behavior'] = self._score_volume_behavior(signal)
        if scores['volume_behavior'] >= 15:
            positive_factors.append("Volume accumulation detected")
        elif scores['volume_behavior'] < 10:
            negative_factors.append("Weak volume patterns")
        
        # 3. Delivery Data Score (0-15)
        scores['delivery_data'] = self._score_delivery_data(signal)
        if scores['delivery_data'] >= 12:
            positive_factors.append("Rising delivery percentage")
        elif scores['delivery_data'] < 8:
            negative_factors.append("Delivery data not supportive")
        
        # 4. Support Strength Score (0-15)
        scores['support_strength'] = self._score_support_strength(signal)
        if scores['support_strength'] >= 12:
            positive_factors.append(f"Strong support at ₹{signal.support_level:.2f}")
        elif scores['support_strength'] < 8:
            weak_support = f"Weak support ({signal.support_touches} touches)"
            negative_factors.append(weak_support)
        
        # 5. Relative Strength Score (0-10)
        scores['relative_strength'] = self._score_relative_strength(signal)
        if scores['relative_strength'] >= 8:
            positive_factors.append("Outperforming the index")
        elif scores['relative_strength'] < 5:
            negative_factors.append("Underperforming the index")
        
        # 6. Volatility Compression Score (0-10)
        scores['volatility_compression'] = self._score_volatility(signal)
        if scores['volatility_compression'] >= 8:
            positive_factors.append("Volatility compression detected")
        
        # 7. Moving Average Behavior Score (0-10)
        scores['ma_behavior'] = self._score_ma_behavior(signal)
        if scores['ma_behavior'] >= 8:
            positive_factors.append("Price above flattening 50 DMA")
        elif scores['ma_behavior'] < 5:
            negative_factors.append("MA trend not favorable")
        
        # Calculate total score
        total_score = 0
        for factor, score in scores.items():
            weight = self.weights.get(factor, 0)
            total_score += int(score * weight / 100)
        
        # Normalize to 0-100
        total_score = min(100, total_score)
        
        # Classification
        if total_score >= self.strong_threshold:
            classification = "Strong Accumulation"
            recommendation = "Buy"
        elif total_score >= self.moderate_threshold:
            classification = "Moderate Setup"
            recommendation = "Watch"
        else:
            classification = "Weak Setup"
            recommendation = "Skip"
        
        return StockScore(
            stock_symbol=signal.stock_symbol,
            total_score=total_score,
            price_structure_score=scores['price_structure'],
            volume_behavior_score=scores['volume_behavior'],
            delivery_data_score=scores['delivery_data'],
            support_strength_score=scores['support_strength'],
            relative_strength_score=scores['relative_strength'],
            volatility_compression_score=scores['volatility_compression'],
            ma_behavior_score=scores['ma_behavior'],
            classification=classification,
            recommendation=recommendation,
            positive_factors=positive_factors,
            negative_factors=negative_factors
        )
    
    def _score_price_structure(self, signal) -> int:
        """Score price structure (consolidation)"""
        score = 0
        
        if signal.in_range:
            score += 10
            
            # Bonus for tight range
            if signal.range_high > 0:
                range_pct = (signal.range_high - signal.range_low) / signal.range_high * 100
                if range_pct < 15:
                    score += 5
                elif range_pct < 20:
                    score += 3
                else:
                    score += 1
                    
            # Bonus for longer consolidation
            if signal.range_days >= 60:
                score += 5
            elif signal.range_days >= 45:
                score += 3
            elif signal.range_days >= 30:
                score += 1
        
        return min(20, score)
    
    def _score_volume_behavior(self, signal) -> int:
        """Score volume behavior"""
        score = 0
        
        if signal.up_volume_ratio > 1:
            score += 8
            
            # Bonus for strong up volume ratio
            if signal.up_volume_ratio > 1.5:
                score += 5
            elif signal.up_volume_ratio > 1.2:
                score += 3
        
        if signal.volume_spike_near_support:
            score += 7
        
        return min(20, score)
    
    def _score_delivery_data(self, signal) -> int:
        """Score delivery percentage (India-specific)"""
        score = 0
        
        if signal.delivery_trend == 'increasing':
            score += 8
            
        if signal.delivery_current >= 50:
            score += 4
            
        if signal.delivery_current >= 60:
            score += 3
        
        return min(15, score)
    
    def _score_support_strength(self, signal) -> int:
        """Score support level strength"""
        score = 0
        
        score += min(signal.support_touches * 3, 9)  # Max 9 points for touches
        
        # Check if price is near support
        if signal.support_level > 0:
            distance_pct = (signal.current_price - signal.support_level) / signal.current_price * 100
            if distance_pct < 3:
                score += 6
            elif distance_pct < 5:
                score += 3
        
        return min(15, score)
    
    def _score_relative_strength(self, signal) -> int:
        """Score relative strength vs index"""
        score = 0
        
        if signal.rs_trend == 'positive':
            score += 7
            
            if signal.rs_ratio > 1.5:
                score += 3
        elif signal.rs_trend == 'neutral':
            score += 3
        
        return min(10, score)
    
    def _score_volatility(self, signal) -> int:
        """Score volatility compression"""
        score = 0
        
        if signal.atr_trend == 'declining':
            score += 8
        elif signal.atr_trend == 'stable':
            score += 4
        
        return min(10, score)
    
    def _score_ma_behavior(self, signal) -> int:
        """Score moving average behavior"""
        score = 0
        
        if signal.price_above_ma50:
            score += 4
            
        if signal.ma50_trend in ['up', 'flat']:
            score += 6
            
            if signal.ma50_trend == 'up':
                score += 2
        
        return min(10, score)
    
    def score_all_signals(
        self, 
        signals: List
    ) -> List[StockScore]:
        """
        Score all accumulation signals
        
        Args:
            signals: List of AccumulationSignal objects
            
        Returns:
            List of StockScore objects sorted by score (descending)
        """
        scores = []
        
        for signal in signals:
            try:
                score = self.score_signal(signal)
                scores.append(score)
            except Exception as e:
                logger.error(f"Error scoring {signal.stock_symbol}: {str(e)}")
                continue
        
        # Sort by total score descending
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        return scores


def get_top_stocks(
    scored_stocks: List[StockScore],
    min_score: int = 60,
    limit: int = 10
) -> List[StockScore]:
    """
    Get top stocks filtered by minimum score
    
    Args:
        scored_stocks: List of scored stocks
        min_score: Minimum score threshold
        limit: Maximum number of stocks to return
        
    Returns:
        Filtered and limited list of stocks
    """
    filtered = [s for s in scored_stocks if s.total_score >= min_score]
    return filtered[:limit]

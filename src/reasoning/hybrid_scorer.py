"""
Hybrid Scorer - Combines Rule-Based + AI Reasoning
Part of the Reasoning Engine
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Result from the hybrid reasoning engine"""
    stock_symbol: str
    total_score: int  # Combined score 0-100
    rule_score: int  # Rule-based score 0-100
    ai_score: Optional[int]  # AI-based score 0-100 (None if unavailable)
    confidence_level: str  # 'high', 'medium', 'low'
    reasoning_text: str  # Human-readable explanation
    positive_factors: List[str]
    negative_factors: List[str]
    ai_insights: List[str]  # AI-specific observations
    timestamp: str


class HybridScorer:
    """
    Hybrid scoring engine combining rule-based algorithms with AI reasoning
    """
    
    def __init__(self, config: Dict):
        self.config = config
        reasoning_config = config.get('reasoning', {})
        
        # Enable/disable reasoning engine
        self.enabled = reasoning_config.get('enabled', True)
        
        # Hybrid weights
        hybrid_weights = reasoning_config.get('hybrid_weights', {})
        self.rule_weight = hybrid_weights.get('rule_based', 60) / 100
        self.ai_weight = hybrid_weights.get('ai_reasoning', 40) / 100
        
        # Validate weights sum to 1.0
        total_weight = self.rule_weight + self.ai_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Hybrid weights sum to {total_weight:.2f}, normalizing to 1.0")
            self.rule_weight = self.rule_weight / total_weight
            self.ai_weight = self.ai_weight / total_weight
        
        # AI reasoner settings
        ai_reasoner = reasoning_config.get('ai_reasoner', {})
        self.ai_enabled = ai_reasoner.get('enabled', True)
        self.ai_min_threshold = ai_reasoner.get('min_confidence_threshold', 50)
        
        # Explanation settings
        explanation = reasoning_config.get('explanation', {})
        self.include_explanation = explanation.get('include_in_telegram', True)
        self.max_explanation_length = explanation.get('max_length', 500)
        
        # Initialize components
        self.rule_scorer = None
        self.ai_reasoner = None
        
        if self.enabled:
            self._init_components()
    
    def _init_components(self):
        """Initialize rule-based and AI reasoners"""
        # Import here to avoid circular dependencies
        try:
            from src.scoring.ai_scorer import AIScoringModel
            self.rule_scorer = AIScoringModel(config=self.config)
            logger.info("Rule-based scorer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize rule scorer: {e}")
        
        # Initialize AI reasoner
        if self.ai_enabled:
            try:
                from src.reasoning.ai_reasoner import AIReasoner
                self.ai_reasoner = AIReasoner(self.config)
                logger.info("AI reasoner initialized")
            except Exception as e:
                logger.warning(f"AI reasoner not available: {e}")
                self.ai_reasoner = None
    
    def score_signal(self, signal) -> ReasoningResult:
        """
        Score an accumulation signal using hybrid approach
        
        Args:
            signal: AccumulationSignal from detector
            
        Returns:
            ReasoningResult with combined scoring
        """
        if not self.enabled:
            # Fallback to simple rule-based scoring
            return self._fallback_score(signal)
        
        # Get rule-based score
        rule_score, positive, negative = self._get_rule_score(signal)
        
        # Get AI score (if available)
        ai_score = None
        ai_insights = []
        if self.ai_reasoner and self.ai_reasoner.is_available():
            try:
                ai_result = self.ai_reasoner.analyze(signal)
                if ai_result:
                    ai_score = ai_result.get('score')
                    ai_insights = ai_result.get('insights', [])
            except Exception as e:
                logger.warning(f"AI reasoning failed for {signal.stock_symbol}: {e}")
        
        # Calculate hybrid score
        total_score = self._calculate_hybrid_score(rule_score, ai_score)
        
        # Determine confidence level
        confidence = self._determine_confidence(total_score, ai_score)
        
        # Generate reasoning text
        reasoning_text = self._generate_reasoning(
            signal, rule_score, ai_score, positive, negative, ai_insights
        )
        
        return ReasoningResult(
            stock_symbol=signal.stock_symbol,
            total_score=total_score,
            rule_score=rule_score,
            ai_score=ai_score,
            confidence_level=confidence,
            reasoning_text=reasoning_text,
            positive_factors=positive,
            negative_factors=negative,
            ai_insights=ai_insights,
            timestamp=datetime.now().isoformat()
        )
    
    def _get_rule_score(self, signal) -> tuple:
        """Get rule-based score using existing AIScoringModel"""
        if not self.rule_scorer:
            # Fallback to simple scoring
            return self._simple_rule_score(signal)
        
        try:
            stock_score = self.rule_scorer.score_signal(signal)
            return (
                stock_score.total_score,
                stock_score.positive_factors,
                stock_score.negative_factors
            )
        except Exception as e:
            logger.error(f"Rule scoring failed: {e}")
            return self._simple_rule_score(signal)
    
    def _simple_rule_score(self, signal) -> tuple:
        """Simple fallback rule-based scoring"""
        score = 0
        positive = []
        negative = []
        
        # Price structure (max 20)
        if signal.in_range:
            score += 15
            positive.append("Strong consolidation phase")
        
        # Support strength (max 15)
        if signal.support_touches >= 3:
            score += 12
            positive.append(f"Strong support ({signal.support_touches} touches)")
        
        # Volume pattern (max 20)
        if signal.up_volume_ratio > 1:
            score += 10
            if signal.up_volume_ratio > 1.5:
                score += 5
                positive.append("Volume accumulation detected")
        
        # Delivery (max 15)
        if signal.delivery_trend == 'increasing':
            score += 10
            positive.append("Rising delivery percentage")
        
        # MA behavior (max 10)
        if signal.price_above_ma50 and signal.ma50_trend in ['up', 'flat']:
            score += 8
            positive.append("Price above key moving average")
        
        # Volatility (max 10)
        if signal.atr_trend == 'declining':
            score += 8
            positive.append("Volatility compression")
        
        # Relative strength (max 10)
        if signal.rs_trend == 'positive':
            score += 7
            positive.append("Outperforming market index")
        
        # Normalize to 0-100 (max possible is ~85)
        score = int(score / 85 * 100)
        
        return score, positive, negative
    
    def _calculate_hybrid_score(self, rule_score: int, ai_score: Optional[int]) -> int:
        """Calculate combined hybrid score"""
        if ai_score is None:
            # Use rule score only
            return rule_score
        
        # Calculate weighted average
        total = (rule_score * self.rule_weight) + (ai_score * self.ai_weight)
        return int(round(total))
    
    def _determine_confidence(self, total_score: int, ai_score: Optional[int]) -> str:
        """Determine confidence level based on scores"""
        if ai_score is not None and ai_score >= self.ai_min_threshold:
            # High confidence - both methods agree
            if abs(total_score - ai_score) < 15:
                return 'high'
            elif abs(total_score - ai_score) < 30:
                return 'medium'
        
        # Medium confidence - rule-based only or disagreement
        if total_score >= 75:
            return 'medium'
        return 'low'
    
    def _generate_reasoning(
        self,
        signal,
        rule_score: int,
        ai_score: Optional[int],
        positive: List[str],
        negative: List[str],
        ai_insights: List[str]
    ) -> str:
        """Generate human-readable reasoning explanation"""
        lines = []
        
        # Header
        lines.append(f"📊 Score: {rule_score}/100 (Rule-Based)")
        if ai_score is not None:
            lines.append(f"🤖 Score: {ai_score}/100 (AI Analysis)")
            lines.append(f"✨ Combined: {res.total_score}/100")
        
        lines.append("")
        
        # Key observations
        if positive:
            lines.append("✅ Key Factors:")
            for factor in positive[:5]:
                lines.append(f"   • {factor}")
        
        if negative:
            lines.append("⚠️ Concerns:")
            for factor in negative[:3]:
                lines.append(f"   • {factor}")
        
        # AI insights
        if ai_insights:
            lines.append("")
            lines.append("🧠 AI Insights:")
            for insight in ai_insights[:3]:
                lines.append(f"   → {insight}")
        
        # Technical details
        lines.append("")
        if signal.in_range:
            range_pct = ((signal.range_high - signal.range_low) / signal.range_high * 100) if signal.range_high > 0 else 0
            lines.append(f"📈 Range: {signal.range_days} days, {range_pct:.1f}% width")
        
        if signal.near_breakout:
            lines.append(f"🎯 Near breakout: {signal.breakout_distance_pct:.1f}% to resistance")
        
        if signal.support_touches > 0:
            lines.append(f"🛡️ Support: ₹{signal.support_level:.2f} ({signal.support_touches} touches)")
        
        # Truncate if needed
        reasoning = "\n".join(lines)
        if len(reasoning) > self.max_explanation_length:
            reasoning = reasoning[:self.max_explanation_length - 3] + "..."
        
        return reasoning
    
    def _fallback_score(self, signal) -> ReasoningResult:
        """Fallback when reasoning is disabled"""
        score, positive, negative = self._simple_rule_score(signal)
        
        return ReasoningResult(
            stock_symbol=signal.stock_symbol,
            total_score=score,
            rule_score=score,
            ai_score=None,
            confidence_level='medium' if score >= 60 else 'low',
            reasoning_text=self._generate_reasoning(signal, score, None, positive, negative, []),
            positive_factors=positive,
            negative_factors=negative,
            ai_insights=[],
            timestamp=datetime.now().isoformat()
        )
    
    def score_all_signals(self, signals: List) -> List[ReasoningResult]:
        """Score all accumulation signals"""
        results = []
        
        for signal in signals:
            try:
                result = self.score_signal(signal)
                results.append(result)
            except Exception as e:
                logger.error(f"Error scoring {signal.stock_symbol}: {e}")
                continue
        
        # Sort by total score
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results


def create_hybrid_scorer(config: Dict) -> HybridScorer:
    """Factory function to create hybrid scorer"""
    return HybridScorer(config)
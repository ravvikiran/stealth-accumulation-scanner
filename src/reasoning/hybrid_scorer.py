"""
Hybrid Scorer - Combines Rule-Based + AI Reasoning
Part of the Reasoning Engine
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """Result from the hybrid reasoning engine"""
    stock_symbol: str
    total_score: int
    rule_score: int
    ai_score: Optional[int]
    confidence_level: str
    reasoning_text: str
    positive_factors: List[str]
    negative_factors: List[str]
    ai_insights: List[str]
    timestamp: str
    rank_score: float = 0.0
    classification: str = "Ignore"
    recommendation: str = "Skip"
    factor_scores: Optional[Dict[str, int]] = None


class HybridScorer:
    """
    Hybrid scoring engine combining rule-based algorithms with AI reasoning.
    Rule-based score remains primary; AI adds explanation/context.
    """

    def __init__(self, config: Dict):
        self.config = config
        reasoning_config = config.get('reasoning', {})

        self.enabled = reasoning_config.get('enabled', True)

        explanation = reasoning_config.get('explanation', {})
        self.include_explanation = explanation.get('include_in_telegram', True)
        self.max_explanation_length = explanation.get('max_length', 500)

        self.rule_scorer = None
        self.ai_reasoner = None
        self.ai_enabled = reasoning_config.get('ai_reasoner', {}).get('enabled', True)

        if self.enabled:
            self._init_components()

    def _init_components(self):
        """Initialize rule-based and AI reasoners"""
        try:
            from src.scoring.ai_scorer import AIScoringModel
            self.rule_scorer = AIScoringModel(config=self.config)
            logger.info("Rule-based scorer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize rule scorer: {e}")

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
        Score signal with rule-based engine and optional AI explanation.
        AI must not replace or distort factor scores.
        """
        if not self.rule_scorer:
            return self._fallback_score(signal)

        stock_score = self.rule_scorer.score_signal(signal)

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

        reasoning_text = self._generate_reasoning(
            signal=signal,
            stock_score=stock_score,
            ai_score=ai_score,
            ai_insights=ai_insights
        )

        return ReasoningResult(
            stock_symbol=stock_score.stock_symbol,
            total_score=stock_score.total_score,
            rule_score=stock_score.total_score,
            ai_score=ai_score,
            confidence_level=self._determine_confidence(stock_score.total_score, ai_score),
            reasoning_text=reasoning_text,
            positive_factors=stock_score.positive_factors,
            negative_factors=stock_score.negative_factors,
            ai_insights=ai_insights,
            timestamp=datetime.now().isoformat(),
            rank_score=stock_score.rank_score,
            classification=stock_score.classification,
            recommendation=stock_score.recommendation,
            factor_scores={
                'price_structure_score': stock_score.price_structure_score,
                'volume_behavior_score': stock_score.volume_behavior_score,
                'delivery_data_score': stock_score.delivery_data_score,
                'support_strength_score': stock_score.support_strength_score,
                'relative_strength_score': stock_score.relative_strength_score,
                'volatility_compression_score': stock_score.volatility_compression_score,
                'ma_behavior_score': stock_score.ma_behavior_score
            }
        )

    def _determine_confidence(self, total_score: int, ai_score: Optional[int]) -> str:
        """Determine confidence level"""
        if total_score >= 75:
            return 'high'
        if total_score >= 60:
            return 'medium'
        if ai_score is not None and ai_score >= 60:
            return 'medium'
        return 'low'

    def _generate_reasoning(self, signal, stock_score, ai_score: Optional[int], ai_insights: List[str]) -> str:
        """Generate human-readable explanation"""
        lines = [
            f"📊 Rule Score: {stock_score.total_score}/100",
            f"🏷️ Classification: {stock_score.classification}",
            ""
        ]

        if stock_score.positive_factors:
            lines.append("✅ Key Factors:")
            for factor in stock_score.positive_factors[:5]:
                lines.append(f"   • {factor}")

        if stock_score.negative_factors:
            lines.append("⚠️ Concerns:")
            for factor in stock_score.negative_factors[:3]:
                lines.append(f"   • {factor}")

        if ai_score is not None:
            lines.append("")
            lines.append(f"🤖 AI Context Score: {ai_score}/100")

        if ai_insights:
            lines.append("🧠 AI Insights:")
            for insight in ai_insights[:3]:
                lines.append(f"   → {insight}")

        lines.append("")
        lines.append(
            f"📐 Factors: PS {stock_score.price_structure_score}, "
            f"VB {stock_score.volume_behavior_score}, "
            f"SS {stock_score.support_strength_score}, "
            f"RS {stock_score.relative_strength_score}"
        )

        if getattr(signal, 'near_breakout', False):
            lines.append(f"🎯 Near breakout: {getattr(signal, 'breakout_distance_pct', 0):.1f}% to resistance")

        reasoning = "\n".join(lines)
        if len(reasoning) > self.max_explanation_length:
            reasoning = reasoning[:self.max_explanation_length - 3] + "..."
        return reasoning

    def _fallback_score(self, signal) -> ReasoningResult:
        """Fallback when scorer unavailable"""
        return ReasoningResult(
            stock_symbol=signal.stock_symbol,
            total_score=0,
            rule_score=0,
            ai_score=None,
            confidence_level='low',
            reasoning_text="Rule scorer unavailable",
            positive_factors=[],
            negative_factors=["Rule scorer unavailable"],
            ai_insights=[],
            timestamp=datetime.now().isoformat(),
            rank_score=0.0,
            classification="Ignore",
            recommendation="Skip",
            factor_scores={}
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

        results.sort(
            key=lambda x: (
                x.rank_score,
                x.total_score
            ),
            reverse=True
        )
        return results


def create_hybrid_scorer(config: Dict) -> HybridScorer:
    """Factory function to create hybrid scorer"""
    return HybridScorer(config)
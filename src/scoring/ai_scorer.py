"""
AI Scoring Model
Assigns confidence scores (0-100) to stocks based on accumulation factors
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


FACTOR_MAXES = {
    "price_structure": 20,
    "volume_behavior": 20,
    "delivery_data": 15,
    "support_strength": 15,
    "relative_strength": 10,
    "volatility_compression": 10,
    "ma_behavior": 10,
}


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
    classification: str  # 'Strong', 'Moderate', 'Early', 'Ignore'
    recommendation: str  # 'Buy', 'Watch', 'Track', 'Skip'

    # Details
    positive_factors: List[str]
    negative_factors: List[str]
    factor_scores: Dict[str, int] = field(default_factory=dict)
    weak_factors: List[str] = field(default_factory=list)
    weak_factor_penalty_applied: bool = False
    setup_boost_applied: bool = False
    pre_penalty_score: int = 0
    rank_score: float = 0.0


class AIScoringModel:
    """
    Rule-based scoring model aligned to the PRD specification.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.scoring_config = config.get("scoring", {})
        self.weights = FACTOR_MAXES

    def score_signal(self, signal) -> StockScore:
        """
        Score an AccumulationSignal
        """
        scores = {
            "price_structure": self._score_price_structure(signal),
            "volume_behavior": self._score_volume_behavior(signal),
            "delivery_data": self._score_delivery_data(signal),
            "support_strength": self._score_support_strength(signal),
            "relative_strength": self._score_relative_strength(signal),
            "volatility_compression": self._score_volatility(signal),
            "ma_behavior": self._score_ma_behavior(signal),
        }

        positive_factors: List[str] = []
        negative_factors: List[str] = []

        if scores["price_structure"] >= 14:
            positive_factors.append("Healthy consolidation range")
        elif scores["price_structure"] == 0:
            negative_factors.append("No valid accumulation range")

        if scores["volume_behavior"] >= 14:
            positive_factors.append("Constructive volume compression with support demand")
        elif scores["volume_behavior"] == 0:
            negative_factors.append("Chaotic or unsupportive volume behavior")

        if scores["delivery_data"] == 15:
            positive_factors.append("Strong delivery participation")
        elif scores["delivery_data"] == 7:
            positive_factors.append("Delivery data unavailable; treated neutral")
        elif scores["delivery_data"] == 0:
            negative_factors.append("Weak delivery participation")

        if scores["support_strength"] >= 9:
            positive_factors.append(f"Support tested {signal.support_touches} times")
        elif scores["support_strength"] <= 4:
            negative_factors.append("Support not established enough")

        if scores["relative_strength"] == 10:
            positive_factors.append("Outperforming the index clearly")
        elif scores["relative_strength"] == 0:
            negative_factors.append("Lagging the index materially")

        if scores["volatility_compression"] == 10:
            positive_factors.append("Volatility is compressing")
        elif scores["volatility_compression"] == 0:
            negative_factors.append("Volatility is expanding")

        if scores["ma_behavior"] >= 7:
            positive_factors.append("Price behavior around 50DMA is constructive")
        elif scores["ma_behavior"] == 0:
            negative_factors.append("50DMA behavior is unfavorable")

        base_total = sum(scores.values())
        weak_factors = [
            factor for factor, value in scores.items()
            if value < FACTOR_MAXES[factor] * 0.4
        ]

        weak_factor_penalty_applied = len(weak_factors) >= 3
        total_score = float(base_total)

        if weak_factor_penalty_applied:
            total_score *= 0.85

        setup_boost_applied = (
            scores["price_structure"] >= 14 and scores["volume_behavior"] >= 14
        )
        if setup_boost_applied:
            total_score += 5

        total_score = min(100, int(round(total_score)))

        if total_score >= 75:
            classification = "Strong"
            recommendation = "Buy"
        elif total_score >= 60:
            classification = "Moderate"
            recommendation = "Watch"
        elif total_score >= 50:
            classification = "Early"
            recommendation = "Track"
        else:
            classification = "Ignore"
            recommendation = "Skip"

        return StockScore(
            stock_symbol=signal.stock_symbol,
            total_score=total_score,
            price_structure_score=scores["price_structure"],
            volume_behavior_score=scores["volume_behavior"],
            delivery_data_score=scores["delivery_data"],
            support_strength_score=scores["support_strength"],
            relative_strength_score=scores["relative_strength"],
            volatility_compression_score=scores["volatility_compression"],
            ma_behavior_score=scores["ma_behavior"],
            classification=classification,
            recommendation=recommendation,
            positive_factors=positive_factors,
            negative_factors=negative_factors,
            factor_scores=scores,
            weak_factors=weak_factors,
            weak_factor_penalty_applied=weak_factor_penalty_applied,
            setup_boost_applied=setup_boost_applied,
            pre_penalty_score=base_total,
            rank_score=0.0,
        )

    def _score_price_structure(self, signal) -> int:
        """Price structure <15 => 20, 15-25 => 14, 25-35 => 8, >35 => 0."""
        if not signal.in_range or signal.range_pct <= 0:
            return 0

        if signal.range_pct < 15:
            return 20
        if signal.range_pct <= 25:
            return 14
        if signal.range_pct <= 35:
            return 8
        return 0

    def _score_volume_behavior(self, signal) -> int:
        """Volume 20/10/0 based on compression+spikes/stable/chaotic."""
        constructive_pattern = signal.volume_pattern in ["declining", "stable"]

        if signal.volume_pattern == "chaotic":
            return 0

        if signal.volume_pattern == "declining" and signal.volume_spike_near_support:
            return 20

        if constructive_pattern:
            return 10

        return 0

    def _score_delivery_data(self, signal) -> int:
        """Delivery 15/8/0/7 neutral if missing."""
        if not getattr(signal, "delivery_available", False) or signal.delivery_trend == "missing":
            return 7

        if signal.delivery_trend == "increasing" and signal.delivery_current >= 50:
            return 15

        if signal.delivery_trend == "stable" and signal.delivery_current >= 45:
            return 8

        return 0

    def _score_support_strength(self, signal) -> int:
        """Support >=3 => 15, 2 => 9, 1 => 4, 0 => 0."""
        touches = int(getattr(signal, "support_touches", 0))

        if touches >= 3:
            return 15
        if touches == 2:
            return 9
        if touches == 1:
            return 4
        return 0

    def _score_relative_strength(self, signal) -> int:
        """RS 10/6/0 for >+3, -2 to +3, < -2."""
        outperformance = getattr(signal, "rs_outperformance_pct", getattr(signal, "rs_ratio", 0.0))

        if outperformance > 3:
            return 10
        if outperformance >= -2:
            return 6
        return 0

    def _score_volatility(self, signal) -> int:
        """Volatility 10/6/0 for declining/flat/rising ATR."""
        if signal.atr_trend == "declining":
            return 10
        if signal.atr_trend == "stable":
            return 6
        return 0

    def _score_ma_behavior(self, signal) -> int:
        """MA 10/7/5/0 - above+up=10, above+flat=7, near=5, else=0."""
        if signal.price_above_ma50 and signal.ma50_trend == "up":
            return 10
        if signal.price_above_ma50 and signal.ma50_trend == "flat":
            return 7
        if getattr(signal, "near_ma50", False):
            return 5
        return 0

    def score_all_signals(self, signals: List) -> List[StockScore]:
        """
        Score all accumulation signals
        """
        scores = []

        for signal in signals:
            try:
                score = self.score_signal(signal)
                scores.append(score)
            except Exception as e:
                logger.error(f"Error scoring {signal.stock_symbol}: {str(e)}")
                continue

        scores.sort(key=lambda x: x.total_score, reverse=True)
        return scores


def get_top_stocks(
    scored_stocks: List[StockScore],
    min_score: int = 60,
    limit: int = 3,
) -> List[StockScore]:
    """
    Apply PRD ranking, quality gate, and return max top candidates.
    """
    candidates: List[StockScore] = []

    for stock in scored_stocks:
        stock.rank_score = (
            stock.total_score * 0.6
            + stock.volume_behavior_score * 0.15
            + stock.price_structure_score * 0.15
            + stock.relative_strength_score * 0.1
        )

        if stock.total_score < min_score:
            continue

        if stock.price_structure_score < 10 or stock.volume_behavior_score < 10:
            continue

        candidates.append(stock)

    candidates.sort(key=lambda s: (s.rank_score, s.total_score), reverse=True)
    return candidates[:limit]

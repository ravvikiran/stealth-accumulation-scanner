import pandas as pd
import pytest

from src.scanner.accumulation_detector import AccumulationDetector, AccumulationSignal
from src.scoring.ai_scorer import AIScoringModel


def make_config():
    return {
        "scanner": {
            "thresholds": {
                "max_range_percentage": 25,
                "support_deviation": 2,
                "resistance_proximity": 5,
            },
            "lookback": {
                "min_range_days": 30,
                "max_range_days": 90,
                "volume_analysis_days": 20,
                "delivery_analysis_days": 10,
                "rs_analysis_days": 20,
            },
        },
        "scoring": {
            "weights": {
                "price_structure": 20,
                "volume_behavior": 20,
                "delivery_data": 15,
                "support_strength": 15,
                "relative_strength": 10,
                "volatility_compression": 10,
                "ma_behavior": 10,
            },
            "thresholds": {
                "strong_setup": 80,
                "moderate_setup": 60,
            },
        },
    }


def make_signal(**overrides):
    base = {
        "stock_symbol": "TEST",
        "current_price": 100.0,
        "in_range": True,
        "range_high": 102.0,
        "range_low": 98.0,
        "range_days": 60,
        "support_level": 98.0,
        "support_touches": 5,
        "resistance_level": 102.0,
        "atr_current": 1.0,
        "atr_trend": "declining",
        "up_volume_ratio": 1.8,
        "volume_spike_near_support": True,
        "delivery_trend": "increasing",
        "delivery_current": 65.0,
        "rs_ratio": 0.05,
        "rs_trend": "positive",
        "price_above_ma50": True,
        "ma50_slope": 0.02,
        "ma50_trend": "up",
        "near_breakout": True,
        "breakout_distance_pct": 1.0,
        "accumulation_detected": True,
        "confidence_factors": {
            "price_structure": True,
            "support_strength": True,
            "volume_pattern": True,
            "ma_behavior": True,
        },
    }
    base.update(overrides)
    return AccumulationSignal(**base)


def make_detector():
    return AccumulationDetector(make_config())


def make_scorer():
    return AIScoringModel(make_config())


def test_perfect_signal_scores_100():
    scorer = make_scorer()
    signal = make_signal()

    score = scorer.score_signal(signal)

    assert score.total_score == 100


def test_missing_delivery_is_neutral_and_does_not_reject():
    scorer = make_scorer()
    signal = make_signal(delivery_trend="stable", delivery_current=0)

    score = scorer.score_signal(signal)

    assert score.delivery_data_score >= 0
    assert score.total_score >= 60
    assert score.recommendation != "Skip"


def test_falling_market_relative_strength_uses_outperformance_band():
    detector = make_detector()

    stock_close = [100] * 20 + [102, 103, 104, 105, 106]
    index_close = [100] * 20 + [98, 97, 96, 95, 94]

    stock_df = pd.DataFrame({"close": stock_close})
    index_df = pd.DataFrame({"close": index_close})
    signal = make_signal(rs_ratio=0, rs_trend="neutral")

    detector._analyze_relative_strength(stock_df, index_df, signal)

    assert signal.rs_ratio > 0
    assert signal.rs_trend == "positive"


def test_flat_support_counts_as_one_distinct_touch_not_many():
    detector = make_detector()

    lows = [100.0] * 15

    touches = detector._count_distinct_support_touches(lows, 100.0, deviation_pct=2)

    assert touches == 1


def test_long_consolidation_correctly_detected_from_longest_valid_range_scan():
    detector = make_detector()
    signal = make_signal(in_range=False, range_high=0.0, range_low=0.0, range_days=0)

    days = 90
    closes = [100.0 + (0.4 if i % 2 == 0 else -0.4) for i in range(days)]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": [102.0] * days,
            "low": [98.0] * days,
            "close": closes,
            "volume": [100000] * days,
        }
    )

    detector._analyze_price_structure(df, signal)

    assert signal.in_range is True
    assert signal.range_days == 90
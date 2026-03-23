"""
Trade Setup Generator
Generates actionable trade setups with entry, stop loss, and targets
"""

from typing import Dict, List, Optional, TYPE_CHECKING, Any
from dataclasses import dataclass
import logging

# Import StockScore for type hints only (avoid circular imports)
if TYPE_CHECKING:
    from src.scoring.ai_scorer import StockScore

logger = logging.getLogger(__name__)


@dataclass
class TradeSetup:
    """Generated trade setup for a stock"""
    stock_symbol: str
    stock_name: str
    current_price: float
    
    # Entry
    entry_price: float
    entry_type: str  # 'breakout', 'early_accumulation'
    
    # Stop Loss
    stop_loss: float
    stop_loss_pct: float
    
    # Targets
    target_1: float
    target_1_distance: float  # Points away
    target_1_time_estimate: str  # Estimated days to hit
    target_2: float
    target_2_distance: float
    target_2_time_estimate: str
    target_3: float
    target_3_distance: float
    target_3_time_estimate: str
    
    # Risk/Reward
    risk_reward_1: float  # R:R for target 1
    risk_reward_2: float  # R:R for target 2
    risk_reward_3: float  # R:R for target 3
    
    # Duration
    expected_duration: str
    duration_type: str  # 'short_term', 'medium_term'
    
    # Analysis
    confidence_score: int
    phase: str
    risk_level: str  # 'Low', 'Moderate', 'High'
    
    # Technical Details
    support_level: float
    resistance_level: float
    range_height: float
    atr_current: float
    
    # Signals
    signals: List[str]
    
    # Reasoning Engine Fields (optional)
    rule_score: Optional[int] = None
    ai_score: Optional[int] = None
    reasoning_text: str = ""
    confidence_level: str = "medium"
    below_threshold: bool = False  # TODO: Populate when filtering signals below score threshold


class TradeSetupGenerator:
    """
    Generates actionable trade setups from scored stocks
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.trade_config = config.get('trade_setup', {})
        
    def generate_setup(
        self,
        score: 'StockScore',
        signal,
        stock_info: Optional[Dict] = None
    ) -> TradeSetup:
        """
        Generate a trade setup from a scored stock
        
        Args:
            score: StockScore object
            signal: AccumulationSignal object
            stock_info: Optional stock metadata
            
        Returns:
            TradeSetup with all trade details
        """
        current = signal.current_price
        
        # Determine entry type
        entry_type, entry_price = self._calculate_entry(signal)
        
        # Calculate stop loss
        stop_loss, stop_loss_pct = self._calculate_stop_loss(signal, entry_price)
        
        # Calculate targets
        t1, t2, t3, t1_dist, t2_dist, t3_dist = self._calculate_targets(signal, entry_price, stop_loss)
        
        # Calculate time estimates based on ATR
        time_estimates = self._calculate_time_estimates(
            signal, t1_dist, t2_dist, t3_dist, entry_price
        )
        
        # Calculate risk/reward
        risk = entry_price - stop_loss
        risk_reward_1 = (t1 - entry_price) / risk if risk > 0 else 0
        risk_reward_2 = (t2 - entry_price) / risk if risk > 0 else 0
        risk_reward_3 = (t3 - entry_price) / risk if risk > 0 else 0
        
        # Determine duration
        duration_type, expected_duration = self._calculate_duration(signal)
        
        # Determine risk level
        risk_level = self._determine_risk_level(risk_reward_1, stop_loss_pct)
        
        # Generate signals list (simplified - no indicators)
        signals = self._generate_signals(signal, score)
        
        # Get ATR
        atr = signal.atr_current if signal.atr_current > 0 else (current * 0.02)  # Default 2%
        
        return TradeSetup(
            stock_symbol=score.stock_symbol,
            stock_name=stock_info.get('name', score.stock_symbol) if stock_info else score.stock_symbol,
            current_price=current,
            entry_price=entry_price,
            entry_type=entry_type,
            stop_loss=stop_loss,
            stop_loss_pct=stop_loss_pct,
            target_1=t1,
            target_1_distance=t1_dist,
            target_1_time_estimate=time_estimates[0],
            target_2=t2,
            target_2_distance=t2_dist,
            target_2_time_estimate=time_estimates[1],
            target_3=t3,
            target_3_distance=t3_dist,
            target_3_time_estimate=time_estimates[2],
            risk_reward_1=round(risk_reward_1, 2),
            risk_reward_2=round(risk_reward_2, 2),
            risk_reward_3=round(risk_reward_3, 2),
            expected_duration=expected_duration,
            duration_type=duration_type,
            confidence_score=score.total_score,
            phase="Accumulation (Wyckoff)",
            risk_level=risk_level,
            support_level=signal.support_level,
            resistance_level=signal.resistance_level,
            range_height=signal.range_high - signal.range_low if signal.in_range else 0,
            atr_current=atr,
            signals=signals,
            rule_score=getattr(score, 'price_structure_score', score.total_score),
            ai_score=getattr(score, 'ai_reasoning_score', None),
            reasoning_text="",
            confidence_level="medium"
        )
    
    def _calculate_entry(
        self, 
        signal
    ) -> tuple:
        """
        Calculate entry price based on breakout or early accumulation
        """
        current = signal.current_price
        resistance = signal.resistance_level
        
        # Check if near breakout
        if signal.near_breakout:
            # Use breakout entry
            entry_type = "Breakout"
            threshold = self.trade_config.get('entry', {}).get('breakout_threshold', 0.02)
            entry_price = resistance * (1 + threshold)
        else:
            # Early accumulation entry near support
            entry_type = "Early Accumulation"
            discount = self.trade_config.get('entry', {}).get('early_entry_discount', 0.03)
            entry_price = resistance * (1 - discount)
        
        return entry_type, round(entry_price, 2)
    
    def _calculate_stop_loss(
        self, 
        signal,
        entry_price: float
    ) -> tuple:
        """
        Calculate stop loss below support
        """
        support = signal.support_level
        sl_pct_config = self.trade_config.get('stop_loss', {}).get('below_support', 0.02)
        max_loss = self.trade_config.get('stop_loss', {}).get('max_loss', 3)
        
        if support > 0:
            # Stop loss below support with buffer
            stop_loss = support * (1 - sl_pct_config)
        else:
            # Fallback: use percentage of entry
            stop_loss = entry_price * (1 - max_loss / 100)
        
        # Calculate actual stop loss percentage
        stop_loss_pct = (entry_price - stop_loss) / entry_price * 100
        
        return round(stop_loss, 2), round(stop_loss_pct, 2)
    
    def _calculate_targets(
        self,
        signal,
        entry_price: float,
        stop_loss: float
    ) -> tuple:
        """
        Calculate target prices and distances
        """
        range_height = signal.range_high - signal.range_low if signal.in_range else 0
        
        targets_config = self.trade_config.get('targets', {})
        
        # Target 1: Range height breakout
        t1_multiple = targets_config.get('t1_range_height', 1.0)
        t1 = entry_price + (range_height * t1_multiple)
        
        # Target 2: 1.5x range
        t2_multiple = targets_config.get('t2_range_height', 1.5)
        t2 = entry_price + (range_height * t2_multiple)
        
        # Target 3: Previous swing high
        t3 = signal.resistance_level
        
        # Ensure targets are above entry
        if t1 <= entry_price:
            t1 = entry_price * 1.05
        if t2 <= entry_price:
            t2 = entry_price * 1.08
        if t3 <= entry_price:
            t3 = entry_price * 1.10
        
        # Calculate distances
        t1_dist = round(t1 - entry_price, 2)
        t2_dist = round(t2 - entry_price, 2)
        t3_dist = round(t3 - entry_price, 2)
        
        return round(t1, 2), round(t2, 2), round(t3, 2), t1_dist, t2_dist, t3_dist
    
    def _calculate_time_estimates(
        self,
        signal,
        t1_dist: float,
        t2_dist: float,
        t3_dist: float,
        entry_price: float
    ) -> tuple:
        """
        Estimate time to achieve targets based on ATR
        Formula: Time = Target Distance / ATR
        """
        # Get ATR (use default if not available)
        atr = signal.atr_current if signal.atr_current > 0 else (entry_price * 0.02)
        
        if atr <= 0:
            return ("N/A", "N/A", "N/A")
        
        # Calculate days for each target
        t1_days = max(1, round(t1_dist / atr))
        t2_days = max(1, round(t2_dist / atr))
        t3_days = max(1, round(t3_dist / atr))
        
        # Format time estimates
        def format_time(days):
            if days <= 1:
                return "1 day"
            elif days <= 5:
                return f"{days} days"
            elif days <= 20:
                weeks = days // 5
                return f"{weeks} week{'s' if weeks > 1 else ''}"
            else:
                months = days // 20
                return f"{months} month{'s' if months > 1 else ''}"
        
        return (format_time(t1_days), format_time(t2_days), format_time(t3_days))
    
    def _calculate_duration(
        self,
        signal
    ) -> tuple:
        """
        Estimate expected holding duration
        """
        duration_config = self.trade_config.get('duration', {})
        
        if signal.near_breakout:
            # Short term if near breakout
            short_term = duration_config.get('short_term_weeks', [2, 4])
            return 'short_term', f"{short_term[0]}-{short_term[1]} weeks"
        else:
            # Medium term for early accumulation
            medium_term = duration_config.get('medium_term_months', [1, 3])
            return 'medium_term', f"{medium_term[0]}-{medium_term[1]} months"
    
    def _determine_risk_level(
        self,
        risk_reward_1: float,
        stop_loss_pct: float
    ) -> str:
        """
        Determine risk level based on R:R and stop loss
        """
        if risk_reward_1 >= 2.0 and stop_loss_pct <= 2:
            return "Low"
        elif risk_reward_1 >= 1.5 and stop_loss_pct <= 3:
            return "Moderate"
        else:
            return "High"
    
    def _generate_signals(
        self,
        signal,
        score: 'StockScore'
    ) -> List[str]:
        """
        Generate simplified human-readable signals (no indicators)
        """
        signals = []
        
        # Use positive factors from scoring (simplified - no indicator names)
        for factor in score.positive_factors:
            # Clean up the factor names
            if 'consolidation' in factor.lower():
                signals.append("Strong consolidation phase")
            elif 'volume' in factor.lower():
                signals.append("Volume accumulation observed")
            elif 'delivery' in factor.lower():
                signals.append("Delivery percentage rising")
            elif 'support' in factor.lower():
                signals.append(f"Strong support zone")
            elif 'outperforming' in factor.lower():
                signals.append("Outperforming market index")
            elif 'compression' in factor.lower():
                signals.append("Volatility compression")
            elif '50 dma' in factor.lower() or 'ma' in factor.lower():
                signals.append("Price above key moving average")
        
        # Add key observations
        if signal.near_breakout:
            signals.append(f"Near breakout point")
        
        if signal.support_touches >= 3:
            signals.append(f"Multiple support touches")
        
        if signal.up_volume_ratio > 1.2:
            signals.append("Buying pressure evident")
        
        # Return unique signals, limited to 6
        unique_signals = list(dict.fromkeys(signals))
        return unique_signals[:6]
    
    def generate_all_setups(
        self,
        scored_stocks: List['StockScore'],
        signals: Dict[str, Any],
        fetcher
    ) -> List[TradeSetup]:
        """
        Generate trade setups for all scored stocks
        
        Args:
            scored_stocks: List of StockScore objects
            signals: Dict mapping symbol to AccumulationSignal
            fetcher: Data fetcher for stock info
            
        Returns:
            List of TradeSetup objects
        """
        setups = []
        
        for score in scored_stocks:
            try:
                signal = signals.get(score.stock_symbol)
                
                if signal is None:
                    continue
                    
                # Get stock info
                try:
                    stock_info = fetcher.get_stock_info(score.stock_symbol)
                except Exception:
                    stock_info = None
                
                setup = self.generate_setup(score, signal, stock_info)
                setups.append(setup)
                
            except Exception as e:
                logger.error(f"Error generating setup for {score.stock_symbol}: {str(e)}")
                continue
        
        return setups


def format_telegram_alert(setup: TradeSetup) -> str:
    """
    Format a trade setup as Telegram alert message
    
    Args:
        setup: TradeSetup object
        
    Returns:
        Formatted Telegram message string
    """
    # Emoji mapping
    emoji = {
        'stock': '📊',
        'phase': '🔹',
        'entry': '💰',
        'stop': '🛑',
        'target': '🎯',
        'confidence': '📈',
        'duration': '⏳',
        'signals': '📋',
        'risk': '⚠️',
        'time': '🕐'
    }
    
    # Build message
    lines = []
    
    # Header
    lines.append(f"{emoji['stock']} Stock Alert: {setup.stock_symbol}")
    if setup.stock_name != setup.stock_symbol:
        lines.append(f"   {setup.stock_name}")
    
    lines.append("")
    
    # Phase
    lines.append(f"{emoji['phase']} Phase: {setup.phase}")
    
    lines.append("")
    
    # Entry & Stop
    lines.append(f"{emoji['entry']} Entry: ₹{setup.entry_price:.2f}")
    lines.append(f"{emoji['stop']} Stop Loss: ₹{setup.stop_loss:.2f} (-{setup.stop_loss_pct:.1f}%)")
    
    lines.append("")
    
    # Targets with time estimates
    lines.append(f"{emoji['target']} Targets:")
    lines.append(f"   T1: ₹{setup.target_1:.2f} | +{setup.target_1_distance:.2f} pts | {setup.target_1_time_estimate} | R:R {setup.risk_reward_1:.1f}")
    lines.append(f"   T2: ₹{setup.target_2:.2f} | +{setup.target_2_distance:.2f} pts | {setup.target_2_time_estimate} | R:R {setup.risk_reward_2:.1f}")
    lines.append(f"   T3: ₹{setup.target_3:.2f} | +{setup.target_3_distance:.2f} pts | {setup.target_3_time_estimate} | R:R {setup.risk_reward_3:.1f}")
    
    lines.append("")
    
    # Confidence
    lines.append(f"{emoji['confidence']} Confidence: {setup.confidence_score}/100")
    lines.append(f"{emoji['risk']} Risk: {setup.risk_level}")
    
    return "\n".join(lines)


def format_summary_alert(setups: List[TradeSetup]) -> str:
    """
    Format a summary alert for multiple setups
    
    Args:
        setups: List of TradeSetup objects
        
    Returns:
        Formatted summary message
    """
    lines = []
    
    lines.append("📊 Daily Accumulation Scanner Summary")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Found {len(setups)} potential setups:")
    lines.append("")
    
    for i, setup in enumerate(setups, 1):
        lines.append(f"{i}. {setup.stock_symbol} - Score: {setup.confidence_score}/100")
        lines.append(f"   Entry: ₹{setup.entry_price:.2f} | SL: ₹{setup.stop_loss:.2f}")
        lines.append(f"   Targets: ₹{setup.target_1:.2f} / ₹{setup.target_2:.2f} / ₹{setup.target_3:.2f}")
        lines.append("")
    
    lines.append("-" * 40)
    lines.append("Scan completed at 3:00 PM IST")
    
    return "\n".join(lines)

"""
SIE Orchestrator - Signal Intelligence Engine Coordinator
Manages signal tracking, outcome recording, and notifications
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SIEOrchestrator:
    """
    Orchestrates the Signal Intelligence Engine components
    """
    
    def __init__(self, config: Dict, telegram_bot=None):
        self.config = config
        self.telegram_bot = telegram_bot
        
        sie_config = config.get('signal_intelligence', {})
        self.enabled = sie_config.get('enabled', True)
        
        # Initialize components
        self.signal_registry = None
        self.outcome_tracker = None
        self.accuracy_calculator = None
        self.learning_engine = None
        self.outcome_notifier = None
        
        if self.enabled:
            self._init_components()
    
    def _init_components(self):
        """Initialize all SIE components"""
        try:
            from src.intelligence.signal_registry import SignalRegistry
            from src.intelligence.outcome_tracker import OutcomeTracker
            from src.intelligence.accuracy_calculator import AccuracyCalculator
            from src.intelligence.learning_engine import LearningEngine
            from src.intelligence.outcome_notifier import OutcomeNotifier
            
            self.signal_registry = SignalRegistry(self.config)
            self.outcome_tracker = OutcomeTracker(self.config)
            self.accuracy_calculator = AccuracyCalculator(self.config)
            self.learning_engine = LearningEngine(self.config)
            self.outcome_notifier = OutcomeNotifier(self.config, self.telegram_bot)
            
            logger.info("SIE Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SIE components: {e}")
    
    def register_signal(self, setup) -> str:
        """
        Register a new signal for tracking
        
        Args:
            setup: TradeSetup object
            
        Returns:
            signal_id
        """
        if not self.enabled or not self.signal_registry:
            return ""
        
        try:
            signal_id = self.signal_registry.register_signal(
                stock_symbol=setup.stock_symbol,
                stock_name=setup.stock_name,
                entry_price=setup.entry_price,
                stop_loss=setup.stop_loss,
                target_1=setup.target_1,
                target_2=setup.target_2,
                target_3=setup.target_3,
                confidence_score=setup.confidence_score,
                rule_score=getattr(setup, 'rule_score', setup.confidence_score),
                ai_score=getattr(setup, 'ai_score', None),
                reasoning_text=getattr(setup, 'reasoning_text', '')
            )
            
            logger.info(f"Registered signal for {setup.stock_symbol}: {signal_id}")
            return signal_id
            
        except Exception as e:
            logger.error(f"Failed to register signal: {e}")
            return ""
    
    def check_and_update_signals(self, fetcher) -> List[Dict]:
        """
        Check all active signals against current prices
        
        Args:
            fetcher: NSEDataFetcher instance
            
        Returns:
            List of resolved signals
        """
        if not self.enabled or not self.signal_registry:
            return []
        
        try:
            # Get active signals
            active_signals = self.signal_registry.get_active_signals()
            
            if not active_signals:
                return []
            
            # Fetch current prices
            current_prices = {}
            for signal in active_signals:
                try:
                    # Get current price from latest data
                    df = fetcher.get_stock_data(signal.stock_symbol, period="5d", interval="1d")
                    if df is not None and not df.empty:
                        current_prices[signal.stock_symbol] = df['close'].iloc[-1]
                    else:
                        # Fallback to stock_info which now includes current_price
                        stock_info = fetcher.get_stock_info(signal.stock_symbol)
                        if isinstance(stock_info, dict) and stock_info.get('current_price'):
                            current_prices[signal.stock_symbol] = stock_info['current_price']
                except Exception as e:
                    logger.warning(f"Failed to get price for {signal.stock_symbol}: {e}")
            
            # Check outcomes
            resolved = self.signal_registry.check_outcomes(current_prices)
            
            # Record outcomes
            for resolution in resolved:
                signal = self.signal_registry.get_signal(resolution['signal_id'])
                if signal:
                    self.outcome_tracker.record_outcome(
                        signal_id=resolution['signal_id'],
                        stock_symbol=signal.stock_symbol,
                        stock_name=signal.stock_name,
                        entry_price=signal.entry_price,
                        exit_price=resolution['exit_price'],
                        stop_loss=signal.stop_loss,
                        target_1=signal.target_1,
                        outcome=resolution['outcome'],
                        confidence_score=signal.confidence_score,
                        rule_score=signal.rule_score,
                        ai_score=signal.ai_score,
                        signal_date=signal.signal_date
                    )
            
            # Send notifications
            if self.outcome_notifier:
                for resolution in resolved:
                    signal = self.signal_registry.get_signal(resolution['signal_id'])
                    if signal:
                        self.outcome_notifier.send_outcome_alert(signal, resolution)
            
            # Check for expired signals
            expired = self.signal_registry.check_expired()
            for exp in expired:
                signal = self.signal_registry.get_signal(exp['signal_id'])
                if signal:
                    self.outcome_tracker.record_outcome(
                        signal_id=exp['signal_id'],
                        stock_symbol=signal.stock_symbol,
                        stock_name=signal.stock_name,
                        entry_price=signal.entry_price,
                        exit_price=signal.entry_price,  # No exit
                        stop_loss=signal.stop_loss,
                        target_1=signal.target_1,
                        outcome='expired',
                        confidence_score=signal.confidence_score,
                        rule_score=signal.rule_score,
                        ai_score=signal.ai_score,
                        signal_date=signal.signal_date
                    )
                    
                    if self.outcome_notifier:
                        self.outcome_notifier.send_expired_alert(signal)
            
            logger.info(f"Checked {len(active_signals)} signals: {len(resolved)} resolved, {len(expired)} expired")
            
            return resolved + expired
            
        except Exception as e:
            logger.error(f"Error checking signals: {e}")
            return []
    
    def get_metrics(self) -> Dict:
        """Get current accuracy metrics"""
        if not self.enabled or not self.outcome_tracker:
            return {}
        
        outcomes = self.outcome_tracker.outcomes
        metrics = self.accuracy_calculator.calculate_metrics(outcomes)
        
        return {
            'total_signals': metrics.total_signals,
            'accuracy_rate': metrics.accuracy_rate,
            'target_1_rate': metrics.target_1_rate,
            'target_2_rate': metrics.target_2_rate,
            'target_3_rate': metrics.target_3_rate,
            'stoploss_rate': metrics.stoploss_rate,
            'avg_return': metrics.avg_return,
            'avg_loss': metrics.avg_loss,
            'risk_adjusted_return': metrics.risk_adjusted_return,
            'active_signals': len(self.signal_registry.get_active_signals()) if self.signal_registry else 0,
            'current_weights': self.learning_engine.get_weights() if self.learning_engine else {}
        }
    
    def get_active_signals_count(self) -> int:
        """Get count of active signals"""
        if not self.signal_registry:
            return 0
        return len(self.signal_registry.get_active_signals())
    
    def send_daily_summary(self) -> bool:
        """Send daily performance summary"""
        if not self.enabled or not self.outcome_notifier:
            return False
        
        return self.outcome_notifier.send_daily_summary(self.get_metrics())


def create_sie_orchestrator(config: Dict, telegram_bot=None) -> SIEOrchestrator:
    """Factory function to create SIE orchestrator"""
    return SIEOrchestrator(config, telegram_bot)
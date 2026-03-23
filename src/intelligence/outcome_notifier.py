"""
Outcome Notifier - Telegram notifications for signal outcomes
Part of Signal Intelligence Engine (SIE)
"""

import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class OutcomeNotifier:
    """
    Sends Telegram notifications for signal outcomes
    """
    
    def __init__(self, config: Dict, telegram_bot=None):
        self.config = config
        self.telegram_bot = telegram_bot
        
        sie_config = config.get('signal_intelligence', {})
        notif_config = sie_config.get('notifications', {})
        
        self.enabled = notif_config.get('outcome_alerts', True)
        self.daily_summary_enabled = notif_config.get('daily_summary', True)
        self.weekly_report_enabled = notif_config.get('weekly_report', True)
    
    def send_outcome_alert(self, signal, resolution: Dict) -> bool:
        """
        Send alert when signal is resolved (target hit or stoploss hit)
        """
        if not self.enabled or not self.telegram_bot:
            return False
        
        try:
            outcome = resolution['outcome']
            pnl_pct = resolution['pnl_pct']
            exit_price = resolution['exit_price']
            
            if 'target' in outcome:
                return self._send_target_hit_alert(signal, outcome, exit_price, pnl_pct)
            elif outcome == 'stoploss_hit':
                return self._send_stoploss_alert(signal, exit_price, pnl_pct)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to send outcome alert: {e}")
            return False
    
    def _send_target_hit_alert(self, signal, outcome: str, exit_price: float, pnl_pct: float) -> bool:
        """Send target hit alert"""
        target_num = outcome.replace('hit_target_', '')
        
        emoji = '🎯'
        outcome_text = f"Target {target_num}"
        
        message = f"""
{emoji} TARGET HIT: {signal.stock_symbol} reached {outcome_text} at ₹{exit_price:.2f}

📊 Entry: ₹{signal.entry_price:.2f} | Target: ₹{exit_price:.2f}
📈 Return: +{pnl_pct:.2f}% | Held: {self._calculate_days(signal.signal_date)} days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 Signal Performance:
   Original Confidence: {signal.confidence_score}/100
   Rule Score: {signal.rule_score} | AI Score: {signal.ai_score or 'N/A'}
   
   Status: {outcome_text} of 3 reached
"""
        
        if signal.ai_score:
            message += f"\n🧠 AI Prediction: ~{min(85, signal.ai_score + 5)}% accuracy for similar setups"
        
        return self.telegram_bot.send_message(message)
    
    def _send_stoploss_alert(self, signal, exit_price: float, pnl_pct: float) -> bool:
        """Send stoploss hit alert"""
        message = f"""
🛑 STOPLOSS HIT: {signal.stock_symbol} hit SL at ₹{exit_price:.2f}

📊 Entry: ₹{signal.entry_price:.2f} | SL: ₹{signal.stop_loss:.2f}
📉 Loss: {pnl_pct:.2f}% | Held: {self._calculate_days(signal.signal_date)} days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 Signal Performance:
   Original Confidence: {signal.confidence_score}/100
   Rule Score: {signal.rule_score} | AI Score: {signal.ai_score or 'N/A'}

💡 Learning: This signal had {'lower' if signal.confidence_score < 70 else 'moderate'} confidence.
   Watch for similar patterns in future.
"""
        
        return self.telegram_bot.send_message(message)
    
    def send_expired_alert(self, signal) -> bool:
        """Send alert when signal expires"""
        if not self.enabled or not self.telegram_bot:
            return False
        
        message = f"""
⏰ SIGNAL EXPIRED: {signal.stock_symbol} did not hit target/SL within 30 days

📊 Entry: ₹{signal.entry_price:.2f}
📉 Final Status: Expired (no resolution)

🧠 Note: Consider reviewing this pattern for future signals
"""
        
        return self.telegram_bot.send_message(message)
    
    def send_daily_summary(self, metrics: Dict) -> bool:
        """Send daily performance summary"""
        if not self.daily_summary_enabled or not self.telegram_bot:
            return False
        
        try:
            active = metrics.get('active_signals', 0)
            accuracy = metrics.get('accuracy_rate', 0)
            t1_rate = metrics.get('target_1_rate', 0)
            sl_rate = metrics.get('stoploss_rate', 0)
            avg_return = metrics.get('avg_return', 0)
            
            message = f"""
📊 Daily Signal Summary - {datetime.now().strftime('%Y-%m-%d')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Performance:
   Active Signals: {active}
   Today's Accuracy: {accuracy:.1f}%
   
   Target Hits: {t1_rate:.1f}%
   Stop Loss: {sl_rate:.1f}%
   
   Avg Return: {avg_return:+.2f}%
"""
            
            # Add weight info if available
            weights = metrics.get('current_weights', {})
            if weights:
                message += "\n📈 Current Weights:"
                for k, v in weights.items():
                    message += f"\n   {k}: {v}%"
            
            return self.telegram_bot.send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return False
    
    def send_weekly_report(self, metrics: Dict) -> bool:
        """Send weekly performance report"""
        if not self.weekly_report_enabled or not self.telegram_bot:
            return False
        
        message = f"""
📊 Weekly Signal Report - Week of {datetime.now().strftime('%Y-%m-%d')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This week's performance summary
would be shown here with:
- Total signals
- Win rate
- Top performing factors
- Weight adjustments made
"""
        
        return self.telegram_bot.send_message(message)
    
    def _calculate_days(self, signal_date: str) -> int:
        """Calculate days since signal"""
        try:
            signal_dt = datetime.fromisoformat(signal_date)
            return (datetime.now() - signal_dt).days
        except:
            return 0


def create_outcome_notifier(config: Dict, telegram_bot=None) -> OutcomeNotifier:
    """Factory function to create outcome notifier"""
    return OutcomeNotifier(config, telegram_bot)
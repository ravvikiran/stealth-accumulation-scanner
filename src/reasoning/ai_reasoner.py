"""
AI Reasoner - LLM-powered reasoning for stock signals
Part of the Reasoning Engine
"""

import logging
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class AIReasoner:
    """
    Uses LLM to provide AI-powered reasoning and scoring for stock signals
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.llm_client = None
        self.enabled = False
        
        self._init_llm()
    
    def _init_llm(self):
        """Initialize LLM client"""
        try:
            from src.llm.llm_client import get_llm_client
            self.llm_client = get_llm_client(self.config)
            self.enabled = self.llm_client.is_enabled() if self.llm_client else False
            
            if self.enabled:
                logger.info("AI Reasoner initialized successfully")
            else:
                logger.warning("AI Reasoner: No LLM provider available")
        except Exception as e:
            logger.warning(f"AI Reasoner initialization failed: {e}")
    
    def is_available(self) -> bool:
        """Check if AI reasoner is available"""
        return self.enabled and self.llm_client is not None
    
    def analyze(self, signal) -> Optional[Dict[str, Any]]:
        """
        Analyze a stock signal using AI/LLM
        
        Args:
            signal: AccumulationSignal object
            
        Returns:
            Dict with 'score' (0-100), 'insights' (list), 'reasoning' (str)
        """
        if not self.is_available():
            return None
        
        try:
            # Build prompt for analysis
            prompt = self._build_analysis_prompt(signal)
            
            # Get LLM response
            response = self.llm_client.generate_analysis(
                system_prompt=self._get_system_prompt(),
                user_prompt=prompt
            )
            
            if not response:
                logger.warning(f"AI reasoner got empty response for {signal.stock_symbol}")
                return None
            
            # Parse response
            return self._parse_response(response, signal)
            
        except Exception as e:
            logger.error(f"AI analysis failed for {signal.stock_symbol}: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for stock analysis"""
        return """You are an expert stock analyst specializing in Wyckoff accumulation patterns and technical analysis.

Your task is to analyze stock data and provide:
1. A confidence score (0-100) for the signal
2. Key insights and observations
3. Risk factors to consider

Be concise and analytical. Focus on:
- Price action and volume dynamics
- Support/resistance strength
- Market relative strength
- Risk/reward assessment

Respond in JSON format:
{
  "score": <0-100>,
  "insights": ["insight1", "insight2", ...],
  "reasoning": "brief explanation"
}"""
    
    def _build_analysis_prompt(self, signal) -> str:
        """Build analysis prompt from signal data"""
        prompt = f"""Analyze the following stock signal for {signal.stock_symbol}:

**Current Price:** ₹{signal.current_price:.2f}

**Price Structure:**
- In Range: {'Yes' if signal.in_range else 'No'}
- Range: {signal.range_days} days (₹{signal.range_low:.2f} - ₹{signal.range_high:.2f})
- Near Breakout: {'Yes' if signal.near_breakout else 'No'} ({signal.breakout_distance_pct:.1f}% to resistance)

**Support/Resistance:**
- Support: ₹{signal.support_level:.2f} ({signal.support_touches} touches)
- Resistance: ₹{signal.resistance_level:.2f}

**Volume & Delivery:**
- Up Volume Ratio: {signal.up_volume_ratio:.2f}
- Volume Spike at Support: {'Yes' if signal.volume_spike_near_support else 'No'}
- Delivery Trend: {signal.delivery_trend} ({signal.delivery_current:.1f}%)

**Moving Averages:**
- Price above 50-DMA: {'Yes' if signal.price_above_ma50 else 'No'}
- 50-DMA Trend: {signal.ma50_trend} (slope: {signal.ma50_slope:.3f})

**Relative Strength:**
- RS Ratio: {signal.rs_ratio:.2f}
- RS Trend: {signal.rs_trend}

**Volatility:**
- ATR Trend: {signal.atr_trend}
- Current ATR: ₹{signal.atr_current:.2f}

**Confidence Factors:**
{self._format_confidence_factors(signal.confidence_factors)}

Provide your analysis in JSON format."""
        return prompt
    
    def _format_confidence_factors(self, factors: Dict) -> str:
        """Format confidence factors for prompt"""
        lines = []
        for key, value in factors.items():
            status = "✓" if value else "✗"
            lines.append(f"- {status} {key}")
        return "\n".join(lines) if lines else "- No factors detected"
    
    def _parse_response(self, response: str, signal) -> Optional[Dict[str, Any]]:
        """Parse LLM response into structured format"""
        import json
        import re
        
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                
                # Validate score
                score = data.get('score', 0)
                if not isinstance(score, (int, float)) or score < 0 or score > 100:
                    score = 50  # Default if invalid
                
                return {
                    'score': int(score),
                    'insights': data.get('insights', []),
                    'reasoning': data.get('reasoning', '')
                }
            
            # If no JSON found, try to extract score from text
            score_match = re.search(r'score[:\s]+(\d+)', response, re.IGNORECASE)
            if score_match:
                score = int(score_match.group(1))
                return {
                    'score': score,
                    'insights': ['Analysis provided by AI'],
                    'reasoning': response[:200]
                }
            
            logger.warning(f"Could not parse AI response for {signal.stock_symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return None
    
    def batch_analyze(self, signals: List) -> Dict[str, Dict]:
        """Analyze multiple signals"""
        results = {}
        
        for signal in signals:
            result = self.analyze(signal)
            if result:
                results[signal.stock_symbol] = result
        
        return results


def create_ai_reasoner(config: Dict) -> AIReasoner:
    """Factory function to create AI reasoner"""
    return AIReasoner(config)
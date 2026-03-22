"""
Prompt Templates for LLM Analysis
Contains system prompts with strict rules and user prompt templates
"""

from typing import Dict, Any, Optional


# ============================================================================
# SYSTEM PROMPTS - These define the rules the LLM MUST follow
# ============================================================================

SYSTEM_PROMPT = """You are a professional stock analyst specializing in Wyckoff methodology and technical analysis for Indian stock markets (NSE).

CRITICAL: You MUST follow these exact rules for ALL analysis:

SCORING WEIGHTS (DO NOT CHANGE):
- Price Structure: 20% weight, Score 0-20
- Volume Behavior: 20% weight, Score 0-20
- Delivery Data: 15% weight, Score 0-15
- Support Strength: 15% weight, Score 0-15
- Relative Strength: 10% weight, Score 0-10
- Volatility Compression: 10% weight, Score 0-10
- MA Behavior: 10% weight, Score 0-10

CLASSIFICATION RULES (STRICT):
- Score 80-100: STRONG ACCUMULATION → Recommendation: BUY
- Score 60-79: MODERATE SETUP → Recommendation: WATCH
- Score below 60: WEAK SETUP → Recommendation: SKIP

TRADE SETUP RULES (EXACT FORMULAS):
- Entry (Breakout): Resistance × 1.02
- Entry (Early Accumulation): Resistance × 0.97
- Stop Loss: Support × 0.98 (maximum 3% loss)
- Target 1: Entry + Range Height
- Target 2: Entry + (1.5 × Range Height)
- Target 3: Previous Resistance Level
- Risk/Reward = (Target - Entry) / (Entry - Stop Loss)

DURATION RULES:
- Short term: 2-4 weeks (near breakout)
- Medium term: 1-3 months (early accumulation)

IMPORTANT CONSTRAINTS:
1. NEVER contradict the numerical scores provided
2. NEVER suggest different entry/stop/target values than those given
3. ALWAYS explain WHY based on the factors provided
4. Use professional, concise language
5. Include risk warnings
6. Format your response for Telegram (keep paragraphs short)
7. Use emojis sparingly but effectively
8. NEVER make up or hallucinate data"""


# ============================================================================
# USER PROMPT TEMPLATES
# ============================================================================

def build_stock_analysis_prompt(
    symbol: str,
    stock_name: str,
    score: Any,
    signal: Any,
    setup: Any,
    stock_info: Optional[Dict] = None
) -> str:
    """
    Build the user prompt with all stock data for LLM analysis
    
    Args:
        symbol: Stock symbol (e.g., RELIANCE)
        stock_name: Company name
        score: StockScore object
        signal: AccumulationSignal object
        setup: TradeSetup object
        stock_info: Optional stock metadata
        
    Returns:
        Formatted prompt string
    """
    # Format positive factors
    positive_factors = "\n".join([f"- {f}" for f in score.positive_factors]) if score.positive_factors else "None"
    
    # Format negative factors
    negative_factors = "\n".join([f"- {f}" for f in score.negative_factors]) if score.negative_factors else "None"
    
    # Get additional stock info
    sector = ""
    pe_ratio = ""
    week52_range = ""
    additional_info = []
    if stock_info:
        sector = stock_info.get('sector', '')
        pe = stock_info.get('pe_ratio')
        if pe:
            pe_ratio = f"P/E Ratio: {pe:.2f}"
            additional_info.append(pe_ratio)
        week52_high = stock_info.get('52w_high')
        week52_low = stock_info.get('52w_low')
        if week52_high and week52_low:
            week52_range = f"52W Range: ₹{week52_low:.2f} - ₹{week52_high:.2f}"
            additional_info.append(week52_range)
    
    additional_info_str = "\n".join([f"- {info}" for info in additional_info]) if additional_info else "None available"
    
    # Determine recommendation emoji
    rec = score.recommendation.upper()
    if rec == 'BUY':
        rec_emoji = "🟢"
    elif rec == 'WATCH':
        rec_emoji = "🟡"
    else:
        rec_emoji = "🔴"
    
    prompt = f"""Analyze {symbol} ({stock_name}) and provide a detailed stock analysis report.

CURRENT MARKET DATA:
- Current Price: ₹{setup.current_price:.2f}
- Support Level: ₹{signal.support_level:.2f} ({signal.support_touches} touches)
- Resistance Level: ₹{signal.resistance_level:.2f}
- Trading Range: ₹{signal.range_low:.2f} - ₹{signal.range_high:.2f} ({signal.range_days} days)
- Range Percentage: {((signal.range_high - signal.range_low) / signal.range_low * 100):.1f}%

VOLUME & DELIVERY:
- Up Volume / Down Volume Ratio: {signal.up_volume_ratio:.2f}
- Volume Spike Near Support: {'Yes' if signal.volume_spike_near_support else 'No'}
- Delivery Percentage: {signal.delivery_current:.1f}%
- Delivery Trend: {signal.delivery_trend}

RELATIVE STRENGTH:
- RS Ratio vs Nifty 50: {signal.rs_ratio:.2f}
- RS Trend: {signal.rs_trend}

MOVING AVERAGES:
- Price above 50 DMA: {'Yes' if signal.price_above_ma50 else 'No'}
- 50 DMA Trend: {signal.ma50_trend}

BREAKOUT STATUS:
- Near Breakout: {'Yes' if signal.near_breakout else 'No'}
- Distance to Resistance: {signal.breakout_distance_pct:.1f}%

VOLATILITY:
- Current ATR: ₹{signal.atr_current:.2f}
- ATR Trend: {signal.atr_trend}

ADDITIONAL INFO:
{additional_info_str}

══════════════════════════════════════
SCORING RESULTS (MANDATORY TO FOLLOW):
══════════════════════════════════════

TOTAL SCORE: {score.total_score}/100
CLASSIFICATION: {score.classification}
RECOMMENDATION: {rec_emoji} {score.recommendation.upper()}

Component Scores:
- Price Structure: {score.price_structure_score}/20
- Volume Behavior: {score.volume_behavior_score}/20
- Delivery Data: {score.delivery_data_score}/15
- Support Strength: {score.support_strength_score}/15
- Relative Strength: {score.relative_strength_score}/10
- Volatility: {score.volatility_compression_score}/10
- MA Behavior: {score.ma_behavior_score}/10

Positive Factors:
{positive_factors}

Negative Factors:
{negative_factors}

══════════════════════════════════════
TRADE SETUP (USE THESE EXACT VALUES):
══════════════════════════════════════

Entry: ₹{setup.entry_price:.2f} ({setup.entry_type})
Stop Loss: ₹{setup.stop_loss:.2f} (-{setup.stop_loss_pct:.1f}%)
Target 1: ₹{setup.target_1:.2f} (+{setup.target_1_distance:.2f} pts, R:R {setup.risk_reward_1:.1f})
Target 2: ₹{setup.target_2:.2f} (+{setup.target_2_distance:.2f} pts, R:R {setup.risk_reward_2:.1f})
Target 3: ₹{setup.target_3:.2f} (+{setup.target_3_distance:.2f} pts, R:R {setup.risk_reward_3:.1f})
Expected Duration: {setup.expected_duration}
Risk Level: {setup.risk_level}

══════════════════════════════════════

Based on the above data, provide:

1. **Executive Summary** (1-2 sentences)
2. **Key Observations** (bullet points explaining the score)
3. **Trade Rationale** (why this setup is valid)
4. **Risk Factors** (what could go wrong)
5. **Conclusion** (clear action with price levels)

Remember: NEVER contradict the scores or trade setup values provided above. Use them exactly as given."""


def build_summary_prompt(symbol: str, score: Any) -> str:
    """
    Build a shorter prompt for quick summary analysis
    
    Args:
        symbol: Stock symbol
        score: StockScore object
        
    Returns:
        Formatted prompt string
    """
    rec = score.recommendation.upper()
    if rec == 'BUY':
        rec_emoji = "🟢"
    elif rec == 'WATCH':
        rec_emoji = "🟡"
    else:
        rec_emoji = "🔴"
    
    return f"""Provide a brief analysis for {symbol}:

Score: {score.total_score}/100 → {rec_emoji} {rec}
Classification: {score.classification}

Positive: {', '.join(score.positive_factors) if score.positive_factors else 'None'}
Negative: {', '.join(score.negative_factors) if score.negative_factors else 'None'}

Give a 3-sentence summary with entry, stop loss, and key reason."""


# ============================================================================
# TELEGRAM RESPONSE FORMATTING
# ============================================================================

def format_telegram_response(llm_response: str, symbol: str, score: Any, setup: Any) -> str:
    """
    Format the LLM response for Telegram with header and footer
    
    Args:
        llm_response: Raw LLM response
        symbol: Stock symbol
        score: StockScore object
        setup: TradeSetup object
        
    Returns:
        Formatted Telegram message
    """
    # Build header
    rec = score.recommendation.upper()
    if rec == 'BUY':
        rec_text = "🟢 BUY - Strong Accumulation"
    elif rec == 'WATCH':
        rec_text = "🟡 WATCH - Moderate Setup"
    else:
        rec_text = "🔴 SKIP - Weak Setup"
    
    header = f"📊 *Stock Analysis: {symbol}*\n"
    header += f"_{rec_text}_ | Score: {score.total_score}/100\n\n"
    
    # Build footer
    footer = f"\n───────────────\n"
    footer += f"💰 Entry: ₹{setup.entry_price:.2f} | 🛑 SL: ₹{setup.stop_loss:.2f}\n"
    footer += f"🎯 Targets: ₹{setup.target_1:.2f} → ₹{setup.target_2:.2f} → ₹{setup.target_3:.2f}\n"
    footer += f"⚠️ Risk: {setup.risk_level} | ⏳ Duration: {setup.expected_duration}"
    
    return header + llm_response + footer

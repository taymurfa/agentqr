"""Technical Analysis Agent: indicator computation, pattern recognition, signal generation.
Works entirely locally using the `ta` library — no external API needed during analysis."""

import json
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base_agent import BaseAgent
from src.agents.tools.analysis_tools import AnalysisTools
from src.agents.tools.data_tools import DataTools


class TechnicalAnalysisAgent(BaseAgent):
    def __init__(self, db: AsyncSession):
        super().__init__(db, "technical_analyst")
        self.analysis = AnalysisTools()
        self.data = DataTools()

    async def run(self, query: str, **kwargs) -> dict:
        ticker = kwargs.get("ticker")
        if not ticker:
            return {"agent": "technical_analyst", "error": "Ticker is required for technical analysis"}

        await self._log("started", f"Technical analysis for {ticker}")

        # Compute all technical indicators (uses ta library locally on OHLCV data)
        indicators = {}
        signal = {}
        price_history = {}

        try:
            indicators = self.analysis.compute_all_indicators(ticker)
        except Exception as e:
            indicators = {"error": f"Could not compute indicators: {e}"}
            print(f"[technical_analyst] Indicator computation failed for {ticker}: {e}")

        try:
            signal = self.analysis.get_signal(ticker)
        except Exception as e:
            signal = {"signal": "N/A", "confidence": 0, "error": str(e)}
            print(f"[technical_analyst] Signal computation failed for {ticker}: {e}")

        try:
            price_history = self.data.get_price_history(ticker, period="1y")
        except Exception as e:
            price_history = {"error": str(e)}
            print(f"[technical_analyst] Price history failed for {ticker}: {e}")
            
        try:
            backtest_results = self.analysis.backtest_strategy(ticker, period="2y")
        except Exception as e:
            backtest_results = {"error": str(e)}
            print(f"[technical_analyst] Backtest failed for {ticker}: {e}")

        context = f"""## Technical Indicators for {ticker.upper()}

### Current Signal: {signal.get('signal', 'N/A')} (Confidence: {signal.get('confidence', 0)}%)
Trend Strength: {signal.get('trend_strength', 'N/A')}
Bullish Signals: {signal.get('bullish_signals', 0)} | Bearish: {signal.get('bearish_signals', 0)} | Neutral: {signal.get('neutral_signals', 0)}

### Price History ({price_history.get('period', '1y')})
Start: ${price_history.get('start_price', 'N/A')} → End: ${price_history.get('end_price', 'N/A')}
52W High: ${price_history.get('high', 'N/A')} | 52W Low: ${price_history.get('low', 'N/A')}
Total Return: {price_history.get('total_return_pct', 'N/A')}%
Annualized Volatility: {price_history.get('volatility', 'N/A')}%

### Strategy Backtest Performance (2Y SMA Crossover)
{json.dumps(backtest_results, indent=2, default=str)}

### All Indicators
{json.dumps(indicators, indent=2, default=str)}
"""

        analysis_prompt = f"""Analyze {ticker.upper()} from a technical perspective.
User Query: {query}

Provide your complete technical analysis following your output structure guidelines.
Include specific price levels, indicator interpretations, and a clear trading signal.
If some data is unavailable, work with what is available and note any limitations."""

        response = await self.call_llm(analysis_prompt, context=context)

        return {
            "agent": "technical_analyst",
            "content": response,
            "indicators": indicators,
            "signal": signal,
            "price_history": price_history,
            "backtest_results": backtest_results,
            "ticker": ticker,
        }

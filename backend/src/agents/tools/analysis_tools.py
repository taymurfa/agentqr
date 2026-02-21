"""Technical indicator computation and financial analysis tools."""

from typing import Optional
import pandas as pd
import numpy as np
from ta import trend, momentum, volatility, volume

from src.ingestion.market_data import MarketDataClient


class AnalysisTools:
    """Technical and fundamental analysis computation tools."""

    def __init__(self):
        self.market_client = MarketDataClient()

    def compute_all_indicators(self, ticker: str, period: str = "1y") -> dict:
        """Compute all technical indicators for a ticker."""
        df = self.market_client.get_ohlcv(ticker, period=period)
        if df.empty or len(df) < 30:
            return {"error": f"Insufficient data for {ticker}"}

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        vol = df["Volume"]

        indicators = {}

        # Trend indicators
        indicators["sma_20"] = round(trend.sma_indicator(close, window=20).iloc[-1], 2)
        indicators["sma_50"] = round(trend.sma_indicator(close, window=50).iloc[-1], 2)
        indicators["sma_200"] = round(trend.sma_indicator(close, window=200).iloc[-1], 2) if len(df) >= 200 else None
        indicators["ema_12"] = round(trend.ema_indicator(close, window=12).iloc[-1], 2)
        indicators["ema_26"] = round(trend.ema_indicator(close, window=26).iloc[-1], 2)

        macd_obj = trend.MACD(close)
        indicators["macd"] = round(macd_obj.macd().iloc[-1], 4)
        indicators["macd_signal"] = round(macd_obj.macd_signal().iloc[-1], 4)
        indicators["macd_histogram"] = round(macd_obj.macd_diff().iloc[-1], 4)

        adx_obj = trend.ADXIndicator(high, low, close)
        indicators["adx"] = round(adx_obj.adx().iloc[-1], 2)

        # Momentum indicators
        indicators["rsi_14"] = round(momentum.rsi(close, window=14).iloc[-1], 2)

        stoch = momentum.StochasticOscillator(high, low, close)
        indicators["stoch_k"] = round(stoch.stoch().iloc[-1], 2)
        indicators["stoch_d"] = round(stoch.stoch_signal().iloc[-1], 2)

        indicators["williams_r"] = round(momentum.williams_r(high, low, close).iloc[-1], 2)
        indicators["roc"] = round(momentum.roc(close, window=10).iloc[-1], 2)

        # Volatility indicators
        bb = volatility.BollingerBands(close)
        indicators["bb_upper"] = round(bb.bollinger_hband().iloc[-1], 2)
        indicators["bb_middle"] = round(bb.bollinger_mavg().iloc[-1], 2)
        indicators["bb_lower"] = round(bb.bollinger_lband().iloc[-1], 2)
        indicators["bb_width"] = round(bb.bollinger_wband().iloc[-1], 4)

        indicators["atr_14"] = round(volatility.average_true_range(high, low, close, window=14).iloc[-1], 2)

        # Volume indicators
        indicators["obv"] = int(volume.on_balance_volume(close, vol).iloc[-1])
        indicators["volume_sma_20"] = int(vol.rolling(20).mean().iloc[-1])

        indicators["current_price"] = round(close.iloc[-1], 2)
        indicators["date"] = str(df.index[-1].date())

        return indicators

    def get_signal(self, ticker: str) -> dict:
        """Generate a consolidated technical signal."""
        indicators = self.compute_all_indicators(ticker)
        if "error" in indicators:
            return indicators

        price = indicators["current_price"]
        signals = {"bullish": 0, "bearish": 0, "neutral": 0}

        # RSI signal
        rsi = indicators.get("rsi_14", 50)
        if rsi < 30:
            signals["bullish"] += 2
        elif rsi < 40:
            signals["bullish"] += 1
        elif rsi > 70:
            signals["bearish"] += 2
        elif rsi > 60:
            signals["bearish"] += 1
        else:
            signals["neutral"] += 1

        # MACD signal
        macd_hist = indicators.get("macd_histogram", 0)
        if macd_hist > 0:
            signals["bullish"] += 1
        elif macd_hist < 0:
            signals["bearish"] += 1

        # Price vs SMAs
        sma_50 = indicators.get("sma_50")
        sma_200 = indicators.get("sma_200")
        if sma_50 and price > sma_50:
            signals["bullish"] += 1
        elif sma_50:
            signals["bearish"] += 1

        if sma_200 and price > sma_200:
            signals["bullish"] += 1
        elif sma_200:
            signals["bearish"] += 1

        # Golden/Death cross
        if sma_50 and sma_200:
            if sma_50 > sma_200:
                signals["bullish"] += 1
            else:
                signals["bearish"] += 1

        # Bollinger Band position
        bb_upper = indicators.get("bb_upper", price)
        bb_lower = indicators.get("bb_lower", price)
        if price <= bb_lower:
            signals["bullish"] += 1
        elif price >= bb_upper:
            signals["bearish"] += 1

        # ADX trend strength
        adx = indicators.get("adx", 0)
        trend_strength = "strong" if adx > 25 else "weak"

        total = signals["bullish"] + signals["bearish"] + signals["neutral"]
        bull_pct = signals["bullish"] / total if total else 0
        bear_pct = signals["bearish"] / total if total else 0

        if bull_pct > 0.6:
            signal = "Strong Buy" if bull_pct > 0.75 else "Buy"
        elif bear_pct > 0.6:
            signal = "Strong Sell" if bear_pct > 0.75 else "Sell"
        else:
            signal = "Neutral"

        return {
            "ticker": ticker.upper(),
            "signal": signal,
            "confidence": round(max(bull_pct, bear_pct) * 100, 1),
            "trend_strength": trend_strength,
            "bullish_signals": signals["bullish"],
            "bearish_signals": signals["bearish"],
            "neutral_signals": signals["neutral"],
            "indicators": indicators,
        }

    def compute_financial_ratios(self, ticker: str) -> dict:
        """Compute derived financial ratios from statements."""
        financials = self.market_client.get_financials(ticker)
        ratios = self.market_client.get_key_ratios(ticker)

        analysis = {
            "key_ratios": ratios,
            "profitability": {
                "gross_margin": ratios.get("gross_margin"),
                "operating_margin": ratios.get("operating_margin"),
                "profit_margin": ratios.get("profit_margin"),
                "roe": ratios.get("roe"),
                "roa": ratios.get("roa"),
            },
            "leverage": {
                "debt_to_equity": ratios.get("debt_to_equity"),
                "current_ratio": ratios.get("current_ratio"),
                "quick_ratio": ratios.get("quick_ratio"),
            },
            "valuation": {
                "pe_ratio": ratios.get("pe_ratio"),
                "forward_pe": ratios.get("forward_pe"),
                "peg_ratio": ratios.get("peg_ratio"),
                "price_to_book": ratios.get("price_to_book"),
                "ev_to_ebitda": ratios.get("ev_to_ebitda"),
            },
            "growth": {
                "revenue_growth": ratios.get("revenue_growth"),
                "earnings_growth": ratios.get("earnings_growth"),
            },
        }

        # Financial health score (1-10)
        score = 5.0
        pm = ratios.get("profit_margin")
        if pm is not None:
            score += 1.0 if pm > 0.15 else (-1.0 if pm < 0 else 0)

        de = ratios.get("debt_to_equity")
        if de is not None:
            score += 1.0 if de < 50 else (-1.0 if de > 200 else 0)

        cr = ratios.get("current_ratio")
        if cr is not None:
            score += 1.0 if cr > 1.5 else (-1.0 if cr < 1.0 else 0)

        roe_val = ratios.get("roe")
        if roe_val is not None:
            score += 1.0 if roe_val > 0.15 else (-0.5 if roe_val < 0.05 else 0)

        rg = ratios.get("revenue_growth")
        if rg is not None:
            score += 1.0 if rg > 0.10 else (-0.5 if rg < 0 else 0)

        analysis["health_score"] = max(1, min(10, round(score, 1)))

        return analysis

    def backtest_strategy(self, ticker: str, period: str = "2y") -> dict:
        """Run a deterministic backtest using moving average crossover."""
        df = self.market_client.get_ohlcv(ticker, period=period)
        if df.empty or len(df) < 50:
            return {"error": f"Insufficient data to backtest {ticker}"}

        df = df.copy()
        df["sma_20"] = df["Close"].rolling(20).mean()
        df["sma_50"] = df["Close"].rolling(50).mean()

        # Buy when SMA 20 crosses above SMA 50
        df["signal"] = 0
        df.loc[df["sma_20"] > df["sma_50"], "signal"] = 1
        
        # Calculate daily returns
        df["daily_returns"] = df["Close"].pct_change()
        
        # Calculate strategy returns (shift signal by 1 so we execute the day *after* signal)
        df["strategy_returns"] = df["signal"].shift(1) * df["daily_returns"]
        
        # Calculate cumulative returns
        df["cum_market_returns"] = (1 + df["daily_returns"]).cumprod() - 1
        df["cum_strategy_returns"] = (1 + df["strategy_returns"]).cumprod() - 1
        
        # Sharpe Ratio (annualized, assuming ~252 trading days and 4% risk-free rate)
        excess_returns = df["strategy_returns"] - (0.04 / 252)
        if excess_returns.std() == 0:
            sharpe_ratio = 0
        else:
            sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
            
        # Max Drawdown
        cum_returns_plus_one = 1 + df["cum_strategy_returns"]
        rolling_max = cum_returns_plus_one.cummax()
        drawdown = (cum_returns_plus_one - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        total_trades = (df["signal"].diff() != 0).sum() - 1
        win_days = (df["strategy_returns"] > 0).sum()
        loss_days = (df["strategy_returns"] < 0).sum()
        win_rate = win_days / (win_days + loss_days) if (win_days + loss_days) > 0 else 0

        return {
            "strategy_name": "SMA Crossover (20/50)",
            "total_return_pct": round(df["cum_strategy_returns"].iloc[-1] * 100, 2),
            "market_return_pct": round(df["cum_market_returns"].iloc[-1] * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "total_trades": int(total_trades),
            "win_rate_pct": round(win_rate * 100, 2)
        }


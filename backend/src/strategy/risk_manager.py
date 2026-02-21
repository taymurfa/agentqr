"""Risk assessment and position sizing."""

from typing import Optional
import numpy as np
import pandas as pd

from src.ingestion.market_data import MarketDataClient


class RiskManager:
    """Computes risk metrics and suggests position sizes."""

    def __init__(self, portfolio_value: float = 100000):
        self.portfolio_value = portfolio_value
        self.max_position_pct = 0.10  # Max 10% per position
        self.max_sector_pct = 0.30  # Max 30% per sector
        self.market_client = MarketDataClient()

    def compute_risk_metrics(self, ticker: str, period: str = "1y") -> dict:
        """Compute risk metrics for a single ticker."""
        df = self.market_client.get_ohlcv(ticker, period=period)
        if df.empty or len(df) < 20:
            return {"error": f"Insufficient data for {ticker}"}

        returns = df["Close"].pct_change().dropna()

        # Basic metrics
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        annual_return = (df["Close"].iloc[-1] / df["Close"].iloc[0]) ** (252 / len(df)) - 1

        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # Value at Risk (95%)
        var_95 = np.percentile(returns, 5)

        # Sortino ratio (downside deviation)
        downside = returns[returns < 0]
        downside_std = downside.std() * np.sqrt(252)
        sortino = annual_return / downside_std if downside_std > 0 else 0

        return {
            "ticker": ticker.upper(),
            "annual_return": round(annual_return * 100, 2),
            "annual_volatility": round(annual_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(max_drawdown * 100, 2),
            "var_95": round(var_95 * 100, 3),
            "daily_volatility": round(daily_vol * 100, 3),
            "data_points": len(returns),
        }

    def suggest_position_size(
        self,
        ticker: str,
        confidence: float,
        risk_metrics: Optional[dict] = None,
    ) -> dict:
        """Suggest position size based on confidence and risk."""
        if risk_metrics is None:
            risk_metrics = self.compute_risk_metrics(ticker)

        if "error" in risk_metrics:
            return {"error": risk_metrics["error"]}

        vol = risk_metrics["annual_volatility"] / 100
        confidence_pct = confidence / 100

        # Kelly-inspired sizing: scale position by confidence and inverse volatility
        raw_size = confidence_pct * (1 / (1 + vol))
        position_pct = min(raw_size, self.max_position_pct)
        position_value = self.portfolio_value * position_pct

        # Number of shares
        current_price = self.market_client.get_ohlcv(ticker, period="5d")
        if not current_price.empty:
            price = current_price["Close"].iloc[-1]
            shares = int(position_value / price)
        else:
            price = 0
            shares = 0

        return {
            "ticker": ticker.upper(),
            "suggested_allocation_pct": round(position_pct * 100, 2),
            "suggested_value": round(position_value, 2),
            "suggested_shares": shares,
            "current_price": round(price, 2),
            "confidence": confidence,
            "risk_adjusted": True,
        }

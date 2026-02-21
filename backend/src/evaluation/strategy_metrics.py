"""Strategy performance metrics: Sharpe, Sortino, max drawdown, alpha, beta."""

import numpy as np
import pandas as pd
from typing import Optional

from src.ingestion.market_data import MarketDataClient


class StrategyMetrics:
    """Computes portfolio and strategy performance metrics."""

    def __init__(self, risk_free_rate: float = 0.04):
        self.risk_free_rate = risk_free_rate
        self.market_client = MarketDataClient()

    def compute_returns_metrics(self, returns: pd.Series) -> dict:
        """Compute comprehensive return metrics from a return series."""
        if returns.empty:
            return {"error": "Empty returns series"}

        annual_factor = 252
        total_return = (1 + returns).prod() - 1
        annual_return = (1 + total_return) ** (annual_factor / len(returns)) - 1
        daily_vol = returns.std()
        annual_vol = daily_vol * np.sqrt(annual_factor)

        # Sharpe
        excess_return = annual_return - self.risk_free_rate
        sharpe = excess_return / annual_vol if annual_vol > 0 else 0

        # Sortino
        downside = returns[returns < 0]
        downside_std = downside.std() * np.sqrt(annual_factor) if len(downside) > 0 else 0
        sortino = excess_return / downside_std if downside_std > 0 else 0

        # Max drawdown
        cum = (1 + returns).cumprod()
        running_max = cum.cummax()
        drawdowns = (cum - running_max) / running_max
        max_dd = drawdowns.min()

        # Calmar
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

        # VaR
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else var_95

        return {
            "total_return": round(total_return * 100, 2),
            "annual_return": round(annual_return * 100, 2),
            "annual_volatility": round(annual_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "max_drawdown": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 4),
            "var_95": round(var_95 * 100, 3),
            "var_99": round(var_99 * 100, 3),
            "cvar_95": round(cvar_95 * 100, 3),
            "win_rate": round((returns > 0).mean() * 100, 1),
            "trading_days": len(returns),
        }

    def compute_alpha_beta(
        self,
        strategy_returns: pd.Series,
        benchmark_ticker: str = "SPY",
    ) -> dict:
        """Compute alpha and beta vs a benchmark."""
        benchmark_data = self.market_client.get_ohlcv(benchmark_ticker, period="2y")
        if benchmark_data.empty:
            return {"error": "No benchmark data"}

        benchmark_returns = benchmark_data["Close"].pct_change().dropna()

        # Align dates
        aligned = pd.DataFrame({
            "strategy": strategy_returns,
            "benchmark": benchmark_returns,
        }).dropna()

        if len(aligned) < 20:
            return {"error": "Insufficient overlapping data"}

        # Beta = Cov(Rs, Rb) / Var(Rb)
        cov = aligned["strategy"].cov(aligned["benchmark"])
        var_b = aligned["benchmark"].var()
        beta = cov / var_b if var_b > 0 else 0

        # Alpha (annualized) = Rs - (Rf + Beta * (Rb - Rf))
        annual_strat = aligned["strategy"].mean() * 252
        annual_bench = aligned["benchmark"].mean() * 252
        alpha = annual_strat - (self.risk_free_rate + beta * (annual_bench - self.risk_free_rate))

        # Correlation
        correlation = aligned["strategy"].corr(aligned["benchmark"])

        # Information ratio
        active_returns = aligned["strategy"] - aligned["benchmark"]
        tracking_error = active_returns.std() * np.sqrt(252)
        info_ratio = active_returns.mean() * 252 / tracking_error if tracking_error > 0 else 0

        return {
            "alpha": round(alpha * 100, 4),
            "beta": round(beta, 4),
            "correlation": round(correlation, 4),
            "tracking_error": round(tracking_error * 100, 2),
            "information_ratio": round(info_ratio, 4),
            "benchmark": benchmark_ticker,
        }

    def evaluate_strategy(
        self,
        ticker: str,
        signals: list[dict],
        benchmark: str = "SPY",
    ) -> dict:
        """Full strategy evaluation."""
        price_data = self.market_client.get_ohlcv(ticker, period="2y")
        if price_data.empty:
            return {"error": f"No price data for {ticker}"}

        returns = price_data["Close"].pct_change().dropna()

        metrics = self.compute_returns_metrics(returns)
        alpha_beta = self.compute_alpha_beta(returns, benchmark)

        return {
            "ticker": ticker.upper(),
            "performance": metrics,
            "risk_adjusted": alpha_beta,
        }

"""Market data retrieval tools for agents."""

from typing import Optional
from datetime import datetime
import pandas as pd

from src.ingestion.market_data import MarketDataClient


class DataTools:
    """Market data tools available to agents."""

    def __init__(self):
        self.market_client = MarketDataClient()

    def get_current_price(self, ticker: str) -> dict:
        """Get current price and basic stats."""
        df = self.market_client.get_ohlcv(ticker, period="5d", interval="1d")
        if df.empty:
            return {"error": f"No price data for {ticker}"}

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        change = latest["Close"] - prev["Close"]
        change_pct = (change / prev["Close"]) * 100

        return {
            "ticker": ticker.upper(),
            "price": round(latest["Close"], 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": int(latest["Volume"]),
            "high": round(latest["High"], 2),
            "low": round(latest["Low"], 2),
            "date": str(df.index[-1].date()),
        }

    def get_price_history(
        self,
        ticker: str,
        period: str = "1y",
    ) -> dict:
        """Get historical price data summary."""
        df = self.market_client.get_ohlcv(ticker, period=period)
        if df.empty:
            return {"error": f"No data for {ticker}"}

        return {
            "ticker": ticker.upper(),
            "period": period,
            "start_date": str(df.index[0].date()),
            "end_date": str(df.index[-1].date()),
            "start_price": round(df.iloc[0]["Close"], 2),
            "end_price": round(df.iloc[-1]["Close"], 2),
            "high": round(df["High"].max(), 2),
            "low": round(df["Low"].min(), 2),
            "avg_volume": int(df["Volume"].mean()),
            "total_return_pct": round(
                ((df.iloc[-1]["Close"] - df.iloc[0]["Close"]) / df.iloc[0]["Close"]) * 100, 2
            ),
            "volatility": round(df["Close"].pct_change().std() * (252 ** 0.5) * 100, 2),
        }

    def get_company_fundamentals(self, ticker: str) -> dict:
        """Get comprehensive company fundamentals."""
        info = self.market_client.get_company_info(ticker)
        ratios = self.market_client.get_key_ratios(ticker)
        return {**info, "ratios": ratios}

    def get_financial_statements(self, ticker: str) -> dict:
        """Get financial statements."""
        return self.market_client.get_financials(ticker)

    def get_peer_comparison(self, tickers: list[str]) -> list[dict]:
        """Get key metrics for multiple tickers for comparison."""
        peers = []
        for ticker in tickers:
            try:
                ratios = self.market_client.get_key_ratios(ticker)
                info = self.market_client.get_company_info(ticker)
                peers.append({
                    "ticker": ticker.upper(),
                    "name": info.get("name", ticker),
                    "market_cap": info.get("market_cap"),
                    "pe_ratio": ratios.get("pe_ratio"),
                    "ev_to_ebitda": ratios.get("ev_to_ebitda"),
                    "profit_margin": ratios.get("profit_margin"),
                    "revenue_growth": ratios.get("revenue_growth"),
                    "roe": ratios.get("roe"),
                    "debt_to_equity": ratios.get("debt_to_equity"),
                })
            except Exception:
                peers.append({"ticker": ticker.upper(), "error": "Data unavailable"})

        return peers

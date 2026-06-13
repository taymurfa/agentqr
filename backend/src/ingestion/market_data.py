"""yfinance market data integration for OHLCV, fundamentals, and financial statements.
Includes in-memory caching to minimize external API calls."""

from typing import Optional
from datetime import datetime, timedelta
import time as _time
import yfinance as yf
import pandas as pd

# Module-level cache: key -> (data, expiry_time)
_data_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 3600  # 1 hour


def _cache_get(key: str) -> Optional[dict]:
    """Get from cache if not expired."""
    if key in _data_cache:
        data, expiry = _data_cache[key]
        if _time.time() < expiry:
            return data
        del _data_cache[key]
    return None


def _cache_set(key: str, data: dict):
    """Store in cache with TTL."""
    _data_cache[key] = (data, _time.time() + _CACHE_TTL)


class MarketDataClient:
    """Fetches market data from Yahoo Finance."""

    def __init__(self):
        from config.settings import get_settings
        self.settings = get_settings()
        self.poly_key = self.settings.polygon_api_key

    def get_company_info(self, ticker: str) -> dict:
        """Get company profile and basic info, preferring yfinance for proper sector names."""
        ticker = self._clean_ticker(ticker)
        cached = _cache_get(f"info:{ticker}")
        if cached:
            return cached

        # Try yfinance first — it has proper GICS sector/industry names
        try:
            stock = yf.Ticker(ticker, session=self.session)
            info = stock.info or {}
            if info.get("shortName") or info.get("longName"):
                result = {
                    "ticker": ticker.upper(),
                    "name": info.get("longName") or info.get("shortName", ticker),
                    "sector": info.get("sector", "Unknown"),
                    "industry": info.get("industry", "Unknown"),
                    "market_cap": info.get("marketCap"),
                    "description": info.get("longBusinessSummary", ""),
                    "country": info.get("country", ""),
                    "exchange": info.get("exchange", ""),
                    "currency": info.get("currency", "USD"),
                    "website": info.get("website", ""),
                    "employees": info.get("fullTimeEmployees"),
                }
                _cache_set(f"info:{ticker}", result)
                return result
        except Exception as e:
            print(f"yfinance info error for {ticker}: {e}")

        # Fallback to Polygon
        if self.poly_key:
            try:
                import httpx
                url = f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}?apiKey={self.poly_key}"
                res = httpx.get(url)
                if res.status_code == 200:
                    details = res.json().get("results", {})
                    return {
                        "ticker": ticker.upper(),
                        "name": details.get("name", ticker),
                        "sector": details.get("sic_description", "Unknown"),
                        "industry": details.get("sic_description", "Unknown"),
                        "market_cap": details.get("market_cap"),
                        "description": details.get("description", ""),
                        "country": details.get("locale", ""),
                        "exchange": details.get("primary_exchange", ""),
                        "currency": details.get("currency_name", "USD"),
                        "website": details.get("homepage_url", ""),
                        "employees": details.get("total_employees"),
                    }
            except Exception as e:
                print(f"Polygon info error for {ticker}: {e}")

        return {"ticker": ticker.upper(), "name": ticker, "sector": "Unknown", "industry": "Unknown"}

    @staticmethod
    def _clean_ticker(ticker: str) -> str:
        """Strip common garbage characters from ticker symbols before querying APIs."""
        import re
        # Remove $, whitespace, trailing commas/periods, and lowercase
        clean = re.sub(r"[$\s]", "", ticker)
        clean = clean.strip(".,;:")
        return clean.upper()

    def get_ohlcv(
        self,
        ticker: str,
        period: str = "2y",
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Get OHLCV price data, using Polygon as primary and yfinance as backup."""
        ticker = self._clean_ticker(ticker)

        if self.poly_key:
            try:
                interval_map = {
                    "1m": (1, "minute"),
                    "5m": (5, "minute"),
                    "15m": (15, "minute"),
                    "30m": (30, "minute"),
                    "60m": (1, "hour"),
                    "1h": (1, "hour"),
                    "1d": (1, "day"),
                }
                multiplier, timespan = interval_map.get(interval, (1, "day"))

                # Calculate dates for Polygon if not provided
                if not end:
                    end_date = datetime.now()
                else:
                    end_date = datetime.strptime(end, "%Y-%m-%d")
                
                if not start:
                    # Approximation of period
                    period_days = {
                        "1d": 1,
                        "5d": 5,
                        "1mo": 30,
                        "3mo": 90,
                        "6mo": 180,
                        "1y": 365,
                        "2y": 730,
                    }
                    days = period_days.get(period, 365)
                    start_date = end_date - timedelta(days=days)
                else:
                    start_date = datetime.strptime(start, "%Y-%m-%d")

                from polygon import RESTClient
                with RESTClient(self.poly_key) as client:
                    aggs = client.get_aggs(
                        ticker,
                        multiplier,
                        timespan,
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d"),
                        adjusted=True,
                        sort="asc",
                        limit=5000,
                    )
                    if aggs:
                        df = pd.DataFrame(aggs)
                        df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')
                        df = df.set_index('Date')
                        df = df.rename(columns={
                            'open': 'Open',
                            'high': 'High',
                            'low': 'Low',
                            'close': 'Close',
                            'volume': 'Volume',
                            'vwap': 'Adj Close'
                        })
                        return df[['Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close']]
            except Exception as e:
                print(f"Polygon error for {ticker}: {e}. Falling back to yfinance.")

        # Fallback to yfinance — try two approaches
        try:
            stock = yf.Ticker(ticker)
            if start and end:
                df = stock.history(start=start, end=end, interval=interval)
            else:
                df = stock.history(period=period, interval=interval)

            # If yfinance returned empty, try auto_adjust=False as a workaround
            if df is None or df.empty:
                df = stock.history(period=period, interval=interval, auto_adjust=False)

            if df is not None and not df.empty:
                # Normalize column names in case auto_adjust changed them
                df.columns = [c.replace(" ", "_") for c in df.columns]
                if "Close" not in df.columns and "Adj_Close" in df.columns:
                    df["Close"] = df["Adj_Close"]
                return df

        except Exception as e:
            print(f"[market_data] yfinance failed for {ticker}: {e}")

        return pd.DataFrame()



    @staticmethod
    def _df_to_serializable(df: "pd.DataFrame") -> dict:
        """Convert a yfinance financial DataFrame to a JSON-safe dict.
        Converts Timestamp column headers to ISO date strings and replaces NaN/Inf with None.
        """
        import math
        result = {}
        for col in df.columns:
            # Column key: convert Timestamp → "YYYY-MM-DD" string
            col_key = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            result[col_key] = {}
            for row_key, value in df[col].items():
                # Row key: also sanitize (index may be str metric names — usually fine)
                safe_row = str(row_key)
                # Value: replace float NaN / Inf with None
                if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                    result[col_key][safe_row] = None
                else:
                    try:
                        # Convert numpy int/float to Python native
                        result[col_key][safe_row] = value.item() if hasattr(value, "item") else value
                    except Exception:
                        result[col_key][safe_row] = str(value)
        return result

    def get_financials(self, ticker: str) -> dict:
        """Get financial statements (income, balance sheet, cash flow)."""
        ticker = self._clean_ticker(ticker)
        stock = yf.Ticker(ticker)

        result = {}

        try:
            income = stock.financials
            if income is not None and not income.empty:
                result["income_statement"] = self._df_to_serializable(income)
        except Exception as e:
            print(f"[market_data] income statement error for {ticker}: {e}")

        try:
            balance = stock.balance_sheet
            if balance is not None and not balance.empty:
                result["balance_sheet"] = self._df_to_serializable(balance)
        except Exception as e:
            print(f"[market_data] balance sheet error for {ticker}: {e}")

        try:
            cashflow = stock.cashflow
            if cashflow is not None and not cashflow.empty:
                result["cash_flow"] = self._df_to_serializable(cashflow)
        except Exception as e:
            print(f"[market_data] cash flow error for {ticker}: {e}")

        return result


    def get_key_ratios(self, ticker: str) -> dict:
        """Extract key financial ratios from yfinance (preferred) or Polygon (fallback)."""
        cached = _cache_get(f"ratios:{ticker}")
        if cached:
            return cached

        # Try yfinance first — it has pre-computed ratios
        try:
            stock = yf.Ticker(ticker, session=self.session)
            info = stock.info or {}

            ratios = {}
            # Valuation ratios
            if info.get("trailingPE"):
                ratios["pe_ratio"] = round(info["trailingPE"], 2)
            if info.get("forwardPE"):
                ratios["forward_pe"] = round(info["forwardPE"], 2)
            if info.get("pegRatio"):
                ratios["peg_ratio"] = round(info["pegRatio"], 2)
            if info.get("priceToBook"):
                ratios["price_to_book"] = round(info["priceToBook"], 2)
            if info.get("enterpriseToEbitda"):
                ratios["ev_to_ebitda"] = round(info["enterpriseToEbitda"], 2)

            # Profitability
            if info.get("profitMargins") is not None:
                ratios["profit_margin"] = round(info["profitMargins"], 4)
            if info.get("grossMargins") is not None:
                ratios["gross_margin"] = round(info["grossMargins"], 4)
            if info.get("operatingMargins") is not None:
                ratios["operating_margin"] = round(info["operatingMargins"], 4)
            if info.get("returnOnEquity") is not None:
                ratios["roe"] = round(info["returnOnEquity"], 4)
            if info.get("returnOnAssets") is not None:
                ratios["roa"] = round(info["returnOnAssets"], 4)

            # Leverage
            if info.get("debtToEquity") is not None:
                ratios["debt_to_equity"] = round(info["debtToEquity"], 2)
            if info.get("currentRatio") is not None:
                ratios["current_ratio"] = round(info["currentRatio"], 2)
            if info.get("quickRatio") is not None:
                ratios["quick_ratio"] = round(info["quickRatio"], 2)

            # Growth
            if info.get("revenueGrowth") is not None:
                ratios["revenue_growth"] = round(info["revenueGrowth"], 4)
            if info.get("earningsGrowth") is not None:
                ratios["earnings_growth"] = round(info["earningsGrowth"], 4)

            # Dividend
            if info.get("dividendYield") is not None:
                ratios["dividend_yield"] = round(info["dividendYield"], 4)

            if ratios:
                _cache_set(f"ratios:{ticker}", ratios)
                return ratios
        except Exception as e:
            print(f"yfinance ratio error for {ticker}: {e}")

        # Fallback: try Polygon for raw financials
        if self.poly_key:
            try:
                import httpx
                f_url = f"https://api.polygon.io/vX/reference/financials?ticker={ticker.upper()}&limit=1&apiKey={self.poly_key}"
                f_res = httpx.get(f_url)
                f_data = f_res.json().get("results", [{}])[0] if f_res.status_code == 200 else {}

                financials = f_data.get("financials", {})
                income = financials.get("income_statement", {})
                balance = financials.get("balance_sheet", {})

                revenue = income.get("revenues", {}).get("value")
                net_income = income.get("net_income_loss", {}).get("value")
                total_equity = balance.get("equity", {}).get("value")

                ratios = {}
                if revenue and net_income:
                    ratios["profit_margin"] = round(net_income / revenue, 4)
                if total_equity and net_income:
                    ratios["roe"] = round(net_income / total_equity, 4)

                return ratios
            except Exception as e:
                print(f"Polygon ratio error for {ticker}: {e}")

        return {}

    def get_analyst_recommendations(self, ticker: str) -> list[dict]:
        """Get analyst recommendations."""
        stock = yf.Ticker(ticker)
        recs = stock.recommendations
        if recs is None or recs.empty:
            return []

        recent = recs.tail(20)
        return recent.reset_index().to_dict("records")

    def get_fundamentals_text(self, ticker: str) -> str:
        """Generate a text summary of company fundamentals for RAG ingestion."""
        info = self.get_company_info(ticker)
        ratios = self.get_key_ratios(ticker)

        lines = [
            f"Company: {info['name']} ({info['ticker']})",
            f"Sector: {info['sector']} | Industry: {info['industry']}",
            f"Market Cap: ${info.get('market_cap', 0):,.0f}" if info.get("market_cap") else "",
            f"\nDescription: {info.get('description', 'N/A')}",
            "\n--- Key Financial Ratios ---",
        ]

        for key, value in ratios.items():
            if value is not None:
                label = key.replace("_", " ").title()
                if isinstance(value, float):
                    lines.append(f"{label}: {value:.4f}")
                else:
                    lines.append(f"{label}: {value}")

        return "\n".join(line for line in lines if line)

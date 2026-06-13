from fastapi import APIRouter, HTTPException, Query

from src.ingestion.market_data import MarketDataClient

router = APIRouter()


@router.get("/candles/{ticker}")
async def get_candles(
    ticker: str,
    period: str = Query("5d"),
    interval: str = Query("15m"),
    limit: int = Query(120, ge=10, le=500),
):
    """Return OHLCV candles for a ticker using Polygon when configured, with Yahoo fallback."""
    market = MarketDataClient()
    df = market.get_ohlcv(ticker=ticker, period=period, interval=interval)

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No candle data found for {ticker.upper()}")

    candles = []
    for index, row in df.tail(limit).iterrows():
        candles.append(
            {
                "time": index.isoformat() if hasattr(index, "isoformat") else str(index),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]) if "Volume" in row and row["Volume"] == row["Volume"] else None,
            }
        )

    return {
        "ticker": ticker.upper(),
        "period": period,
        "interval": interval,
        "source": "market_data",
        "candles": candles,
    }

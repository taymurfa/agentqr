"""Time-series data operations for OHLCV and indicator storage."""

from datetime import datetime
from typing import Optional
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import PriceData, IndicatorValue


class TimeSeriesStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_ohlcv(self, company_id: str, df: pd.DataFrame):
        """Store OHLCV data from a pandas DataFrame (yfinance format)."""
        for _, row in df.iterrows():
            price = PriceData(
                company_id=company_id,
                date=row.name if isinstance(row.name, datetime) else pd.to_datetime(row.name),
                open=float(row.get("Open", 0)),
                high=float(row.get("High", 0)),
                low=float(row.get("Low", 0)),
                close=float(row.get("Close", 0)),
                volume=float(row.get("Volume", 0)),
                adjusted_close=float(row.get("Adj Close", row.get("Close", 0))),
            )
            self.db.add(price)
        await self.db.commit()

    async def get_ohlcv(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retrieve OHLCV data as a pandas DataFrame."""
        conditions = [PriceData.company_id == company_id]
        if start_date:
            conditions.append(PriceData.date >= start_date)
        if end_date:
            conditions.append(PriceData.date <= end_date)

        stmt = select(PriceData).where(and_(*conditions)).order_by(PriceData.date)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return pd.DataFrame()

        data = [
            {
                "Date": r.date,
                "Open": r.open,
                "High": r.high,
                "Low": r.low,
                "Close": r.close,
                "Volume": r.volume,
                "Adj Close": r.adjusted_close,
            }
            for r in rows
        ]
        df = pd.DataFrame(data).set_index("Date")
        return df

    async def store_indicator(
        self,
        company_id: str,
        indicator_name: str,
        date: datetime,
        value: float,
        metadata: Optional[dict] = None,
    ):
        """Store a single indicator value."""
        ind = IndicatorValue(
            company_id=company_id,
            date=date,
            indicator_name=indicator_name,
            value=value,
            metadata_=metadata,
        )
        self.db.add(ind)
        await self.db.commit()

    async def store_indicators_bulk(
        self,
        company_id: str,
        indicator_name: str,
        series: pd.Series,
    ):
        """Store a pandas Series of indicator values."""
        for date, value in series.items():
            if pd.notna(value):
                ind = IndicatorValue(
                    company_id=company_id,
                    date=pd.to_datetime(date),
                    indicator_name=indicator_name,
                    value=float(value),
                )
                self.db.add(ind)
        await self.db.commit()

    async def get_indicators(
        self,
        company_id: str,
        indicator_names: list[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Retrieve indicator values as a pivoted DataFrame."""
        conditions = [
            IndicatorValue.company_id == company_id,
            IndicatorValue.indicator_name.in_(indicator_names),
        ]
        if start_date:
            conditions.append(IndicatorValue.date >= start_date)
        if end_date:
            conditions.append(IndicatorValue.date <= end_date)

        stmt = select(IndicatorValue).where(and_(*conditions)).order_by(IndicatorValue.date)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return pd.DataFrame()

        data = [{"Date": r.date, "indicator": r.indicator_name, "value": r.value} for r in rows]
        df = pd.DataFrame(data)
        return df.pivot(index="Date", columns="indicator", values="value")

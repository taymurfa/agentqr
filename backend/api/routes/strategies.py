import uuid
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from src.database.connection import get_db
from src.database.models import Strategy

router = APIRouter()


@router.get("/")
async def list_strategies(
    sector: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Strategy).order_by(Strategy.created_at.desc()).limit(limit)
    if sector:
        stmt = stmt.where(Strategy.sector == sector)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "strategies": [
            {
                "id": str(s.id),
                "name": s.name,
                "sector": s.sector,
                "tickers": s.tickers,
                "recommendation": s.recommendation,
                "confidence": s.confidence,
                "sharpe_ratio": s.sharpe_ratio,
                "created_at": str(s.created_at),
            }
            for s in items
        ]
    }


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    try:
        sid = uuid.UUID(strategy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid strategy id")
    stmt = select(Strategy).where(Strategy.id == sid)
    result = await db.execute(stmt)
    s = result.scalar_one_or_none()

    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")

    return {
        "id": str(s.id),
        "name": s.name,
        "sector": s.sector,
        "tickers": s.tickers,
        "recommendation": s.recommendation,
        "rationale": s.rationale,
        "confidence": s.confidence,
        "risk_assessment": s.risk_assessment,
        "sharpe_ratio": s.sharpe_ratio,
        "max_drawdown": s.max_drawdown,
        "backtest_results": s.backtest_results,
        "created_at": str(s.created_at),
    }

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from src.database.connection import get_db
from src.database.models import TradeOrder, TradePosition, TradingAccount
from src.strategy.broker_client import MockBrokerClient, AlpacaBrokerClient
from config.settings import get_settings

router = APIRouter()


class OrderRequest(BaseModel):
    ticker: str
    side: str  # BUY or SELL
    qty: float
    order_type: str = "MARKET"  # MARKET or LIMIT
    limit_price: Optional[float] = None


@router.get("/account")
async def get_account(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if settings.trading_mode == "alpaca":
        broker = AlpacaBrokerClient()
    else:
        broker = MockBrokerClient(db)
    
    try:
        info = await broker.get_account_info()
        info["trading_mode"] = settings.trading_mode
        info["trading_dry_run"] = settings.trading_dry_run
        info["trading_auto_execute"] = settings.trading_auto_execute
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if settings.trading_mode == "alpaca":
        broker = AlpacaBrokerClient()
    else:
        broker = MockBrokerClient(db)
        
    try:
        positions = await broker.get_positions()
        return {"positions": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_orders(limit: int = Query(50, le=100), db: AsyncSession = Depends(get_db)):
    stmt = select(TradeOrder).order_by(TradeOrder.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    orders = res.scalars().all()
    return {
        "orders": [
            {
                "id": str(o.id),
                "ticker": o.ticker,
                "side": o.side,
                "qty": o.qty,
                "order_type": o.order_type,
                "limit_price": o.limit_price,
                "status": o.status,
                "filled_qty": o.filled_qty,
                "avg_fill_price": o.avg_fill_price,
                "agent_rationale": o.agent_rationale,
                "created_at": str(o.created_at),
            }
            for o in orders
        ]
    }


@router.post("/orders")
async def create_manual_order(body: OrderRequest, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if settings.trading_mode == "alpaca":
        broker = AlpacaBrokerClient()
    else:
        broker = MockBrokerClient(db)
        
    try:
        res = await broker.place_order(
            ticker=body.ticker,
            side=body.side,
            qty=body.qty,
            order_type=body.order_type,
            limit_price=body.limit_price,
            agent_rationale="Manual execution bypass",
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle-auto")
async def toggle_auto(enabled: bool):
    settings = get_settings()
    settings.trading_auto_execute = enabled
    return {"status": "success", "trading_auto_execute": settings.trading_auto_execute}


@router.post("/toggle-dry-run")
async def toggle_dry_run(enabled: bool):
    settings = get_settings()
    settings.trading_dry_run = enabled
    return {"status": "success", "trading_dry_run": settings.trading_dry_run}


@router.post("/kill-switch")
async def trigger_kill_switch(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if settings.trading_mode == "alpaca":
        broker = AlpacaBrokerClient()
    else:
        broker = MockBrokerClient(db)
        
    try:
        # Trip circuit breaker in DB
        stmt = select(TradingAccount).where(TradingAccount.is_live == (settings.trading_mode == "alpaca"))
        res = await db.execute(stmt)
        acc = res.scalar_one_or_none()
        if acc:
            acc.circuit_breaker_tripped = True
            await db.commit()
            
        # Cancel all pending orders & liquidate positions
        await broker.cancel_all_orders()
        await broker.liquidate_all_positions()
        
        return {"status": "success", "message": "Emergency Kill Switch activated! All positions liquidated and orders cancelled."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    stmt = select(TradingAccount).where(TradingAccount.is_live == (settings.trading_mode == "alpaca"))
    res = await db.execute(stmt)
    acc = res.scalar_one_or_none()
    if acc:
        acc.circuit_breaker_tripped = False
        await db.commit()
        return {"status": "success", "message": "Circuit breaker reset."}
    return {"status": "failed", "message": "No account found to reset."}

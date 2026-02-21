from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from src.database.connection import get_db

router = APIRouter()


class IngestRequest(BaseModel):
    ticker: str
    sources: list[str] = ["sec_filings", "market_data", "news"]
    filing_types: list[str] = ["10-K", "10-Q"]
    num_filings: int = 5


class BulkIngestRequest(BaseModel):
    tickers: list[str]
    sources: list[str] = ["sec_filings", "market_data", "news"]


@router.post("/ticker")
async def ingest_ticker(
    body: IngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Ingest all data for a single ticker — also ensures company record is populated."""
    from sqlalchemy import select
    from src.database.models import Company
    from src.ingestion.market_data import MarketDataClient

    ticker = body.ticker.upper()

    # Immediately create/update the company record so the UI shows data right away
    stmt = select(Company).where(Company.ticker == ticker)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    try:
        market_client = MarketDataClient()
        info = market_client.get_company_info(ticker)
        ratios = market_client.get_key_ratios(ticker)

        if not company:
            company = Company(
                ticker=ticker,
                name=info.get("name", ticker),
                sector=info.get("sector"),
                industry=info.get("industry"),
                market_cap=info.get("market_cap"),
                description=info.get("description"),
                fundamentals=ratios,
            )
            db.add(company)
        else:
            company.name = info.get("name", company.name or ticker)
            company.sector = info.get("sector", company.sector)
            company.industry = info.get("industry", company.industry)
            company.market_cap = info.get("market_cap", company.market_cap)
            company.description = info.get("description", company.description)
            company.fundamentals = ratios

        await db.commit()
    except Exception as e:
        print(f"Warning: Could not fetch company info for {ticker}: {e}")
        await db.rollback()
        # Still create a minimal record if none exists
        if not company:
            company = Company(ticker=ticker, name=ticker)
            db.add(company)
            await db.commit()

    # Start background ingestion (SEC filings, vector embeddings, etc.)
    from workers.ingestion_worker import ingest_company_data
    background_tasks.add_task(
        ingest_company_data,
        ticker=body.ticker,
        sources=body.sources,
        filing_types=body.filing_types,
        num_filings=body.num_filings,
    )

    return {
        "status": "ingestion_started",
        "ticker": ticker,
        "name": company.name if company else ticker,
        "sector": company.sector if company else None,
        "sources": body.sources,
    }


@router.post("/bulk")
async def ingest_bulk(
    body: BulkIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Ingest data for multiple tickers."""
    from workers.ingestion_worker import ingest_company_data

    for ticker in body.tickers:
        background_tasks.add_task(
            ingest_company_data,
            ticker=ticker,
            sources=body.sources,
        )

    return {
        "status": "bulk_ingestion_started",
        "tickers": body.tickers,
        "count": len(body.tickers),
    }


@router.get("/status/{ticker}")
async def ingestion_status(ticker: str, db: AsyncSession = Depends(get_db)):
    """Check ingestion status for a ticker."""
    from sqlalchemy import select, func
    from src.database.models import AgentLog

    stmt = (
        select(AgentLog)
        .where(AgentLog.agent_name == "ingestion")
        .where(AgentLog.message.contains(ticker.upper()))
        .order_by(AgentLog.created_at.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "ticker": ticker,
        "logs": [
            {"status": l.status, "message": l.message, "created_at": str(l.created_at)}
            for l in logs
        ],
    }

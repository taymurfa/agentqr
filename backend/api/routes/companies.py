from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from src.database.connection import get_db
from src.database.models import Company

router = APIRouter()


@router.get("/")
async def list_companies(
    sector: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company).offset(offset).limit(limit)
    if sector:
        stmt = stmt.where(Company.sector == sector)
    stmt = stmt.order_by(Company.ticker)

    result = await db.execute(stmt)
    companies = result.scalars().all()

    return {
        "companies": [
            {
                "id": str(c.id),
                "ticker": c.ticker,
                "name": c.name or c.ticker,
                "sector": c.sector or "Unknown",
                "industry": c.industry,
                "market_cap": c.market_cap,
                "description": c.description,
                "has_research": bool(c.research_summary),
                "fundamentals": c.fundamentals,
                "last_updated": str(c.updated_at) if c.updated_at else None,
            }
            for c in companies
        ]
    }


@router.get("/{ticker}")
async def get_company(ticker: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Company).where(Company.ticker == ticker.upper())
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        # Try to fetch it from yfinance on the fly
        try:
            from src.ingestion.market_data import MarketDataClient
            market_client = MarketDataClient()
            info = market_client.get_company_info(ticker)
            ratios = market_client.get_key_ratios(ticker)

            company = Company(
                ticker=ticker.upper(),
                name=info.get("name", ticker),
                sector=info.get("sector"),
                industry=info.get("industry"),
                market_cap=info.get("market_cap"),
                description=info.get("description"),
                fundamentals=ratios,
            )
            db.add(company)
            await db.commit()
            await db.refresh(company)
        except Exception:
            return {"error": f"Company {ticker} not found"}
    elif (
        not company.market_cap
        or not company.sector
        or company.name == company.ticker
        or company.sector.isupper()  # Polygon SIC codes like "ELECTRONIC COMPUTERS"
        or (company.fundamentals and "market_cap_label" in (company.fundamentals or {}))  # Old format
        or (company.fundamentals and "pe_ratio" not in (company.fundamentals or {}))  # Missing real ratios
    ):
        # Auto-update stale/incomplete records
        try:
            from src.ingestion.market_data import MarketDataClient
            market_client = MarketDataClient()
            info = market_client.get_company_info(ticker)
            ratios = market_client.get_key_ratios(ticker)

            company.name = info.get("name", company.name)
            company.sector = info.get("sector", company.sector)
            company.industry = info.get("industry", company.industry)
            company.market_cap = info.get("market_cap", company.market_cap)
            company.description = info.get("description", company.description)
            company.fundamentals = ratios or company.fundamentals
            await db.commit()
            await db.refresh(company)
        except Exception as e:
            print(f"Warning: Could not update company info for {ticker}: {e}")

    return {
        "id": str(company.id),
        "ticker": company.ticker,
        "name": company.name or company.ticker,
        "sector": company.sector or "Unknown",
        "industry": company.industry or "Unknown",
        "market_cap": company.market_cap,
        "description": company.description,
        "research_summary": company.research_summary,
        "fundamentals": company.fundamentals or {},
        "has_research": bool(company.research_summary),
        "created_at": str(company.created_at),
        "updated_at": str(company.updated_at) if company.updated_at else None,
    }

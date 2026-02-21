"""Structured JSON export for research results."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Company, Strategy, Filing


class JSONExporter:
    """Exports research data as structured JSON."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_company_research(self, ticker: str) -> dict:
        """Export full research data for a company as JSON."""
        stmt = select(Company).where(Company.ticker == ticker.upper())
        result = await self.db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            return {"error": f"Company {ticker} not found"}

        filing_stmt = select(Filing).where(Filing.company_id == company.id).order_by(Filing.filing_date.desc())
        filing_result = await self.db.execute(filing_stmt)
        filings = filing_result.scalars().all()

        strategy_stmt = select(Strategy).where(Strategy.tickers.contains([ticker.upper()])).order_by(Strategy.created_at.desc()).limit(5)
        strategy_result = await self.db.execute(strategy_stmt)
        strategies = strategy_result.scalars().all()

        return {
            "export_date": datetime.utcnow().isoformat(),
            "company": {
                "ticker": company.ticker,
                "name": company.name,
                "sector": company.sector,
                "industry": company.industry,
                "market_cap": company.market_cap,
                "description": company.description,
                "research_summary": company.research_summary,
                "fundamentals": company.fundamentals,
            },
            "filings": [
                {
                    "type": f.filing_type,
                    "date": str(f.filing_date) if f.filing_date else None,
                    "accession_number": f.accession_number,
                    "url": f.url,
                    "summary": f.content_summary,
                    "sections": f.sections,
                }
                for f in filings
            ],
            "strategies": [
                {
                    "name": s.name,
                    "recommendation": s.recommendation,
                    "confidence": s.confidence,
                    "rationale": s.rationale,
                    "risk_assessment": s.risk_assessment,
                    "sharpe_ratio": s.sharpe_ratio,
                    "created_at": str(s.created_at),
                }
                for s in strategies
            ],
        }

    async def export_sector_overview(self, sector: str) -> dict:
        """Export research overview for an entire sector."""
        stmt = select(Company).where(Company.sector == sector).order_by(Company.ticker)
        result = await self.db.execute(stmt)
        companies = result.scalars().all()

        return {
            "export_date": datetime.utcnow().isoformat(),
            "sector": sector,
            "company_count": len(companies),
            "companies": [
                {
                    "ticker": c.ticker,
                    "name": c.name,
                    "market_cap": c.market_cap,
                    "research_summary": c.research_summary,
                }
                for c in companies
            ],
        }

    def to_json_string(self, data: dict, indent: int = 2) -> str:
        return json.dumps(data, indent=indent, default=str)

"""Background worker for data ingestion tasks."""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.models import Company, Filing, AgentLog
from src.database.timeseries import TimeSeriesStore
from src.ingestion.sec_edgar import SECEdgarClient
from src.ingestion.market_data import MarketDataClient
from src.ingestion.news_feeds import NewsFeedClient
from src.knowledge_base.document_processor import DocumentProcessor


async def ingest_company_data(
    ticker: str,
    sources: list[str] = None,
    filing_types: list[str] = None,
    num_filings: int = 5,
):
    """Full ingestion pipeline for a single company."""
    sources = sources or ["sec_filings", "market_data", "news"]
    filing_types = filing_types or ["10-K", "10-Q"]
    job_id = str(uuid.uuid4())[:8]

    async with async_session() as db:
        await _log(db, job_id, "ingestion", "started", f"Starting ingestion for {ticker.upper()}")

        try:
            company = await _ensure_company(db, ticker)

            if "market_data" in sources:
                await _ingest_market_data(db, job_id, company, ticker)

            if "sec_filings" in sources:
                await _ingest_sec_filings(db, job_id, company, ticker, filing_types, num_filings)

            if "news" in sources:
                await _ingest_news(db, job_id, ticker)

            await _log(db, job_id, "ingestion", "completed", f"Ingestion complete for {ticker.upper()}")

        except Exception as e:
            await _log(db, job_id, "ingestion", "failed", f"Ingestion failed for {ticker}: {str(e)}")
            raise


async def _ensure_company(db: AsyncSession, ticker: str) -> Company:
    """Ensure company exists in DB, creating it from market data if needed."""
    stmt = select(Company).where(Company.ticker == ticker.upper())
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        market_client = MarketDataClient()
        info = market_client.get_company_info(ticker)

        company = Company(
            ticker=info["ticker"],
            name=info["name"],
            sector=info.get("sector"),
            industry=info.get("industry"),
            market_cap=info.get("market_cap"),
            description=info.get("description"),
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)

    return company


async def _ingest_market_data(db: AsyncSession, job_id: str, company: Company, ticker: str):
    """Ingest OHLCV data and fundamentals."""
    await _log(db, job_id, "ingestion", "running", f"Ingesting market data for {ticker}")

    market_client = MarketDataClient()
    ts_store = TimeSeriesStore(db)
    doc_processor = DocumentProcessor()

    # OHLCV data
    df = market_client.get_ohlcv(ticker, period="2y")
    if not df.empty:
        await ts_store.store_ohlcv(company.id, df)

    # Fundamentals as text for RAG
    fundamentals_text = market_client.get_fundamentals_text(ticker)
    doc_processor.process_text(
        text=fundamentals_text,
        metadata={
            "ticker": ticker.upper(),
            "source": "yfinance",
            "document_type": "fundamentals",
            "date": datetime.utcnow().isoformat(),
        },
        namespace=ticker.lower(),
    )

    # Store key ratios in company record
    ratios = market_client.get_key_ratios(ticker)
    company.fundamentals = ratios
    company.updated_at = datetime.utcnow()
    await db.commit()


async def _ingest_sec_filings(
    db: AsyncSession,
    job_id: str,
    company: Company,
    ticker: str,
    filing_types: list[str],
    num_filings: int,
):
    """Ingest SEC filings."""
    sec_client = SECEdgarClient()
    doc_processor = DocumentProcessor()

    for filing_type in filing_types:
        await _log(db, job_id, "ingestion", "running",
                   f"Fetching {filing_type} filings for {ticker}")

        filings = sec_client.get_filing(ticker, filing_type, count=num_filings)

        for filing_data in filings:
            # Check if already ingested
            existing = await db.execute(
                select(Filing).where(Filing.accession_number == filing_data.accession_number)
            )
            if existing.scalar_one_or_none():
                continue

            # Process and store in vector DB
            vector_ids = doc_processor.process_sec_filing(
                content=filing_data.content,
                ticker=ticker,
                filing_type=filing_type,
                filing_date=filing_data.filing_date,
                namespace=ticker.lower(),
            )

            # Store filing record in PostgreSQL
            filing_record = Filing(
                company_id=company.id,
                filing_type=filing_type,
                filing_date=datetime.strptime(filing_data.filing_date, "%Y-%m-%d"),
                accession_number=filing_data.accession_number,
                url=filing_data.url,
                content_summary=filing_data.content[:500],
                sections=list(filing_data.sections.keys()),
                vector_ids=vector_ids,
            )
            db.add(filing_record)

        await db.commit()

    if not company.cik:
        cik = sec_client.get_cik(ticker)
        if cik:
            company.cik = cik
            await db.commit()


async def _ingest_news(db: AsyncSession, job_id: str, ticker: str):
    """Ingest news articles for a ticker."""
    await _log(db, job_id, "ingestion", "running", f"Fetching news for {ticker}")

    news_client = NewsFeedClient()
    doc_processor = DocumentProcessor()

    articles = news_client.fetch_ticker_news(ticker, max_items=15)

    for article in articles:
        if article.content and len(article.content) > 50:
            doc_processor.process_news(
                article_text=article.content,
                ticker=ticker,
                source=article.source,
                published_date=article.published_date,
                title=article.title,
                namespace=ticker.lower(),
            )


async def _log(db: AsyncSession, job_id: str, agent: str, status: str, message: str):
    """Write an agent log entry."""
    log = AgentLog(
        id=uuid.uuid4(),
        job_id=job_id,
        agent_name=agent,
        status=status,
        message=message,
    )
    db.add(log)
    await db.commit()

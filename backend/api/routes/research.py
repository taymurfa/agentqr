from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from src.database.connection import get_db

router = APIRouter()


class ResearchRequest(BaseModel):
    ticker: str
    sector: Optional[str] = None
    depth: str = "standard"  # "quick", "standard", "deep"


class CompareRequest(BaseModel):
    tickers: list[str]
    metrics: list[str] = ["fundamentals", "technicals", "sentiment"]


@router.post("/run")
async def trigger_research(
    body: ResearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a research job for a given ticker — returns full synthesis."""
    from src.agents.orchestrator import OrchestratorAgent

    try:
        orchestrator = OrchestratorAgent(db)
        result = await orchestrator.research(
            ticker=body.ticker,
            sector=body.sector,
            depth=body.depth,
        )

        # Auto-generate a Strategy record from the research results
        try:
            await _create_strategy_from_research(db, body.ticker, result)
        except Exception as e:
            print(f"Strategy creation failed (non-fatal): {e}")

        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_companies(body: CompareRequest, db: AsyncSession = Depends(get_db)):
    """Compare multiple companies across specified metrics."""
    from src.agents.orchestrator import OrchestratorAgent

    try:
        orchestrator = OrchestratorAgent(db)
        result = await orchestrator.compare(tickers=body.tickers, metrics=body.metrics)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}")
async def get_research_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get status of a running research job."""
    from sqlalchemy import select
    from src.database.models import AgentLog

    stmt = select(AgentLog).where(AgentLog.job_id == job_id).order_by(AgentLog.created_at.desc())
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return {
        "job_id": job_id,
        "logs": [{"agent": l.agent_name, "status": l.status, "message": l.message} for l in logs],
    }


@router.get("/summary/{ticker}")
async def get_research_summary(ticker: str, db: AsyncSession = Depends(get_db)):
    """Get the latest research summary for a ticker."""
    from sqlalchemy import select
    from src.database.models import Company

    stmt = select(Company).where(Company.ticker == ticker.upper())
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        return {"error": f"No research found for {ticker}"}

    return {
        "ticker": company.ticker,
        "name": company.name,
        "sector": company.sector,
        "research_summary": company.research_summary,
        "fundamentals": company.fundamentals,
        "last_updated": str(company.updated_at) if company.updated_at else None,
    }


async def _create_strategy_from_research(db: AsyncSession, ticker: str, result: dict):
    """Auto-generate a Strategy record from the research synthesis."""
    import re
    from src.database.models import Strategy

    synthesis = result.get("synthesis", "")
    if not synthesis or len(synthesis) < 50:
        return

    # Try to extract signal/recommendation from the synthesis
    recommendation = "Hold"  # default
    confidence = 50.0

    text_lower = synthesis.lower()
    if "strong buy" in text_lower:
        recommendation = "Strong Buy"
        confidence = 85.0
    elif "strong sell" in text_lower:
        recommendation = "Strong Sell"
        confidence = 85.0
    elif "buy" in text_lower and "sell" not in text_lower[:text_lower.index("buy") + 30]:
        recommendation = "Buy"
        confidence = 70.0
    elif "sell" in text_lower:
        recommendation = "Sell"
        confidence = 70.0
    elif "hold" in text_lower or "neutral" in text_lower:
        recommendation = "Hold"
        confidence = 60.0

    # Extract confidence score if present (e.g. "confidence: 75%" or "confidence score: 0.75")
    conf_match = re.search(r'confidence[:\s]+(\d+(?:\.\d+)?)\s*%?', text_lower)
    if conf_match:
        val = float(conf_match.group(1))
        confidence = val if val > 1 else val * 100

    # Look for technical analyst results
    sharpe_ratio = None
    max_drawdown = None
    backtest_data = None
    
    for ar in result.get("agent_results", []):
        if ar.get("agent") == "technical_analyst":
            bt = ar.get("backtest_results", {})
            if bt and "error" not in bt:
                sharpe_ratio = bt.get("sharpe_ratio")
                max_drawdown = bt.get("max_drawdown_pct")
                backtest_data = bt

    strategy = Strategy(
        name=f"{ticker.upper()} Research Strategy",
        sector=result.get("sector"),
        tickers=[ticker.upper()],
        recommendation=recommendation,
        rationale=synthesis[:2000],
        confidence=round(confidence, 1),
        risk_assessment=None,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        backtest_results=backtest_data,
        agent_outputs=result.get("agent_results"),
    )
    db.add(strategy)
    await db.commit()

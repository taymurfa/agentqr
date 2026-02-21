from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from src.database.connection import get_db
from src.database.models import AgentLog, Company, Strategy

router = APIRouter()


@router.get("/overview")
async def monitoring_overview(db: AsyncSession = Depends(get_db)):
    """Get monitoring overview with agent stats, recent activity, and system status."""

    # Agent call counts
    agent_stats_stmt = (
        select(
            AgentLog.agent_name,
            func.count(AgentLog.id).label("total_calls"),
            func.sum(AgentLog.tokens_used).label("total_tokens"),
            func.avg(AgentLog.latency_ms).label("avg_latency"),
        )
        .group_by(AgentLog.agent_name)
    )
    result = await db.execute(agent_stats_stmt)
    agent_rows = result.all()

    agent_stats = {}
    for row in agent_rows:
        agent_stats[row[0]] = {
            "total_calls": row[1],
            "total_tokens": int(row[2] or 0),
            "avg_latency_ms": round(row[3] or 0, 1),
        }

    # Recent activity (last 20 logs)
    recent_stmt = (
        select(AgentLog)
        .order_by(desc(AgentLog.created_at))
        .limit(20)
    )
    result = await db.execute(recent_stmt)
    recent_logs = result.scalars().all()

    recent_activity = [
        {
            "agent": l.agent_name,
            "status": l.status,
            "message": l.message,
            "tokens": l.tokens_used or 0,
            "latency_ms": l.latency_ms or 0,
            "created_at": str(l.created_at),
        }
        for l in recent_logs
    ]

    # Company count
    company_count_result = await db.execute(select(func.count(Company.id)))
    company_count = company_count_result.scalar() or 0

    # Strategy count
    strategy_count_result = await db.execute(select(func.count(Strategy.id)))
    strategy_count = strategy_count_result.scalar() or 0

    # Total tokens used
    tokens_result = await db.execute(select(func.sum(AgentLog.tokens_used)))
    total_tokens = tokens_result.scalar() or 0

    return {
        "agent_stats": agent_stats,
        "recent_activity": recent_activity,
        "system": {
            "companies_ingested": company_count,
            "strategies_generated": strategy_count,
            "total_tokens_used": total_tokens,
            "total_agent_calls": sum(s["total_calls"] for s in agent_stats.values()),
        },
    }

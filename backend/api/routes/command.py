"""POST /api/command — orchestrator entry point.

Kicks off the research pipeline as a background task and returns a job_id.
Also exposes GET /api/command/{job_id} for status polling and
GET /api/agent-events for the UI activity feed.
"""

from __future__ import annotations

import json
import uuid
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session, get_db
from src.database.models import AgentLog
from src.agents.research_pipeline import JOBS, run_pipeline

router = APIRouter()


class CommandRequest(BaseModel):
    command: str


@router.post("/command")
async def submit_command(payload: CommandRequest):
    if not payload.command.strip():
        raise HTTPException(status_code=400, detail="command is required")
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "command": payload.command,
        "created_at": datetime.utcnow().isoformat(),
    }
    # Fire-and-forget; pipeline manages its own sessions.
    asyncio.create_task(run_pipeline(async_session, job_id, payload.command))
    return {"job_id": job_id, "status": "running"}


@router.get("/command/{job_id}")
async def get_command_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.get("/agent-events/stream")
async def stream_agent_events(request: Request, job_id: Optional[str] = None):
    """Server-Sent Events stream of new AgentLog rows.

    On connect: replays the latest 20 rows, then emits each new row as it lands.
    The frontend uses EventSource to subscribe.
    """

    async def gen():
        last_id: Optional[str] = None

        async with async_session() as db:
            stmt = select(AgentLog).order_by(desc(AgentLog.created_at)).limit(20)
            if job_id:
                stmt = (
                    select(AgentLog).where(AgentLog.job_id == job_id)
                    .order_by(desc(AgentLog.created_at)).limit(20)
                )
            rows = (await db.execute(stmt)).scalars().all()
            for r in reversed(rows):
                yield _format_event(r)
            if rows:
                last_id = str(rows[0].id)

        # Tail loop: poll DB ~2x/sec for new rows, send as SSE.
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.5)
            async with async_session() as db:
                stmt = select(AgentLog).order_by(desc(AgentLog.created_at)).limit(20)
                if job_id:
                    stmt = (
                        select(AgentLog).where(AgentLog.job_id == job_id)
                        .order_by(desc(AgentLog.created_at)).limit(20)
                    )
                rows = (await db.execute(stmt)).scalars().all()
            # Emit rows newer than last_id, in chronological order.
            new_rows = []
            for r in rows:
                if str(r.id) == last_id:
                    break
                new_rows.append(r)
            for r in reversed(new_rows):
                yield _format_event(r)
            if rows:
                last_id = str(rows[0].id)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_event(r: AgentLog) -> str:
    payload = {
        "id": str(r.id),
        "job_id": r.job_id,
        "agent": r.agent_name,
        "status": r.status,
        "message": r.message,
        "latency_ms": r.latency_ms or 0,
        "created_at": str(r.created_at),
    }
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/agent-events")
async def list_agent_events(
    limit: int = 30,
    job_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentLog).order_by(desc(AgentLog.created_at)).limit(min(limit, 100))
    if job_id:
        stmt = select(AgentLog).where(AgentLog.job_id == job_id).order_by(desc(AgentLog.created_at)).limit(min(limit, 100))
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "events": [
            {
                "id": str(r.id),
                "job_id": r.job_id,
                "agent": r.agent_name,
                "status": r.status,
                "message": r.message,
                "latency_ms": r.latency_ms or 0,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
    }

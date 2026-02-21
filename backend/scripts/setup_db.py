"""Initialize database tables."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import engine, Base
from src.database.models import (
    Company, Filing, PriceData, IndicatorValue,
    Strategy, AgentLog, PerformanceMetric,
    ChatSession, Message,
)


async def init_db():
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())

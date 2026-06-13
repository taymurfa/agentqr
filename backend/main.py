from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from config.settings import get_settings
from api.routes import chat, research, companies, strategies, ingestion, health, monitoring, trading, market, command
from src.database.connection import engine, Base, async_session
from workers.trading_worker import start_trading_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Start background trading scheduler
    scheduler_task = asyncio.create_task(start_trading_scheduler(async_session))
    
    yield
    
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
        
    await engine.dispose()


settings = get_settings()

app = FastAPI(
    title="Agentic Quant Researcher",
    description="Multi-agent RAG system for quantitative research",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(ingestion.router, prefix="/api/ingestion", tags=["ingestion"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(trading.router, prefix="/api/trading", tags=["trading"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(command.router, prefix="/api", tags=["command"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=False)

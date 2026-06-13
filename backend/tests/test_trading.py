import pytest
import pytest_asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.database.connection import Base
from src.database.models import TradingAccount, TradeOrder, TradePosition, Company
from src.strategy.broker_client import MockBrokerClient
from src.agents.trading_agent import TradingAgent


@pytest_asyncio.fixture
async def db_session():
    """Setup in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        yield session
        
    await engine.dispose()


@pytest.mark.asyncio
async def test_mock_broker_account_creation(db_session):
    broker = MockBrokerClient(db_session)
    acc = await broker.get_account_info()
    
    assert acc["cash"] == 100000.0
    assert acc["buying_power"] == 100000.0
    assert acc["equity"] == 100000.0
    assert acc["is_live"] is False
    assert acc["circuit_breaker_tripped"] is False


@pytest.mark.asyncio
async def test_mock_broker_place_buy_order(db_session):
    broker = MockBrokerClient(db_session)
    
    # Place a buy order for Apple (AAPL)
    # Note: MockBrokerClient will internally try to fetch current price using yfinance fallback
    res = await broker.place_order(
        ticker="AAPL",
        side="BUY",
        qty=10,
        order_type="MARKET",
    )
    
    # Assert fill or reject based on market data client availability
    if res.get("status") == "FILLED":
        assert res["filled_qty"] == 10
        assert res["avg_fill_price"] > 0
        
        # Check database
        acc = await broker.get_account_info()
        assert acc["cash"] < 100000.0
        
        positions = await broker.get_positions()
        assert len(positions) == 1
        assert positions[0]["ticker"] == "AAPL"
        assert positions[0]["qty"] == 10
    else:
        # If offline or yfinance rate limit hit, check that error exists
        assert "error" in res or res["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_trading(db_session):
    broker = MockBrokerClient(db_session)
    
    # Trip circuit breaker manually in the database
    acc = await broker._get_or_create_account()
    acc.circuit_breaker_tripped = True
    await db_session.commit()
    
    res = await broker.place_order(
        ticker="AAPL",
        side="BUY",
        qty=10,
    )
    
    assert res["status"] == "REJECTED"
    assert "Circuit breaker is active" in res["error"]

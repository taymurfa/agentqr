import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, Integer, DateTime, JSON,
    ForeignKey, Enum as SAEnum, Index, UUID, Boolean,
)
from sqlalchemy.orm import relationship

from src.database.connection import Base


def gen_uuid():
    return uuid.uuid4()


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), index=True)
    industry = Column(String(255))
    market_cap = Column(Float)
    description = Column(Text)
    cik = Column(String(20))
    research_summary = Column(Text)
    fundamentals = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    filings = relationship("Filing", back_populates="company", cascade="all, delete-orphan")
    price_data = relationship("PriceData", back_populates="company", cascade="all, delete-orphan")


class Filing(Base):
    __tablename__ = "filings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    filing_type = Column(String(20), nullable=False)  # 10-K, 10-Q, 8-K
    filing_date = Column(DateTime)
    accession_number = Column(String(50), unique=True)
    url = Column(Text)
    content_summary = Column(Text)
    sections = Column(JSON)
    vector_ids = Column(JSON)  # IDs of chunks stored in Pinecone
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="filings")

    __table_args__ = (Index("ix_filings_company_type", "company_id", "filing_type"),)


class PriceData(Base):
    __tablename__ = "price_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    adjusted_close = Column(Float)

    company = relationship("Company", back_populates="price_data")

    __table_args__ = (
        Index("ix_price_company_date", "company_id", "date", unique=True),
    )


class IndicatorValue(Base):
    __tablename__ = "indicator_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    indicator_name = Column(String(50), nullable=False)  # RSI, MACD, SMA_50, etc.
    value = Column(Float)
    metadata_ = Column("metadata", JSON)

    __table_args__ = (
        Index("ix_indicator_company_date_name", "company_id", "date", "indicator_name"),
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    tickers = Column(JSON)
    recommendation = Column(String(50))  # buy, sell, hold, watch
    rationale = Column(Text)
    confidence = Column(Float)
    risk_assessment = Column(Text)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    backtest_results = Column(JSON)
    agent_outputs = Column(JSON)  # Raw outputs from each agent
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id = Column(String(50), index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # started, running, completed, failed
    message = Column(Text)
    input_data = Column(JSON)
    output_data = Column(JSON)
    tokens_used = Column(Integer)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float)
    metric_type = Column(String(50))  # retrieval, agent, strategy, system
    metadata_ = Column("metadata", JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    title = Column(String(255), default="New Research Chat")
    context = Column(JSON)  # Active research context for this session
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan",
                            order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    agents_used = Column(JSON)
    context_sources = Column(JSON)  # Which documents/data sources were referenced
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (Index("ix_messages_session_created", "session_id", "created_at"),)


class TradingAccount(Base):
    __tablename__ = "trading_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    cash = Column(Float, nullable=False, default=100000.0)
    buying_power = Column(Float, nullable=False, default=100000.0)
    equity = Column(Float, nullable=False, default=100000.0)
    initial_balance = Column(Float, nullable=False, default=100000.0)
    is_live = Column(Boolean, default=False)
    circuit_breaker_tripped = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TradeOrder(Base):
    __tablename__ = "trade_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    strategy_id = Column(UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True)
    ticker = Column(String(10), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY, SELL
    qty = Column(Float, nullable=False)
    order_type = Column(String(20), nullable=False)  # MARKET, LIMIT
    limit_price = Column(Float, nullable=True)
    status = Column(String(20), nullable=False)  # PENDING, FILLED, CANCELED, REJECTED, DRY_RUN
    filled_qty = Column(Float, default=0.0)
    avg_fill_price = Column(Float, nullable=True)
    broker_order_id = Column(String(100), unique=True, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    agent_rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TradePosition(Base):
    __tablename__ = "trade_positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    qty = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    unrealized_pnl_pct = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


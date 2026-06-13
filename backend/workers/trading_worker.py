import asyncio
import logging
import traceback
from datetime import datetime
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select, delete

from config.settings import get_settings
from src.database.models import TradingAccount, TradePosition, TradeOrder, Company
from src.strategy.broker_client import MockBrokerClient, AlpacaBrokerClient
from src.agents.orchestrator import OrchestratorAgent
from src.agents.trading_agent import TradingAgent
from src.strategy.risk_manager import RiskManager

logger = logging.getLogger("trading_worker")
logging.basicConfig(level=logging.INFO)


class TradingWorker:
    """Manages the background execution loop for automated trading and state sync."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self.settings = get_settings()
        
    async def get_broker(self, db: AsyncSession):
        if self.settings.trading_mode == "alpaca":
            return AlpacaBrokerClient()
        return MockBrokerClient(db)

    async def reconcile_portfolio(self):
        """Sync local DB account and positions state with the broker."""
        async with self.session_factory() as db:
            try:
                broker = await self.get_broker(db)
                acc_info = await broker.get_account_info()
                
                # Update account
                stmt = select(TradingAccount).where(TradingAccount.is_live == (self.settings.trading_mode == "alpaca"))
                res = await db.execute(stmt)
                acc = res.scalar_one_or_none()
                
                if not acc:
                    acc = TradingAccount(
                        cash=acc_info["cash"],
                        buying_power=acc_info["buying_power"],
                        equity=acc_info["equity"],
                        initial_balance=acc_info["initial_balance"],
                        is_live=(self.settings.trading_mode == "alpaca"),
                    )
                    db.add(acc)
                else:
                    acc.cash = acc_info["cash"]
                    acc.buying_power = acc_info["buying_power"]
                    acc.equity = acc_info["equity"]
                    acc.updated_at = datetime.utcnow()
                
                await db.commit()

                # Sync positions
                broker_positions = await broker.get_positions()
                
                # Delete all existing local positions first (for simple rebuild reconciliation)
                await db.execute(delete(TradePosition))
                await db.commit()
                
                for bp in broker_positions:
                    pos = TradePosition(
                        ticker=bp["ticker"],
                        qty=bp["qty"],
                        avg_entry_price=bp["avg_entry_price"],
                        current_price=bp["current_price"],
                        market_value=bp["market_value"],
                        unrealized_pnl=bp["unrealized_pnl"],
                        unrealized_pnl_pct=bp["unrealized_pnl_pct"],
                    )
                    db.add(pos)
                
                await db.commit()
                logger.info(f"Successfully reconciled portfolio state. Cash: ${acc_info['cash']:.2f}, Equity: ${acc_info['equity']:.2f}")
            except Exception as e:
                logger.error(f"Error during portfolio reconciliation: {e}")
                traceback.print_exc()

    async def check_circuit_breakers(self) -> bool:
        """Monitor drawdown and trip circuit breaker if limits are exceeded. Returns True if tripped."""
        async with self.session_factory() as db:
            try:
                stmt = select(TradingAccount).where(TradingAccount.is_live == (self.settings.trading_mode == "alpaca"))
                res = await db.execute(stmt)
                acc = res.scalar_one_or_none()
                
                if not acc:
                    return False
                
                if acc.circuit_breaker_tripped:
                    return True

                # Drawdown check
                peak = acc.initial_balance
                current = acc.equity
                drawdown = ((peak - current) / peak) * 100 if peak > 0 else 0.0
                
                if drawdown > self.settings.max_portfolio_drawdown_pct:
                    logger.warning(f"CRITICAL: Drawdown of {drawdown:.2f}% exceeded limit of {self.settings.max_portfolio_drawdown_pct}%! Tripping circuit breaker.")
                    acc.circuit_breaker_tripped = True
                    await db.commit()
                    
                    # Liquidate everything immediately
                    broker = await self.get_broker(db)
                    await broker.cancel_all_orders()
                    await broker.liquidate_all_positions()
                    return True
                
                # Daily loss check (simplified daily realized loss checks can be added here)
                return False
            except Exception as e:
                logger.error(f"Error in circuit breaker check: {e}")
                return False

    async def run_autonomous_scan(self):
        """Find candidate stocks, run full research, and trade based on synthesized strategy."""
        if not self.settings.trading_auto_execute:
            logger.info("Autonomous execution is disabled (TRADING_AUTO_EXECUTE=false). Scanning skipped.")
            return

        logger.info("Starting autonomous trading scan...")
        
        async with self.session_factory() as db:
            try:
                # 1. Fetch watchlist (all companies currently in database)
                stmt = select(Company).limit(10)
                res = await db.execute(stmt)
                companies = res.scalars().all()
                
                if not companies:
                    logger.info("No companies found in database to scan. Scanning skipped.")
                    return

                orchestrator = OrchestratorAgent(db)
                trading_agent = TradingAgent(db)
                risk_manager = RiskManager()
                
                for company in companies:
                    ticker = company.ticker.upper()
                    logger.info(f"Scanning ticker: {ticker}")
                    
                    # Run end-to-end research synthesis
                    # Quick/standard analysis
                    research_res = await orchestrator.research(ticker=ticker, sector=company.sector, depth="standard")
                    synthesis = research_res.get("synthesis", "")
                    
                    # Determine signal from synthesis
                    recommendation = "Hold"
                    synthesis_lower = synthesis.lower()
                    if "strong buy" in synthesis_lower:
                        recommendation = "BUY"
                    elif "buy" in synthesis_lower:
                        recommendation = "BUY"
                    elif "sell" in synthesis_lower:
                        recommendation = "SELL"
                    
                    if recommendation in ("BUY", "SELL"):
                        confidence = 70.0
                        # Check confidence in synthesis
                        import re
                        conf_match = re.search(r'confidence[:\s]+(\d+(?:\.\d+)?)\s*%?', synthesis_lower)
                        if conf_match:
                            confidence = float(conf_match.group(1))
                        
                        # Size position
                        sizing = risk_manager.suggest_position_size(ticker, confidence)
                        suggested_shares = sizing.get("suggested_shares", 0)
                        
                        if suggested_shares > 0 or recommendation == "SELL":
                            # For SELL, check if we own the position
                            own_position = False
                            pos_qty = 0.0
                            stmt_pos = select(TradePosition).where(TradePosition.ticker == ticker)
                            res_pos = await db.execute(stmt_pos)
                            pos = res_pos.scalar_one_or_none()
                            if pos:
                                own_position = True
                                pos_qty = pos.qty
                                
                            if recommendation == "BUY" or (recommendation == "SELL" and own_position):
                                qty_to_trade = suggested_shares if recommendation == "BUY" else pos_qty
                                
                                # Fetch or create latest Strategy ID
                                from src.database.models import Strategy
                                stmt_strat = select(Strategy).order_by(Strategy.created_at.desc()).limit(1)
                                res_strat = await db.execute(stmt_strat)
                                strat = res_strat.scalar_one_or_none()
                                strategy_id = str(strat.id) if strat else None
                                
                                # Call TradingAgent to execute the trade
                                logger.info(f"Agent Action: {recommendation} {qty_to_trade} shares of {ticker}")
                                await trading_agent.run(
                                    query=f"Execute {recommendation} order for {qty_to_trade} shares of {ticker}",
                                    ticker=ticker,
                                    side=recommendation,
                                    suggested_shares=qty_to_trade,
                                    strategy_id=strategy_id,
                                    sector=company.sector,
                                )
                                
                                # Pause to prevent spamming APIs
                                await asyncio.sleep(5)
                                
            except Exception as e:
                logger.error(f"Error in autonomous scan: {e}")
                traceback.print_exc()


async def start_trading_scheduler(session_factory: async_sessionmaker[AsyncSession]):
    """Background scheduler loop to run checks and scans."""
    worker = TradingWorker(session_factory)
    
    # Initial reconciliation
    await worker.reconcile_portfolio()
    
    scan_interval_seconds = 3600  # 1 hour
    sync_interval_seconds = 60    # 1 minute
    
    elapsed = 0
    
    logger.info("Background quantitative trading scheduler started.")
    
    while True:
        try:
            # Reconcile portfolio & check circuit breakers every 1 minute
            await worker.reconcile_portfolio()
            tripped = await worker.check_circuit_breakers()
            
            if tripped:
                logger.warning("Circuit breaker is tripped! Automated execution disabled.")
            
            # Run autonomous ticker scan every 1 hour (if not tripped and auto-execute is on)
            if not tripped and elapsed >= scan_interval_seconds:
                await worker.run_autonomous_scan()
                elapsed = 0
                
            await asyncio.sleep(sync_interval_seconds)
            elapsed += sync_interval_seconds
        except asyncio.CancelledError:
            logger.info("Background quantitative trading scheduler stopped.")
            break
        except Exception as e:
            logger.error(f"Error in trading scheduler loop: {e}")
            await asyncio.sleep(sync_interval_seconds)

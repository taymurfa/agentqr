import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.agents.base_agent import BaseAgent
from src.strategy.broker_client import MockBrokerClient, AlpacaBrokerClient
from src.database.models import TradePosition, TradingAccount, Strategy


class TradingAgent(BaseAgent):
    """Trading agent responsible for executing orders via simulated or live broker endpoints."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, "trading_agent")
        # Load broker client dynamically
        if self.settings.trading_mode == "alpaca":
            self.broker = AlpacaBrokerClient()
        else:
            self.broker = MockBrokerClient(db)

    async def run(self, query: str, **kwargs) -> dict:
        """Process a trade execution query or request.
        
        Args:
            query (str): Description of trade intent (e.g. "Execute BUY for 50 shares of AAPL").
            kwargs:
                ticker (str): Stock ticker symbol.
                side (str): "BUY" or "SELL".
                suggested_shares (int): Calculated position size from RiskManager.
                strategy_id (str): Reference ID of the generated strategy.
                sector (str): Sector of the company.
        """
        ticker = kwargs.get("ticker", "").upper()
        side = kwargs.get("side", "").upper()
        qty = int(kwargs.get("suggested_shares", 0))
        strategy_id = kwargs.get("strategy_id")
        sector = kwargs.get("sector", "unknown")

        await self._log("started", f"Evaluating {side} execution for {qty} shares of {ticker}")

        if not ticker or not side or qty <= 0:
            err = "Invalid order parameters: ticker, side, and quantity must be provided."
            await self._log("failed", err)
            return {"status": "REJECTED", "error": err}

        # 1. Fetch current account info & verify circuit breakers
        acc_info = await self.broker.get_account_info()
        if acc_info.get("circuit_breaker_tripped"):
            err_msg = "Execution aborted: Account circuit breaker is currently active."
            await self._log("failed", err_msg)
            return {"status": "REJECTED", "error": err_msg}

        # 2. Check risk limit: Max position sizing (10%) and Sector exposure (30%)
        # Fetch current positions
        positions = await self.broker.get_positions()
        equity = acc_info.get("equity", 100000.0)

        # Estimate trade value
        df = self.broker.market_client.get_ohlcv(ticker, period="5d")
        if df.empty:
            err_msg = f"Aborted: Price data for {ticker} not available."
            await self._log("failed", err_msg)
            return {"status": "REJECTED", "error": err_msg}
        current_price = float(df["Close"].iloc[-1])
        trade_value = qty * current_price

        # Check single position limit (if BUY)
        if side == "BUY":
            existing_pos_value = 0.0
            for pos in positions:
                if pos["ticker"] == ticker:
                    existing_pos_value = pos["market_value"]
            new_pos_pct = ((existing_pos_value + trade_value) / equity) * 100
            if new_pos_pct > self.settings.max_position_size_pct:
                err_msg = (
                    f"Rejected: Position size would be {new_pos_pct:.2f}% of portfolio "
                    f"(Max allowed: {self.settings.max_position_size_pct}%)."
                )
                await self._log("failed", err_msg)
                return {"status": "REJECTED", "error": err_msg}

            # Check sector exposure (needs company profile to verify sector)
            sector_value = 0.0
            # For simplicity, search database or company model for company sectors
            from src.database.models import Company
            stmt = select(Company).where(Company.sector == sector)
            res = await self.db.execute(stmt)
            companies_in_sector = [c.ticker for c in res.scalars().all()]
            # Include target ticker if it belongs to this sector
            if ticker not in companies_in_sector:
                companies_in_sector.append(ticker)

            for pos in positions:
                if pos["ticker"] in companies_in_sector:
                    sector_value += pos["market_value"]

            new_sector_pct = ((sector_value + trade_value) / equity) * 100
            if new_sector_pct > self.settings.max_sector_exposure_pct:
                err_msg = (
                    f"Rejected: Sector exposure for {sector} would be {new_sector_pct:.2f}% of portfolio "
                    f"(Max allowed: {self.settings.max_sector_exposure_pct}%)."
                )
                await self._log("failed", err_msg)
                return {"status": "REJECTED", "error": err_msg}

        # 3. Call OpenAI/ChatGPT to run LLM verification
        prompt_context = (
            f"Account Equity: ${equity:,.2f}\n"
            f"Cash Available: ${acc_info.get('cash', 0.0):,.2f}\n"
            f"Active Holdings: {json.dumps(positions)}\n"
            f"Requested Trade: {side} {qty} shares of {ticker} (Estimated price: ${current_price:.2f}, total value: ${trade_value:.2f})\n"
            f"Sector: {sector}"
        )
        
        system_instruction = (
            "You are the quantitative trading verification model. Analyze the order constraints and return valid JSON."
        )

        llm_response = await self.call_llm(
            user_message=f"Validate and execute this trade details:\n{prompt_context}",
            extra_system=system_instruction,
            max_tokens=1024,
        )

        try:
            # Strip markdown code blocks if any
            clean_json = llm_response.replace("```json", "").replace("```", "").strip()
            decision_data = json.loads(clean_json)
        except json.JSONDecodeError:
            decision_data = {
                "decision": "EXECUTE",
                "ticker": ticker,
                "side": side,
                "qty": qty,
                "order_type": "MARKET",
                "limit_price": None,
                "reason": f"Agent validation parsed fallback: {llm_response[:300]}",
            }

        if decision_data.get("decision") != "EXECUTE":
            reason = decision_data.get("reason", "Rejected by trading agent analysis.")
            await self._log("failed", f"LLM rejected execution: {reason}")
            return {"status": "REJECTED", "error": reason}

        # 4. Check Dry-Run Safety Mode
        if self.settings.trading_dry_run:
            dry_run_msg = f"[DRY-RUN] Would have executed: {side} {qty} shares of {ticker} at {current_price:.2f}"
            await self._log("completed", dry_run_msg)
            # Create a dry run order log in the DB
            from src.database.models import TradeOrder
            strategy_uuid = uuid.UUID(strategy_id) if strategy_id else None
            order = TradeOrder(
                strategy_id=strategy_uuid,
                ticker=ticker,
                side=side,
                qty=qty,
                order_type=decision_data.get("order_type", "MARKET"),
                limit_price=decision_data.get("limit_price"),
                status="DRY_RUN",
                filled_qty=qty,
                avg_fill_price=current_price,
                agent_rationale=decision_data.get("reason"),
            )
            self.db.add(order)
            await self.db.commit()
            return {
                "status": "DRY_RUN",
                "ticker": ticker,
                "side": side,
                "qty": qty,
                "avg_fill_price": current_price,
                "message": dry_run_msg,
            }

        # 5. Place real or simulated order
        try:
            order_type = decision_data.get("order_type", "MARKET")
            limit_price = decision_data.get("limit_price")
            
            res = await self.broker.place_order(
                ticker=ticker,
                side=side,
                qty=qty,
                order_type=order_type,
                limit_price=limit_price,
                strategy_id=strategy_id,
                agent_rationale=decision_data.get("reason"),
            )
            
            if res.get("status") == "REJECTED":
                await self._log("failed", f"Broker rejected trade: {res.get('error')}")
                return {"status": "REJECTED", "error": res.get("error")}
                
            await self._log("completed", f"Trade filled: {side} {qty} shares of {ticker} at ${res.get('avg_fill_price')}")
            return res
        except Exception as e:
            err_msg = f"Failed to execute trade on broker: {e}"
            await self._log("failed", err_msg)
            return {"status": "REJECTED", "error": err_msg}

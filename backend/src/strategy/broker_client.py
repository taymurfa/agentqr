import uuid
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from config.settings import get_settings
from src.database.models import TradingAccount, TradeOrder, TradePosition
from src.ingestion.market_data import MarketDataClient


class BaseBrokerClient(ABC):
    """Abstract Base Class for Broker integrations."""

    @abstractmethod
    async def get_account_info(self) -> dict:
        """Fetch account cash, equity, buying power, and P&L."""
        pass

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """Fetch active holdings."""
        pass

    @abstractmethod
    async def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        strategy_id: Optional[str] = None,
        agent_rationale: Optional[str] = None,
    ) -> dict:
        """Place an order."""
        pass

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel a pending order."""
        pass

    @abstractmethod
    async def liquidate_all_positions(self) -> bool:
        """Liquidate all open positions."""
        pass

    @abstractmethod
    async def cancel_all_orders(self) -> bool:
        """Cancel all pending orders."""
        pass


class MockBrokerClient(BaseBrokerClient):
    """Local simulation broker client. Operates on the database to track mock account state."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.market_client = MarketDataClient()

    async def _get_or_create_account(self) -> TradingAccount:
        stmt = select(TradingAccount).where(TradingAccount.is_live == False)
        res = await self.db.execute(stmt)
        acc = res.scalar_one_or_none()

        if not acc:
            acc = TradingAccount(
                id=uuid.uuid4(),
                cash=100000.0,
                buying_power=100000.0,
                equity=100000.0,
                initial_balance=100000.0,
                is_live=False,
                circuit_breaker_tripped=False,
            )
            self.db.add(acc)
            await self.db.commit()
            await self.db.refresh(acc)
        return acc

    async def get_account_info(self) -> dict:
        acc = await self._get_or_create_account()
        # Recalculate equity based on position values
        stmt = select(TradePosition)
        res = await self.db.execute(stmt)
        positions = res.scalars().all()
        
        pos_value = 0.0
        for pos in positions:
            # Sync current price
            df = self.market_client.get_ohlcv(pos.ticker, period="5d")
            if not df.empty:
                current_price = float(df["Close"].iloc[-1])
                pos.current_price = current_price
                pos.market_value = pos.qty * current_price
                pos.unrealized_pnl = pos.market_value - (pos.qty * pos.avg_entry_price)
                pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.qty * pos.avg_entry_price)) * 100
                pos_value += pos.market_value
        
        acc.equity = acc.cash + pos_value
        acc.buying_power = acc.cash  # Simplified: no margin multiplier in mock
        await self.db.commit()

        return {
            "cash": acc.cash,
            "buying_power": acc.buying_power,
            "equity": acc.equity,
            "initial_balance": acc.initial_balance,
            "circuit_breaker_tripped": acc.circuit_breaker_tripped,
            "is_live": False,
        }

    async def get_positions(self) -> list[dict]:
        await self.get_account_info()  # Forces update of prices
        stmt = select(TradePosition)
        res = await self.db.execute(stmt)
        positions = res.scalars().all()
        return [
            {
                "ticker": p.ticker,
                "qty": p.qty,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_pct": p.unrealized_pnl_pct,
            }
            for p in positions
        ]

    async def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        strategy_id: Optional[str] = None,
        agent_rationale: Optional[str] = None,
    ) -> dict:
        ticker = ticker.upper()
        side = side.upper()
        order_type = order_type.upper()

        acc = await self._get_or_create_account()
        if acc.circuit_breaker_tripped:
            return {"status": "REJECTED", "error": "Circuit breaker is active. Trading disabled."}

        # Fetch current price
        df = self.market_client.get_ohlcv(ticker, period="5d")
        if df.empty:
            return {"status": "REJECTED", "error": f"Failed to get price data for {ticker}."}
        
        current_price = float(df["Close"].iloc[-1])
        fill_price = limit_price if (order_type == "LIMIT" and limit_price) else current_price
        
        # Check order limit logic (if buy limit order is too low it wouldn't fill immediately, but for mock we fill immediately)
        total_cost = fill_price * qty
        
        # Create order row
        order_id = uuid.uuid4()
        strategy_uuid = uuid.UUID(strategy_id) if strategy_id else None
        order = TradeOrder(
            id=order_id,
            strategy_id=strategy_uuid,
            ticker=ticker,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            status="PENDING",
            agent_rationale=agent_rationale,
            broker_order_id=f"mock_{order_id.hex[:12]}",
        )
        self.db.add(order)

        if side == "BUY":
            if acc.cash < total_cost:
                order.status = "REJECTED"
                order.rejection_reason = f"Insufficient cash. Required: {total_cost:.2f}, Available: {acc.cash:.2f}"
                await self.db.commit()
                return {"status": "REJECTED", "error": order.rejection_reason}

            # Deduct cash
            acc.cash -= total_cost
            acc.buying_power = acc.cash
            
            # Fill order
            order.status = "FILLED"
            order.filled_qty = qty
            order.avg_fill_price = fill_price

            # Create or update position
            stmt = select(TradePosition).where(TradePosition.ticker == ticker)
            res = await self.db.execute(stmt)
            pos = res.scalar_one_or_none()

            if pos:
                new_qty = pos.qty + qty
                pos.avg_entry_price = ((pos.avg_entry_price * pos.qty) + total_cost) / new_qty
                pos.qty = new_qty
                pos.current_price = current_price
                pos.market_value = pos.qty * current_price
                pos.unrealized_pnl = pos.market_value - (pos.qty * pos.avg_entry_price)
                pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.qty * pos.avg_entry_price)) * 100
            else:
                pos = TradePosition(
                    id=uuid.uuid4(),
                    ticker=ticker,
                    qty=qty,
                    avg_entry_price=fill_price,
                    current_price=current_price,
                    market_value=total_cost,
                    unrealized_pnl=0.0,
                    unrealized_pnl_pct=0.0,
                )
                self.db.add(pos)

        elif side == "SELL":
            stmt = select(TradePosition).where(TradePosition.ticker == ticker)
            res = await self.db.execute(stmt)
            pos = res.scalar_one_or_none()

            if not pos or pos.qty < qty:
                order.status = "REJECTED"
                order.rejection_reason = f"No open position or insufficient shares to sell for {ticker}."
                await self.db.commit()
                return {"status": "REJECTED", "error": order.rejection_reason}

            # Add cash
            acc.cash += total_cost
            acc.buying_power = acc.cash
            
            # Fill order
            order.status = "FILLED"
            order.filled_qty = qty
            order.avg_fill_price = fill_price

            # Update position
            if pos.qty == qty:
                await self.db.delete(pos)
            else:
                pos.qty -= qty
                pos.current_price = current_price
                pos.market_value = pos.qty * current_price
                pos.unrealized_pnl = pos.market_value - (pos.qty * pos.avg_entry_price)
                pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.qty * pos.avg_entry_price)) * 100

        await self.db.commit()
        await self.db.refresh(order)
        return {
            "order_id": str(order.id),
            "broker_order_id": order.broker_order_id,
            "status": order.status,
            "filled_qty": order.filled_qty,
            "avg_fill_price": order.avg_fill_price,
        }

    async def cancel_order(self, broker_order_id: str) -> bool:
        stmt = select(TradeOrder).where(TradeOrder.broker_order_id == broker_order_id)
        res = await self.db.execute(stmt)
        order = res.scalar_one_or_none()
        
        if order and order.status == "PENDING":
            order.status = "CANCELED"
            await self.db.commit()
            return True
        return False

    async def liquidate_all_positions(self) -> bool:
        stmt = select(TradePosition)
        res = await self.db.execute(stmt)
        positions = res.scalars().all()
        
        for pos in positions:
            await self.place_order(
                ticker=pos.ticker,
                side="SELL",
                qty=pos.qty,
                order_type="MARKET",
            )
        return True

    async def cancel_all_orders(self) -> bool:
        stmt = select(TradeOrder).where(TradeOrder.status == "PENDING")
        res = await self.db.execute(stmt)
        orders = res.scalars().all()
        for order in orders:
            order.status = "CANCELED"
        await self.db.commit()
        return True


class AlpacaBrokerClient(BaseBrokerClient):
    """Alpaca REST API paper/live broker client."""

    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "APCA-API-KEY-ID": self.settings.alpaca_api_key_id,
            "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
            "Content-Type": "application/json",
        }
        self.base_url = self.settings.alpaca_base_url.rstrip("/")

    async def _request(self, method: str, path: str, json_data: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient() as client:
            try:
                res = await client.request(method, url, headers=self.headers, json=json_data, timeout=15.0)
                if res.status_code >= 400:
                    try:
                        err_msg = res.json().get("message", res.text)
                    except Exception:
                        err_msg = res.text
                    raise Exception(f"Alpaca API Error {res.status_code}: {err_msg}")
                return res.json() if res.content else {}
            except httpx.RequestError as e:
                raise Exception(f"Alpaca connection failed: {e}")

    async def get_account_info(self) -> dict:
        acc = await self._request("GET", "/v2/account")
        return {
            "cash": float(acc.get("cash", 0.0)),
            "buying_power": float(acc.get("buying_power", 0.0)),
            "equity": float(acc.get("equity", 0.0)),
            "initial_balance": float(acc.get("last_equity", 100000.0)),
            "circuit_breaker_tripped": False,  # Managed in db/worker level
            "is_live": acc.get("currency") == "USD" and not ("paper" in self.base_url),
        }

    async def get_positions(self) -> list[dict]:
        positions = await self._request("GET", "/v2/positions")
        return [
            {
                "ticker": pos.get("symbol"),
                "qty": float(pos.get("qty", 0.0)),
                "avg_entry_price": float(pos.get("avg_entry_price", 0.0)),
                "current_price": float(pos.get("current_price", 0.0)),
                "market_value": float(pos.get("market_value", 0.0)),
                "unrealized_pnl": float(pos.get("unrealized_pl", 0.0)),
                "unrealized_pnl_pct": float(pos.get("unrealized_plpc", 0.0)) * 100,
            }
            for pos in positions
        ]

    async def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        strategy_id: Optional[str] = None,
        agent_rationale: Optional[str] = None,
    ) -> dict:
        payload = {
            "symbol": ticker.upper(),
            "qty": str(qty),
            "side": side.lower(),
            "type": order_type.lower(),
            "time_in_force": "day",
        }
        if order_type.upper() == "LIMIT" and limit_price:
            payload["limit_price"] = f"{limit_price:.2f}"

        res = await self._request("POST", "/v2/orders", payload)
        
        # Alpaca status can be: 'accepted', 'pending_new', 'filled', etc.
        status_map = {
            "accepted": "PENDING",
            "pending_new": "PENDING",
            "filled": "FILLED",
            "partially_filled": "PENDING",
            "canceled": "CANCELED",
            "rejected": "REJECTED",
        }
        raw_status = res.get("status", "accepted")
        mapped_status = status_map.get(raw_status, "PENDING")

        return {
            "order_id": str(uuid.uuid4()),  # Created locally
            "broker_order_id": res.get("id"),
            "status": mapped_status,
            "filled_qty": float(res.get("filled_qty", 0.0)),
            "avg_fill_price": float(res.get("filled_avg_price")) if res.get("filled_avg_price") else None,
        }

    async def cancel_order(self, broker_order_id: str) -> bool:
        try:
            await self._request("DELETE", f"/v2/orders/{broker_order_id}")
            return True
        except Exception:
            return False

    async def liquidate_all_positions(self) -> bool:
        try:
            # DELETE /v2/positions liquidates all open positions in Alpaca
            await self._request("DELETE", "/v2/positions")
            return True
        except Exception:
            return False

    async def cancel_all_orders(self) -> bool:
        try:
            # DELETE /v2/orders cancels all open orders in Alpaca
            await self._request("DELETE", "/v2/orders")
            return True
        except Exception:
            return False

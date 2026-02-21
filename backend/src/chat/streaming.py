"""Streaming response handler for chat WebSocket."""

import re
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.orchestrator import OrchestratorAgent
from src.chat.manager import ChatManager
from src.chat.context_builder import ContextBuilder


class StreamingResponseHandler:
    """Handles chat message processing and response generation."""

    COMMAND_PATTERNS = {
        "research": re.compile(r"^/research\s+(\w+)", re.IGNORECASE),
        "compare": re.compile(r"^/compare\s+([\w\s,]+)", re.IGNORECASE),
        "strategy": re.compile(r"^/strategy\s+(.+)", re.IGNORECASE),
        "technical": re.compile(r"^/technical\s+(\w+)", re.IGNORECASE),
        "fundamental": re.compile(r"^/fundamental\s+(\w+)", re.IGNORECASE),
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = OrchestratorAgent(db)
        self.chat_mgr = ChatManager(db)
        self.context_builder = ContextBuilder(db)

    async def generate_response(self, session_id: str, message: str) -> dict:
        """Generate a non-streaming response."""
        command = self._parse_command(message)

        if command:
            return await self._handle_command(command, session_id)

        # Build conversation context
        history = await self.chat_mgr.get_conversation_context(session_id)

        # Detect ticker mentions for targeted research
        ticker = self._extract_ticker(message)

        result = await self.orchestrator.run(
            query=message,
            ticker=ticker,
            conversation_history=history,
        )

        return {
            "content": result.get("content", ""),
            "agents_used": result.get("agents_used", []),
            "context_sources": [],
        }

    async def stream_response(
        self,
        session_id: str,
        message: str,
    ) -> AsyncIterator[dict]:
        """Stream a response for WebSocket delivery."""
        command = self._parse_command(message)

        if command:
            yield {"type": "agent_status", "agent": command["type"], "status": "working"}
            result = await self._handle_command(command, session_id)
            # Stream the result as tokens
            for i in range(0, len(result["content"]), 20):
                yield {"type": "token", "content": result["content"][i:i + 20]}
            if result.get("context_sources"):
                yield {"type": "context", "sources": result["context_sources"]}
            return

        # Regular chat message
        ticker = self._extract_ticker(message)

        if ticker:
            yield {"type": "agent_status", "agent": "orchestrator", "status": "planning"}

        result = await self.orchestrator.run(query=message, ticker=ticker)

        # Stream the synthesis content
        content = result.get("content", "")
        for i in range(0, len(content), 20):
            yield {"type": "token", "content": content[i:i + 20]}

        if result.get("agents_used"):
            for agent in result["agents_used"]:
                yield {"type": "agent_status", "agent": agent, "status": "completed"}

    def _parse_command(self, message: str) -> Optional[dict]:
        """Parse slash commands from user messages."""
        message = message.strip()
        if not message.startswith("/"):
            return None

        for cmd_type, pattern in self.COMMAND_PATTERNS.items():
            match = pattern.match(message)
            if match:
                return {"type": cmd_type, "args": match.group(1).strip()}

        return None

    async def _handle_command(self, command: dict, session_id: str) -> dict:
        """Execute a parsed slash command."""
        cmd_type = command["type"]
        args = command["args"]

        if cmd_type == "research":
            result = await self.orchestrator.research(ticker=args)
            return {
                "content": result.get("synthesis", ""),
                "agents_used": result.get("agents_used", []),
                "context_sources": [],
            }

        elif cmd_type == "compare":
            tickers = [t.strip().upper() for t in args.split(",")]
            result = await self.orchestrator.compare(tickers=tickers)
            return {
                "content": result.get("synthesis", ""),
                "agents_used": ["fundamental_analyst", "technical_analyst"],
                "context_sources": [],
            }

        elif cmd_type == "technical":
            from src.agents.technical_analyst import TechnicalAnalysisAgent
            agent = TechnicalAnalysisAgent(self.db)
            result = await agent.run(f"Technical analysis for {args}", ticker=args)
            return {
                "content": result.get("content", ""),
                "agents_used": ["technical_analyst"],
                "context_sources": [],
            }

        elif cmd_type == "fundamental":
            from src.agents.fundamental_analyst import FundamentalAnalysisAgent
            agent = FundamentalAnalysisAgent(self.db)
            result = await agent.run(f"Fundamental analysis for {args}", ticker=args)
            return {
                "content": result.get("content", ""),
                "agents_used": ["fundamental_analyst"],
                "context_sources": [],
            }

        elif cmd_type == "strategy":
            result = await self.orchestrator.run(
                query=f"Generate trading strategy for {args}",
                sector=args,
            )
            return {
                "content": result.get("content", ""),
                "agents_used": result.get("agents_used", []),
                "context_sources": [],
            }

        return {"content": "Unknown command", "agents_used": [], "context_sources": []}

    def _extract_ticker(self, message: str) -> Optional[str]:
        """Try to extract a stock ticker from the message."""
        ticker_pattern = re.compile(r'\b([A-Z]{1,5})\b')
        words = message.upper().split()
        common_words = {
            "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
            "HER", "WAS", "ONE", "OUR", "OUT", "HIS", "HAS", "HOW", "MAN",
            "NEW", "NOW", "OLD", "SEE", "WAY", "WHO", "BOY", "DID", "ITS",
            "LET", "SAY", "SHE", "TOO", "USE", "WHAT", "SHOW", "TELL",
            "RESEARCH", "ANALYZE", "COMPARE", "BUY", "SELL", "HOLD",
        }
        for word in words:
            if (
                ticker_pattern.match(word)
                and word not in common_words
                and 1 < len(word) <= 5
            ):
                return word
        return None

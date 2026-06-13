"""Orchestrator Agent: routes tasks to specialist agents and aggregates results."""

import re
import json
import asyncio
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.agents.base_agent import BaseAgent
from src.agents.sector_researcher import SectorResearchAgent
from src.agents.technical_analyst import TechnicalAnalysisAgent
from src.agents.fundamental_analyst import FundamentalAnalysisAgent
from src.agents.trading_agent import TradingAgent
from src.database.models import Company, Strategy


class OrchestratorAgent(BaseAgent):
    """Master orchestrator that routes tasks and aggregates multi-agent results."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, "orchestrator")
        self.sector_agent = SectorResearchAgent(db)
        self.tech_agent = TechnicalAnalysisAgent(db)
        self.fundamental_agent = FundamentalAnalysisAgent(db)
        self.trading_agent = TradingAgent(db)

    async def run(self, query: str, **kwargs) -> dict:
        """Route a query to the appropriate agents and synthesize results."""
        await self._log("started", f"Orchestrating: {query[:100]}")

        plan = self._plan_research(query, **kwargs)
        results = await self._execute_plan(plan, query, **kwargs)
        synthesis = await self._synthesize(query, results)

        return {
            "agent": "orchestrator",
            "content": synthesis,
            "agents_used": [r["agent"] for r in results],
            "agent_results": results,
        }

    async def research(self, ticker: str, sector: str = None, depth: str = "standard") -> dict:
        """Full research pipeline for a single ticker."""
        query = f"Comprehensive research analysis for {ticker}"

        if not sector:
            stmt = select(Company).where(Company.ticker == ticker.upper())
            result = await self.db.execute(stmt)
            company = result.scalar_one_or_none()
            sector = company.sector if company else None

        agents_to_run = ["sector_researcher", "fundamental_analyst"]
        if depth in ("standard", "deep"):
            agents_to_run.append("technical_analyst")

        results = []

        # Run agents sequentially to avoid DB locking
        for agent_name in agents_to_run:
            try:
                r = await self._run_agent(agent_name, query, ticker=ticker, sector=sector)
                if isinstance(r, dict):
                    results.append(r)
                else:
                    results.append({"agent": agent_name, "error": str(r), "content": f"Agent returned unexpected type: {type(r)}"})
            except Exception as e:
                print(f"[orchestrator] {agent_name} raised: {e}")
                results.append({"agent": agent_name, "error": str(e), "content": f"Agent failed: {e}"})

        synthesis = await self._synthesize(query, results)

        # Store research summary
        await self._update_research_summary(ticker, synthesis)

        return {
            "ticker": ticker,
            "sector": sector,
            "synthesis": synthesis,
            "agents_used": [r["agent"] for r in results],
            "agent_results": results,
        }

    async def compare(self, tickers: list[str], metrics: list[str] = None) -> dict:
        """Compare multiple companies."""
        query = f"Compare {', '.join(tickers)} across key metrics"
        results = []

        for ticker in tickers:
            tasks = []
            if "fundamentals" in (metrics or ["fundamentals"]):
                tasks.append(self._run_agent("fundamental_analyst", query, ticker=ticker, peers=tickers))
            if "technicals" in (metrics or ["technicals"]):
                tasks.append(self._run_agent("technical_analyst", query, ticker=ticker))

            for t in tasks:
                try:
                    r = await t
                except Exception as e:
                    r = {"agent": "error", "content": str(e)}
                    
                if isinstance(r, dict):
                    results.append(r)

        synthesis = await self._synthesize(query, results)

        return {
            "tickers": tickers,
            "synthesis": synthesis,
            "agent_results": results,
        }

    def _plan_research(self, query: str, **kwargs) -> list[str]:
        """Determine which agents to invoke based on the query."""
        query_lower = query.lower()
        agents = []

        if kwargs.get("ticker"):
            # Specific-type-only requests
            if any(w in query_lower for w in ["technical", "chart", "indicator", "signal", "momentum"]):
                agents.append("technical_analyst")
            if any(w in query_lower for w in ["fundamental", "valuation", "ratio", "dcf"]):
                agents.append("fundamental_analyst")
            # "Full", "research", "analyze", "overview", "sector", "compare" → all agents
            if any(w in query_lower for w in ["full", "research", "analyze", "analysis", "overview", "sector", "risk", "report"]):
                agents = ["sector_researcher", "fundamental_analyst", "technical_analyst"]

            # Default: run all if no specific type detected or mixed signals
            if not agents:
                agents = ["sector_researcher", "fundamental_analyst", "technical_analyst"]
        else:
            # General queries go to sector researcher
            agents = ["sector_researcher"]

        return agents

    async def _execute_plan(self, agent_names: list[str], query: str, **kwargs) -> list[dict]:
        """Execute the research plan by running agents sequentially."""
        outputs = []
        for name in agent_names:
            try:
                r = await self._run_agent(name, query, **kwargs)
                if isinstance(r, dict):
                    outputs.append(r)
                else:
                    outputs.append({"agent": name, "error": str(r), "content": f"Unexpected return type from {name}"})
            except Exception as e:
                print(f"[orchestrator] {name} raised: {e}")
                outputs.append({"agent": name, "error": str(e), "content": f"Agent failed: {e}"})

        return outputs

    async def _run_agent(self, agent_name: str, query: str, **kwargs) -> dict:
        """Run a single agent."""
        agent_map = {
            "sector_researcher": self.sector_agent,
            "technical_analyst": self.tech_agent,
            "fundamental_analyst": self.fundamental_agent,
            "trading_agent": self.trading_agent,
        }
        agent = agent_map.get(agent_name)
        if not agent:
            return {"agent": agent_name, "error": f"Unknown agent: {agent_name}"}

        return await agent.run(query, **kwargs)

    async def _synthesize(self, query: str, results: list[dict]) -> str:
        """Synthesize results from multiple agents into a unified response."""
        context_parts = []
        for r in results:
            agent = r.get("agent", "unknown")
            content = r.get("content", r.get("error", "No output"))
            context_parts.append(f"## {agent.replace('_', ' ').title()} Output\n\n{content}")

        full_context = "\n\n---\n\n".join(context_parts)

        synthesis_prompt = f"""Original Query: {query}

You have received outputs from {len(results)} specialist agents. Synthesize their findings into a 
unified, actionable research response. Follow your output format:
1. Executive Summary
2. Key Findings
3. Agent-specific insights
4. Recommendation with confidence level
5. Risk factors

Be concise but comprehensive. Resolve any contradictions between agents."""

        return await self.call_llm(synthesis_prompt, context=full_context, max_tokens=4096)

    async def _update_research_summary(self, ticker: str, synthesis: str):
        """Store condensed research summary in the company record."""
        try:
            stmt = select(Company).where(Company.ticker == ticker.upper())
            result = await self.db.execute(stmt)
            company = result.scalar_one_or_none()

            if company:
                summary = await self.generate_summary(synthesis, max_length=300)
                company.research_summary = summary
                company.updated_at = datetime.utcnow()
                await self.db.commit()
        except Exception as e:
            try:
                await self.db.rollback()
            except Exception:
                pass
            print(f"[orchestrator] Failed to update research summary: {e}")


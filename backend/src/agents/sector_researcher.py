"""Sector Research Agent: deep research on companies using SEC filings, earnings, and news.
Falls back to local data when vector search is unavailable (rate limited)."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.agents.base_agent import BaseAgent
from src.agents.tools.search_tools import SearchTools
from src.agents.tools.data_tools import DataTools
from src.database.models import Company


class SectorResearchAgent(BaseAgent):
    def __init__(self, db: AsyncSession):
        super().__init__(db, "sector_researcher")
        self.search = SearchTools()
        self.data = DataTools()

    async def run(self, query: str, **kwargs) -> dict:
        ticker = kwargs.get("ticker")
        sector = kwargs.get("sector")

        await self._log("started", f"Sector research for: {query}")

        context_parts = []
        sources_used = []

        if ticker:
            # Search SEC filings (gracefully returns [] if rate limited)
            filing_results = self.search.search_filings(query, ticker, top_k=8)
            if filing_results:
                context_parts.append("## SEC Filing Data\n" + self._format_results(filing_results))
                sources_used.append("sec_filings")

            # Search earnings calls
            earnings_results = self.search.search_earnings_calls(query, ticker, top_k=5)
            if earnings_results:
                context_parts.append("## Earnings Call Data\n" + self._format_results(earnings_results))
                sources_used.append("earnings_calls")

            # Search news
            news_results = self.search.search_news(query, ticker, top_k=5)
            if news_results:
                context_parts.append("## News Data\n" + self._format_results(news_results))
                sources_used.append("news")

            # Always get company fundamentals (local data, no API needed after initial fetch)
            try:
                company_info = self.data.get_company_fundamentals(ticker)
                context_parts.append(f"## Company Profile\n{json.dumps(company_info, indent=2, default=str)}")
                sources_used.append("market_data")
            except Exception as e:
                print(f"[sector_researcher] Failed to get fundamentals: {e}")

            # Also get local DB company info including any stored research
            try:
                stmt = select(Company).where(Company.ticker == ticker.upper())
                result = await self.db.execute(stmt)
                company = result.scalar_one_or_none()
                if company:
                    db_info = {
                        "name": company.name,
                        "sector": company.sector,
                        "industry": company.industry,
                        "description": company.description,
                        "market_cap": company.market_cap,
                        "fundamentals": company.fundamentals,
                    }
                    context_parts.append(f"## Database Company Record\n{json.dumps(db_info, indent=2, default=str)}")
                    sources_used.append("local_database")
            except Exception as e:
                print(f"[sector_researcher] Failed to get DB info: {e}")

            # If no vector data was retrieved, add a note so the LLM knows
            if not filing_results and not earnings_results and not news_results:
                context_parts.append(
                    "## Note\nVector search was unavailable (API rate limited). "
                    "Analysis is based on available market data, fundamentals, and cached company info. "
                    "SEC filing details are not included in this run."
                )
        else:
            # Sector-wide search
            ns = sector.lower().replace(" ", "-") if sector else None
            rag_results = await self.rag_query(query, namespace=ns, top_k=15)
            context = self.build_context(rag_results)
            if rag_results:
                context_parts.append(context)
                sources_used.append("knowledge_base")
            else:
                context_parts.append(
                    f"## Sector Overview\nPerform a sector-level analysis for {sector or 'the market'}"
                )

        full_context = "\n\n".join(context_parts)

        research_prompt = f"""Research Query: {query}
{"Ticker: " + ticker if ticker else ""}
{"Sector: " + sector if sector else ""}

Based on the retrieved research context, provide a comprehensive sector research analysis. 
Focus on:
1. Industry positioning and competitive landscape
2. Key sector trends and macro factors
3. Company-specific risks and catalysts
4. Revenue drivers and market dynamics
Follow your output structure guidelines."""

        response = await self.call_llm(research_prompt, context=full_context)

        return {
            "agent": "sector_researcher",
            "content": response,
            "sources_used": sources_used,
            "ticker": ticker,
            "sector": sector,
        }

    def _format_results(self, results: list[dict]) -> str:
        parts = []
        for r in results:
            text = r.get("text", "")
            source = r.get("source", r.get("title", ""))
            date = r.get("date", "")
            section = r.get("section", "")
            score = r.get("score", 0)

            header = f"[{source}"
            if date:
                header += f" | {date}"
            if section:
                header += f" | {section}"
            header += f" | relevance: {score:.2f}]"

            parts.append(f"{header}\n{text}")
        return "\n\n".join(parts)

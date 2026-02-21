"""Fundamental Analysis Agent: financial ratios, DCF, peer comparison.
Works with local data when vector search is unavailable."""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.agents.base_agent import BaseAgent
from src.agents.tools.analysis_tools import AnalysisTools
from src.agents.tools.data_tools import DataTools
from src.agents.tools.search_tools import SearchTools
from src.database.models import Company


class FundamentalAnalysisAgent(BaseAgent):
    def __init__(self, db: AsyncSession):
        super().__init__(db, "fundamental_analyst")
        self.analysis = AnalysisTools()
        self.data = DataTools()
        self.search = SearchTools()

    async def run(self, query: str, **kwargs) -> dict:
        ticker = kwargs.get("ticker")
        peers = kwargs.get("peers", [])

        if not ticker:
            return {"agent": "fundamental_analyst", "error": "Ticker is required for fundamental analysis"}

        await self._log("started", f"Fundamental analysis for {ticker}")

        # Compute financial ratios (uses ta library, local computation)
        ratio_analysis = {}
        try:
            ratio_analysis = self.analysis.compute_financial_ratios(ticker)
        except Exception as e:
            ratio_analysis = {"error": str(e)}
            print(f"[fundamental_analyst] Ratio computation failed for {ticker}: {e}")

        # Get financial statements
        financials = {}
        try:
            financials = self.data.get_financial_statements(ticker)
        except Exception as e:
            financials = {"error": str(e)}
            print(f"[fundamental_analyst] Financial statements failed for {ticker}: {e}")

        # Get company info
        fundamentals = {}
        try:
            fundamentals = self.data.get_company_fundamentals(ticker)
        except Exception as e:
            fundamentals = {"error": str(e)}
            print(f"[fundamental_analyst] Fundamentals failed for {ticker}: {e}")

        # Also pull from local database (cached ratios from ingestion)
        try:
            stmt = select(Company).where(Company.ticker == ticker.upper())
            result = await self.db.execute(stmt)
            company = result.scalar_one_or_none()
            if company and company.fundamentals:
                fundamentals["cached_ratios"] = company.fundamentals
        except Exception as e:
            print(f"[fundamental_analyst] DB lookup failed: {e}")

        # Peer comparison if peers provided
        peer_data = None
        if peers:
            try:
                peer_data = self.data.get_peer_comparison([ticker] + peers)
            except Exception as e:
                print(f"[fundamental_analyst] Peer comparison failed: {e}")

        # Search knowledge base for financial data from filings (graceful if rate limited)
        filing_context = self.search.search_filings(
            f"financial results revenue earnings {ticker}", ticker, top_k=5
        )

        context = f"""## Fundamental Analysis for {ticker.upper()}

### Financial Health Score: {ratio_analysis.get('health_score', 'N/A')}/10

### Company Profile
{json.dumps(fundamentals, indent=2, default=str)[:3000]}

### Financial Ratios
{json.dumps(ratio_analysis, indent=2, default=str)}

### Financial Statements Summary
{json.dumps(financials, indent=2, default=str)[:5000]}
"""

        if peer_data:
            context += f"\n### Peer Comparison\n{json.dumps(peer_data, indent=2, default=str)}"

        if filing_context:
            context += "\n\n### From SEC Filings\n"
            for r in filing_context[:3]:
                context += f"\n[{r.get('source', '')} | {r.get('date', '')}]\n{r.get('text', '')}\n"
        else:
            context += "\n\n### Note\nSEC filing search was unavailable (API rate limited). Analysis is based on available financial statements and ratios."

        analysis_prompt = f"""Perform a comprehensive fundamental analysis of {ticker.upper()}.
User Query: {query}
{"Peers for comparison: " + ", ".join(peers) if peers else ""}

Follow your output structure: Financial Health Score, Key Metrics, Valuation Assessment,
Peer Comparison (if available), Growth Outlook, and Red Flags.
If some data is unavailable, indicate that and work with what is available."""

        response = await self.call_llm(analysis_prompt, context=context)

        return {
            "agent": "fundamental_analyst",
            "content": response,
            "health_score": ratio_analysis.get("health_score"),
            "ratios": ratio_analysis,
            "peer_comparison": peer_data,
            "ticker": ticker,
        }

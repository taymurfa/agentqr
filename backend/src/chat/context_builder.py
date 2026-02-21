"""Builds research context for chat responses."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Company, Filing
from src.knowledge_base.vector_store import VectorStore
from src.knowledge_base.embeddings import EmbeddingGenerator


class ContextBuilder:
    """Assembles research context from multiple sources for the chat LLM."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStore()
        self.embedder = EmbeddingGenerator()

    async def build_context(
        self,
        query: str,
        ticker: Optional[str] = None,
        include_filings: bool = True,
        include_fundamentals: bool = True,
        include_research_summary: bool = True,
        max_chunks: int = 10,
    ) -> dict:
        """Build a comprehensive context dict for the chat response."""
        context = {"sources": [], "text": ""}
        parts = []

        # Add research summary from DB if available
        if ticker and include_research_summary:
            stmt = select(Company).where(Company.ticker == ticker.upper())
            result = await self.db.execute(stmt)
            company = result.scalar_one_or_none()

            if company and company.research_summary:
                parts.append(f"## Existing Research Summary for {ticker}\n{company.research_summary}")
                context["sources"].append({"type": "research_summary", "ticker": ticker})

            if company and company.fundamentals and include_fundamentals:
                import json
                parts.append(f"## Key Fundamentals\n{json.dumps(company.fundamentals, indent=2, default=str)[:2000]}")
                context["sources"].append({"type": "fundamentals", "ticker": ticker})

        # Vector search for relevant documents
        query_embedding = self.embedder.embed_query(query)
        results = self.vector_store.query(
            vector=query_embedding,
            top_k=max_chunks,
            namespace=ticker.lower() if ticker else None,
        )

        for r in results:
            meta = r.get("metadata", {})
            text = meta.get("text", "")
            if text:
                source_info = {
                    "type": meta.get("source", "unknown"),
                    "ticker": meta.get("ticker", ""),
                    "date": meta.get("filing_date", meta.get("published_date", "")),
                    "section": meta.get("section", ""),
                    "score": r.get("score", 0),
                }
                parts.append(f"[{source_info['type']} | {source_info.get('date', '')}]\n{text}")
                context["sources"].append(source_info)

        context["text"] = "\n\n---\n\n".join(parts)
        return context

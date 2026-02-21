"""Vector search and web search tools for agents.
Gracefully degrades when Voyage AI is rate-limited — returns empty results
instead of crashing so agents can still work with local data."""

from typing import Optional
from src.knowledge_base.vector_store import VectorStore
from src.knowledge_base.embeddings import EmbeddingGenerator


class SearchTools:
    """Search tools available to all agents."""

    def __init__(self):
        self.vector_store = VectorStore()
        self.embedder = EmbeddingGenerator()

    def search_knowledge_base(
        self,
        query: str,
        namespace: Optional[str] = None,
        top_k: int = 10,
        source_filter: Optional[str] = None,
    ) -> list[dict]:
        """Search the vector knowledge base for relevant documents.
        Returns empty list if embeddings are unavailable (rate limited)."""
        embedding = self.embedder.embed_query(query)
        if embedding is None:
            return []  # Graceful degradation

        filter_dict = None
        if source_filter:
            filter_dict = {"source": source_filter}

        try:
            results = self.vector_store.query(
                vector=embedding,
                top_k=top_k,
                namespace=namespace,
                filter=filter_dict,
                include_metadata=True,
            )
        except Exception as e:
            print(f"[search] Vector query failed: {e}")
            return []

        return [
            {
                "text": r["metadata"].get("text", ""),
                "source": r["metadata"].get("source", ""),
                "ticker": r["metadata"].get("ticker", ""),
                "filing_type": r["metadata"].get("filing_type", ""),
                "date": r["metadata"].get("filing_date", r["metadata"].get("published_date", "")),
                "section": r["metadata"].get("section", ""),
                "score": r["score"],
            }
            for r in results
        ]

    def search_filings(
        self,
        query: str,
        ticker: str,
        filing_type: Optional[str] = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Search specifically within SEC filings for a ticker."""
        return self.search_knowledge_base(
            query=query,
            namespace=ticker.lower(),
            top_k=top_k,
            source_filter=None,
        )

    def search_news(
        self,
        query: str,
        ticker: Optional[str] = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Search news articles in the knowledge base."""
        embedding = self.embedder.embed_query(query)
        if embedding is None:
            return []

        filter_dict = {"document_type": "news"}

        try:
            results = self.vector_store.query(
                vector=embedding,
                top_k=top_k,
                namespace=ticker.lower() if ticker else None,
                filter=filter_dict,
                include_metadata=True,
            )
        except Exception as e:
            print(f"[search] News query failed: {e}")
            return []

        return [
            {
                "title": r["metadata"].get("title", ""),
                "text": r["metadata"].get("text", ""),
                "source": r["metadata"].get("source", ""),
                "date": r["metadata"].get("published_date", ""),
                "score": r["score"],
            }
            for r in results
        ]

    def search_earnings_calls(
        self,
        query: str,
        ticker: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Search earnings call transcripts."""
        embedding = self.embedder.embed_query(query)
        if embedding is None:
            return []

        filter_dict = {"document_type": "earnings_transcript"}

        try:
            results = self.vector_store.query(
                vector=embedding,
                top_k=top_k,
                namespace=ticker.lower(),
                filter=filter_dict,
                include_metadata=True,
            )
        except Exception as e:
            print(f"[search] Earnings query failed: {e}")
            return []

        return [
            {
                "text": r["metadata"].get("text", ""),
                "date": r["metadata"].get("call_date", ""),
                "score": r["score"],
            }
            for r in results
        ]

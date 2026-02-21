"""Document processing: PDF/HTML/text parsing and metadata extraction."""

import re
from typing import Optional
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pathlib import Path

from src.knowledge_base.chunking import Chunk, RecursiveChunker, SECFilingChunker
from src.knowledge_base.embeddings import EmbeddingGenerator
from src.knowledge_base.vector_store import VectorStore


class DocumentProcessor:
    """Processes raw documents into embedded, indexed chunks."""

    def __init__(self):
        self.chunker = RecursiveChunker()
        self.sec_chunker = SECFilingChunker()
        self.embedder = EmbeddingGenerator()
        self.vector_store = VectorStore()
        # Ensure Pinecone index exists and has the correct dimension before any ingestion
        try:
            self.vector_store.ensure_index()
        except Exception as e:
            print(f"[document_processor] Warning: could not ensure Pinecone index: {e}")


    def process_html(self, html: str, metadata: Optional[dict] = None) -> str:
        """Extract clean text from HTML content."""
        soup = BeautifulSoup(html, "lxml")

        for tag in soup.find_all(["script", "style", "header", "footer", "nav"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def process_pdf(self, pdf_path: str) -> str:
        """Extract text from a PDF file."""
        reader = PdfReader(pdf_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    def process_sec_filing(
        self,
        content: str,
        ticker: str,
        filing_type: str,
        filing_date: str,
        namespace: Optional[str] = None,
    ) -> list[str]:
        """Process an SEC filing: parse, chunk, embed, and store in Pinecone."""
        if "<html" in content.lower() or "<body" in content.lower():
            content = self.process_html(content)

        chunks = self.sec_chunker.chunk_filing(
            text=content,
            ticker=ticker,
            filing_type=filing_type,
            filing_date=filing_date,
        )

        return self._embed_and_store(chunks, namespace=namespace or ticker.lower())

    def process_text(
        self,
        text: str,
        metadata: Optional[dict] = None,
        namespace: Optional[str] = None,
    ) -> list[str]:
        """Process generic text: chunk, embed, and store."""
        chunks = self.chunker.chunk_text(text, metadata=metadata)
        ns = namespace or metadata.get("ticker", "general") if metadata else "general"
        return self._embed_and_store(chunks, namespace=ns)

    def process_earnings_call(
        self,
        transcript: str,
        ticker: str,
        call_date: str,
        namespace: Optional[str] = None,
    ) -> list[str]:
        """Process an earnings call transcript."""
        metadata = {
            "ticker": ticker,
            "source": "earnings_call",
            "call_date": call_date,
            "document_type": "earnings_transcript",
        }
        chunks = self.chunker.chunk_text(transcript, metadata=metadata)
        return self._embed_and_store(chunks, namespace=namespace or ticker.lower())

    def process_news(
        self,
        article_text: str,
        ticker: str,
        source: str,
        published_date: str,
        title: str = "",
        namespace: Optional[str] = None,
    ) -> list[str]:
        """Process a news article."""
        metadata = {
            "ticker": ticker,
            "source": source,
            "published_date": published_date,
            "title": title,
            "document_type": "news",
        }
        chunks = self.chunker.chunk_text(article_text, metadata=metadata)
        return self._embed_and_store(chunks, namespace=namespace or ticker.lower())

    def _embed_and_store(self, chunks: list[Chunk], namespace: str) -> list[str]:
        """Embed chunks and upsert into Pinecone. Returns vector IDs."""
        if not chunks:
            return []

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_batch(texts)

        vectors = []
        vector_ids = []
        for chunk, embedding in zip(chunks, embeddings):
            vid = f"{namespace}_{chunk.chunk_id}"
            vectors.append({
                "id": vid,
                "values": embedding,
                "metadata": {
                    **chunk.metadata,
                    "text": chunk.text[:1000],  # Store truncated text in metadata for retrieval
                },
            })
            vector_ids.append(vid)

        self.vector_store.upsert(vectors, namespace=namespace)
        return vector_ids

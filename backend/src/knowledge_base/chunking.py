"""Document chunking strategies for financial documents."""

import re
import hashlib
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)
    chunk_id: Optional[str] = None

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = hashlib.md5(self.text[:500].encode()).hexdigest()


class RecursiveChunker:
    """Recursively splits text using a hierarchy of separators."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n\n", "\n\n", "\n", ". ", " "]

    def chunk_text(
        self,
        text: str,
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """Split text into overlapping chunks with metadata."""
        metadata = metadata or {}
        raw_chunks = self._split_recursive(text, self.separators)

        chunks = []
        for i, chunk_text in enumerate(raw_chunks):
            chunk_meta = {
                **metadata,
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            }
            chunks.append(Chunk(text=chunk_text.strip(), metadata=chunk_meta))

        return chunks

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        sep = separators[0] if separators else " "
        remaining_seps = separators[1:] if len(separators) > 1 else []

        parts = text.split(sep)
        chunks = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)

                if len(part) > self.chunk_size and remaining_seps:
                    sub_chunks = self._split_recursive(part, remaining_seps)
                    chunks.extend(sub_chunks)
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        # Apply overlap
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            overlap_text = prev[-self.chunk_overlap:] if len(prev) > self.chunk_overlap else prev
            overlapped.append(overlap_text + " " + chunks[i])
        return overlapped


class SECFilingChunker(RecursiveChunker):
    """Specialized chunker for SEC filings that respects section boundaries."""

    SEC_SECTION_PATTERNS = [
        r"(?:ITEM|Item)\s+(\d+[A-Za-z]?)\s*[.:\-—]\s*(.+)",
        r"(?:PART|Part)\s+(I{1,3}|IV)\s*[.:\-—]\s*(.+)",
    ]

    def chunk_filing(
        self,
        text: str,
        ticker: str,
        filing_type: str,
        filing_date: str,
    ) -> list[Chunk]:
        """Chunk an SEC filing, preserving section structure in metadata."""
        sections = self._extract_sections(text)
        all_chunks = []

        for section_name, section_text in sections:
            base_meta = {
                "ticker": ticker,
                "filing_type": filing_type,
                "filing_date": filing_date,
                "section": section_name,
                "source": "sec_edgar",
            }
            chunks = self.chunk_text(section_text, metadata=base_meta)
            all_chunks.extend(chunks)

        return all_chunks

    def _extract_sections(self, text: str) -> list[tuple[str, str]]:
        """Extract named sections from filing text."""
        combined_pattern = "|".join(self.SEC_SECTION_PATTERNS)
        matches = list(re.finditer(combined_pattern, text, re.IGNORECASE))

        if not matches:
            return [("full_document", text)]

        sections = []
        for i, match in enumerate(matches):
            section_name = match.group(0).strip()[:100]
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()
            if section_text:
                sections.append((section_name, section_text))

        return sections

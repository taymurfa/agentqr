"""Earnings call transcript ingestion."""

import re
import httpx
from typing import Optional
from dataclasses import dataclass

from config.settings import get_settings


@dataclass
class EarningsCallTranscript:
    ticker: str
    quarter: str
    year: int
    date: str
    content: str
    participants: list[str]
    qa_section: str


class EarningsCallClient:
    """Fetches and processes earnings call transcripts from SEC filings (8-K/DEF 14A)
    and free sources."""

    def __init__(self):
        settings = get_settings()
        self.headers = {
            "User-Agent": settings.sec_edgar_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    def get_transcripts_from_sec(
        self,
        ticker: str,
        cik: str,
        count: int = 4,
    ) -> list[EarningsCallTranscript]:
        """
        Attempt to get earnings-related filings from SEC (8-K filings
        often contain earnings information).
        """
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            resp = httpx.get(url, headers=self.headers, timeout=30)
            data = resp.json()
        except Exception:
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        transcripts = []
        for i, form in enumerate(forms):
            if form == "8-K" and len(transcripts) < count:
                acc = accessions[i].replace("-", "")
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc}/{primary_docs[i]}"

                try:
                    content = httpx.get(doc_url, headers=self.headers, timeout=30, follow_redirects=True).text
                    if self._is_earnings_related(content):
                        parsed = self._parse_transcript(content, ticker, dates[i])
                        if parsed:
                            transcripts.append(parsed)
                except Exception:
                    continue

        return transcripts

    def _is_earnings_related(self, content: str) -> bool:
        """Check if an 8-K filing is earnings-related."""
        earnings_keywords = [
            "earnings", "quarterly results", "financial results",
            "revenue", "earnings per share", "EPS",
            "conference call", "Q1", "Q2", "Q3", "Q4",
        ]
        content_lower = content.lower()
        return sum(1 for kw in earnings_keywords if kw.lower() in content_lower) >= 2

    def _parse_transcript(
        self,
        content: str,
        ticker: str,
        date: str,
    ) -> Optional[EarningsCallTranscript]:
        """Parse earnings call content from a filing."""
        from bs4 import BeautifulSoup

        if "<html" in content.lower():
            soup = BeautifulSoup(content, "lxml")
            for tag in soup.find_all(["script", "style"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
        else:
            text = content

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        participants = self._extract_participants(text)
        qa_section = self._extract_qa(text)

        quarter, year = self._infer_quarter(date)

        return EarningsCallTranscript(
            ticker=ticker.upper(),
            quarter=quarter,
            year=year,
            date=date,
            content=text[:50000],
            participants=participants,
            qa_section=qa_section,
        )

    def _extract_participants(self, text: str) -> list[str]:
        """Extract participant names from transcript."""
        patterns = [
            r"(?:Participants?|Speakers?|Presenters?)[\s:]+(.+?)(?:\n\n|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                block = match.group(1)
                names = [line.strip() for line in block.split("\n") if line.strip()]
                return names[:20]
        return []

    def _extract_qa(self, text: str) -> str:
        """Extract Q&A section from transcript."""
        qa_patterns = [
            r"(?:Question.and.Answer|Q\s*&\s*A|Q&A\s+Session)(.+?)(?:\n\n\n|\Z)",
        ]
        for pattern in qa_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()[:20000]
        return ""

    def _infer_quarter(self, date_str: str) -> tuple[str, int]:
        """Infer fiscal quarter from filing date."""
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            month = dt.month
            if month <= 3:
                return "Q4", dt.year - 1
            elif month <= 6:
                return "Q1", dt.year
            elif month <= 9:
                return "Q2", dt.year
            else:
                return "Q3", dt.year
        except Exception:
            return "Unknown", 0

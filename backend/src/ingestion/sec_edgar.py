"""SEC EDGAR filing downloader and parser."""

import re
import time
import httpx
from typing import Optional
from bs4 import BeautifulSoup
from dataclasses import dataclass

from config.settings import get_settings


@dataclass
class SECFiling:
    ticker: str
    cik: str
    accession_number: str
    filing_type: str
    filing_date: str
    url: str
    content: str
    sections: dict


class SECEdgarClient:
    """Downloads and parses SEC EDGAR filings."""

    BASE_URL = "https://efts.sec.gov/LATEST"
    FILING_URL = "https://www.sec.gov/Archives/edgar/data"
    HEADERS_BASE = {"Accept-Encoding": "gzip, deflate"}

    IMPORTANT_SECTIONS_10K = {
        "1": "Business",
        "1A": "Risk Factors",
        "2": "Properties",
        "6": "Selected Financial Data",
        "7": "MD&A",
        "7A": "Quantitative and Qualitative Disclosures",
        "8": "Financial Statements",
    }

    IMPORTANT_SECTIONS_10Q = {
        "1": "Financial Statements",
        "2": "MD&A",
        "3": "Quantitative and Qualitative Disclosures",
        "1A": "Risk Factors",
    }

    def __init__(self):
        settings = get_settings()
        self.user_agent = settings.sec_edgar_user_agent
        self.headers = {
            **self.HEADERS_BASE,
            "User-Agent": self.user_agent,
        }

    def get_cik(self, ticker: str) -> Optional[str]:
        """Look up CIK number for a ticker."""
        url = f"{self.BASE_URL}/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms=10-K"
        resp = httpx.get(url, headers=self.headers, timeout=30)

        # Alternative: use company tickers JSON
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        resp = httpx.get(tickers_url, headers=self.headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker.upper():
                    return str(entry["cik_str"]).zfill(10)
        return None

    def get_filings_list(
        self,
        ticker: str,
        filing_type: str = "10-K",
        count: int = 5,
    ) -> list[dict]:
        """Get list of recent filings for a ticker."""
        cik = self.get_cik(ticker)
        if not cik:
            return []

        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = httpx.get(url, headers=self.headers, timeout=30)
        if resp.status_code != 200:
            return []

        data = resp.json()
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        filings = []
        for i, form in enumerate(forms):
            if form == filing_type and len(filings) < count:
                acc = accessions[i].replace("-", "")
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc}/{primary_docs[i]}"
                filings.append({
                    "cik": cik,
                    "accession_number": accessions[i],
                    "filing_type": form,
                    "filing_date": dates[i],
                    "url": doc_url,
                })

        return filings

    def download_filing(self, url: str) -> str:
        """Download filing content from SEC EDGAR."""
        time.sleep(0.1)  # Rate limiting: 10 req/sec
        resp = httpx.get(url, headers=self.headers, timeout=60, follow_redirects=True)
        if resp.status_code != 200:
            raise Exception(f"Failed to download filing: {resp.status_code}")
        return resp.text

    def parse_filing(
        self,
        html_content: str,
        filing_type: str = "10-K",
    ) -> dict:
        """Parse an SEC filing HTML into sections."""
        soup = BeautifulSoup(html_content, "lxml")

        for tag in soup.find_all(["script", "style"]):
            tag.decompose()

        full_text = soup.get_text(separator="\n")
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = re.sub(r" {2,}", " ", full_text)

        sections_map = (
            self.IMPORTANT_SECTIONS_10K if filing_type == "10-K"
            else self.IMPORTANT_SECTIONS_10Q
        )

        sections = {}
        for item_num, section_name in sections_map.items():
            pattern = rf"(?:ITEM|Item)\s+{re.escape(item_num)}[\s.:\-—]+{re.escape(section_name)}"
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                start = match.start()
                # Find next section
                next_pattern = r"(?:ITEM|Item)\s+\d+[A-Za-z]?\s*[.:\-—]"
                next_match = re.search(next_pattern, full_text[match.end():], re.IGNORECASE)
                end = match.end() + next_match.start() if next_match else min(start + 50000, len(full_text))
                sections[f"Item {item_num}: {section_name}"] = full_text[start:end].strip()

        if not sections:
            sections["full_document"] = full_text[:100000]

        return sections

    def get_filing(
        self,
        ticker: str,
        filing_type: str = "10-K",
        count: int = 5,
    ) -> list[SECFiling]:
        """Full pipeline: list, download, and parse filings."""
        filings_list = self.get_filings_list(ticker, filing_type, count)
        results = []

        for filing_info in filings_list:
            try:
                html = self.download_filing(filing_info["url"])
                sections = self.parse_filing(html, filing_type)

                full_text = "\n\n".join(sections.values())

                results.append(SECFiling(
                    ticker=ticker.upper(),
                    cik=filing_info["cik"],
                    accession_number=filing_info["accession_number"],
                    filing_type=filing_type,
                    filing_date=filing_info["filing_date"],
                    url=filing_info["url"],
                    content=full_text,
                    sections=sections,
                ))
            except Exception as e:
                print(f"Error processing filing {filing_info.get('accession_number')}: {e}")
                continue

        return results

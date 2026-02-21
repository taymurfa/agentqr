"""CLI script for data ingestion."""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workers.ingestion_worker import ingest_company_data


async def main():
    parser = argparse.ArgumentParser(description="Ingest data for a company")
    parser.add_argument("ticker", help="Stock ticker (e.g., AAPL)")
    parser.add_argument("--sources", nargs="+", default=["sec_filings", "market_data", "news"],
                        help="Data sources to ingest")
    parser.add_argument("--filing-types", nargs="+", default=["10-K", "10-Q"],
                        help="SEC filing types")
    parser.add_argument("--num-filings", type=int, default=5,
                        help="Number of filings to fetch per type")

    args = parser.parse_args()

    print(f"Starting ingestion for {args.ticker.upper()}...")
    print(f"Sources: {args.sources}")
    print(f"Filing types: {args.filing_types}")

    await ingest_company_data(
        ticker=args.ticker,
        sources=args.sources,
        filing_types=args.filing_types,
        num_filings=args.num_filings,
    )

    print(f"Ingestion complete for {args.ticker.upper()}")


if __name__ == "__main__":
    asyncio.run(main())

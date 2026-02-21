"""CLI script to trigger research on a company."""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import async_session
from src.agents.orchestrator import OrchestratorAgent


async def main():
    parser = argparse.ArgumentParser(description="Run research on a company")
    parser.add_argument("ticker", help="Stock ticker (e.g., AAPL)")
    parser.add_argument("--depth", choices=["quick", "standard", "deep"], default="standard")
    parser.add_argument("--sector", default=None)

    args = parser.parse_args()

    print(f"Running {args.depth} research for {args.ticker.upper()}...")

    async with async_session() as db:
        orchestrator = OrchestratorAgent(db)
        result = await orchestrator.research(
            ticker=args.ticker,
            sector=args.sector,
            depth=args.depth,
        )

    print("\n" + "=" * 80)
    print(f"RESEARCH RESULTS: {args.ticker.upper()}")
    print("=" * 80)
    print(f"\nAgents used: {', '.join(result.get('agents_used', []))}")
    print(f"\n{result.get('synthesis', 'No synthesis generated')}")


if __name__ == "__main__":
    asyncio.run(main())

"""CLI script to run the full evaluation suite."""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.evaluation.retrieval_metrics import RetrievalMetrics
from src.evaluation.strategy_metrics import StrategyMetrics
from src.evaluation.benchmark import SystemBenchmark


async def run_benchmarks():
    """Run system benchmarks."""
    print("=" * 60)
    print("SYSTEM BENCHMARKS")
    print("=" * 60)

    bench = SystemBenchmark()

    print("\n[1/3] Embedding throughput...")
    try:
        emb_result = await bench.benchmark_embedding(num_texts=20)
        print(f"  Avg: {emb_result.avg_time_ms}ms | P95: {emb_result.p95_ms}ms | "
              f"Throughput: {emb_result.throughput_per_sec}/s")
    except Exception as e:
        print(f"  Skipped (API key needed): {e}")

    print("\n[2/3] Vector search latency...")
    try:
        vs_result = await bench.benchmark_vector_search(num_queries=10)
        print(f"  Avg: {vs_result.avg_time_ms}ms | P95: {vs_result.p95_ms}ms | "
              f"Throughput: {vs_result.throughput_per_sec}/s")
    except Exception as e:
        print(f"  Skipped (Pinecone needed): {e}")

    print("\n[3/3] LLM response latency...")
    try:
        llm_result = await bench.benchmark_llm_response(num_calls=3)
        print(f"  Avg: {llm_result.avg_time_ms}ms | P95: {llm_result.p95_ms}ms")
    except Exception as e:
        print(f"  Skipped (API key needed): {e}")

    return bench.get_summary()


def run_retrieval_eval():
    """Run retrieval quality evaluation with sample data."""
    print("\n" + "=" * 60)
    print("RETRIEVAL QUALITY EVALUATION")
    print("=" * 60)

    # Sample test queries with known relevant documents
    sample_queries = [
        {
            "retrieved_ids": ["doc1", "doc3", "doc5", "doc2", "doc8", "doc7", "doc4", "doc10", "doc6", "doc9"],
            "relevant_ids": {"doc1", "doc2", "doc3", "doc4"},
        },
        {
            "retrieved_ids": ["doc2", "doc1", "doc6", "doc3", "doc9", "doc4", "doc7", "doc5", "doc8", "doc10"],
            "relevant_ids": {"doc1", "doc2", "doc5"},
        },
        {
            "retrieved_ids": ["doc5", "doc3", "doc1", "doc8", "doc2", "doc7", "doc6", "doc4", "doc9", "doc10"],
            "relevant_ids": {"doc1", "doc3", "doc5", "doc8"},
        },
    ]

    results = RetrievalMetrics.evaluate_batch(sample_queries)
    print("\nAveraged metrics across sample queries:")
    for metric, value in results.items():
        print(f"  {metric}: {value}")

    return results


def run_strategy_eval():
    """Run strategy performance evaluation."""
    print("\n" + "=" * 60)
    print("STRATEGY PERFORMANCE EVALUATION")
    print("=" * 60)

    metrics = StrategyMetrics()

    tickers = ["SPY"]  # Use SPY as a baseline test
    for ticker in tickers:
        try:
            result = metrics.evaluate_strategy(ticker, signals=[], benchmark="SPY")
            if "error" not in result:
                perf = result.get("performance", {})
                print(f"\n{ticker}:")
                print(f"  Annual Return: {perf.get('annual_return')}%")
                print(f"  Sharpe Ratio: {perf.get('sharpe_ratio')}")
                print(f"  Max Drawdown: {perf.get('max_drawdown')}%")
                print(f"  Win Rate: {perf.get('win_rate')}%")
            else:
                print(f"\n{ticker}: {result['error']}")
        except Exception as e:
            print(f"\n{ticker}: Skipped ({e})")


async def main():
    print("AGENTIC QUANT RESEARCHER — EVALUATION SUITE")
    print("=" * 60)

    retrieval_results = run_retrieval_eval()
    strategy_results = run_strategy_eval()
    benchmark_results = await run_benchmarks()

    # Save results
    output = {
        "retrieval": retrieval_results,
        "benchmarks": benchmark_results,
    }

    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "evaluation_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())

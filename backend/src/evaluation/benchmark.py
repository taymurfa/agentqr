"""End-to-end latency benchmarks and throughput measurements."""

import time
import asyncio
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_per_sec: float


class SystemBenchmark:
    """Benchmarks system components for latency and throughput."""

    def __init__(self):
        self.results: list[BenchmarkResult] = []

    async def benchmark_embedding(self, num_texts: int = 100) -> BenchmarkResult:
        """Benchmark embedding generation throughput."""
        from src.knowledge_base.embeddings import EmbeddingGenerator

        embedder = EmbeddingGenerator()
        texts = [f"Sample text for embedding benchmark iteration {i}" for i in range(num_texts)]

        times = []
        for text in texts:
            start = time.perf_counter()
            embedder.embed_text(text)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = self._compute_stats("embedding_single", times)
        self.results.append(result)
        return result

    async def benchmark_vector_search(self, num_queries: int = 50) -> BenchmarkResult:
        """Benchmark vector search latency."""
        from src.knowledge_base.embeddings import EmbeddingGenerator
        from src.knowledge_base.vector_store import VectorStore

        embedder = EmbeddingGenerator()
        store = VectorStore()

        queries = [
            "revenue growth analysis", "risk factors", "competitive landscape",
            "earnings per share trend", "market opportunity",
        ] * (num_queries // 5 + 1)

        times = []
        for query in queries[:num_queries]:
            embedding = embedder.embed_query(query)
            start = time.perf_counter()
            store.query(vector=embedding, top_k=10)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = self._compute_stats("vector_search", times)
        self.results.append(result)
        return result

    async def benchmark_llm_response(self, num_calls: int = 10) -> BenchmarkResult:
        """Benchmark LLM response latency."""
        from anthropic import Anthropic
        from config.settings import get_settings

        settings = get_settings()
        client = Anthropic(api_key=settings.anthropic_api_key)

        prompts = [
            "Briefly analyze Apple's competitive position in 2 sentences.",
            "What are the key risk factors for semiconductor companies?",
            "Summarize the importance of free cash flow in valuation.",
        ] * (num_calls // 3 + 1)

        times = []
        for prompt in prompts[:num_calls]:
            start = time.perf_counter()
            client.messages.create(
                model=settings.anthropic_model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = self._compute_stats("llm_response", times)
        self.results.append(result)
        return result

    def _compute_stats(self, name: str, times: list[float]) -> BenchmarkResult:
        import numpy as np
        times_arr = np.array(times)
        total = sum(times)
        avg = np.mean(times_arr)
        throughput = len(times) / (total / 1000) if total > 0 else 0

        return BenchmarkResult(
            name=name,
            iterations=len(times),
            total_time_ms=round(total, 2),
            avg_time_ms=round(avg, 2),
            min_time_ms=round(np.min(times_arr), 2),
            max_time_ms=round(np.max(times_arr), 2),
            p50_ms=round(np.percentile(times_arr, 50), 2),
            p95_ms=round(np.percentile(times_arr, 95), 2),
            p99_ms=round(np.percentile(times_arr, 99), 2),
            throughput_per_sec=round(throughput, 2),
        )

    def get_summary(self) -> dict:
        """Get summary of all benchmark results."""
        return {
            r.name: {
                "avg_ms": r.avg_time_ms,
                "p50_ms": r.p50_ms,
                "p95_ms": r.p95_ms,
                "p99_ms": r.p99_ms,
                "throughput/s": r.throughput_per_sec,
            }
            for r in self.results
        }

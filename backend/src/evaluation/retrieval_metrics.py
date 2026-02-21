"""Retrieval quality metrics: Precision@k, Recall@k, MRR, NDCG."""

import numpy as np
from typing import Optional


class RetrievalMetrics:
    """Compute standard information retrieval metrics for RAG evaluation."""

    @staticmethod
    def precision_at_k(relevant: list[bool], k: int) -> float:
        """Fraction of top-k results that are relevant."""
        if k <= 0:
            return 0.0
        top_k = relevant[:k]
        return sum(top_k) / len(top_k)

    @staticmethod
    def recall_at_k(relevant: list[bool], total_relevant: int, k: int) -> float:
        """Fraction of all relevant docs found in top-k."""
        if total_relevant == 0:
            return 0.0
        top_k = relevant[:k]
        return sum(top_k) / total_relevant

    @staticmethod
    def mean_reciprocal_rank(relevant: list[bool]) -> float:
        """Reciprocal of the rank of the first relevant result."""
        for i, is_rel in enumerate(relevant):
            if is_rel:
                return 1.0 / (i + 1)
        return 0.0

    @staticmethod
    def ndcg_at_k(relevance_scores: list[float], k: int) -> float:
        """Normalized Discounted Cumulative Gain."""
        if k <= 0 or not relevance_scores:
            return 0.0

        top_k = relevance_scores[:k]
        dcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(top_k))

        ideal = sorted(relevance_scores, reverse=True)[:k]
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal))

        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def evaluate_query(
        retrieved_ids: list[str],
        relevant_ids: set[str],
        k_values: list[int] = None,
    ) -> dict:
        """Full evaluation of a single query against ground truth."""
        if k_values is None:
            k_values = [1, 3, 5, 10]

        relevant = [rid in relevant_ids for rid in retrieved_ids]
        total_relevant = len(relevant_ids)

        results = {}
        for k in k_values:
            results[f"precision@{k}"] = RetrievalMetrics.precision_at_k(relevant, k)
            results[f"recall@{k}"] = RetrievalMetrics.recall_at_k(relevant, total_relevant, k)

        results["mrr"] = RetrievalMetrics.mean_reciprocal_rank(relevant)

        # Binary relevance for NDCG
        scores = [1.0 if r else 0.0 for r in relevant]
        for k in k_values:
            results[f"ndcg@{k}"] = RetrievalMetrics.ndcg_at_k(scores, k)

        return results

    @staticmethod
    def evaluate_batch(
        queries: list[dict],
    ) -> dict:
        """
        Evaluate a batch of queries.
        Each query: {"retrieved_ids": [...], "relevant_ids": set(...)}
        Returns averaged metrics.
        """
        if not queries:
            return {}

        all_results = []
        for q in queries:
            result = RetrievalMetrics.evaluate_query(
                q["retrieved_ids"], q["relevant_ids"]
            )
            all_results.append(result)

        avg = {}
        for key in all_results[0]:
            avg[key] = np.mean([r[key] for r in all_results])

        return {k: round(v, 4) for k, v in avg.items()}

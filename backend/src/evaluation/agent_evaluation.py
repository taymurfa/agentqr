"""Agent response quality evaluation: LLM-as-judge + factual accuracy."""

from anthropic import Anthropic
from config.settings import get_settings


class AgentEvaluator:
    """Evaluates agent response quality using LLM-as-judge methodology."""

    JUDGE_PROMPT = """You are an expert financial analyst evaluating the quality of AI-generated research responses.

Score the following response on each criterion (1-10):

1. **Accuracy**: Are the facts, numbers, and claims correct based on the source material?
2. **Completeness**: Does the response cover all important aspects of the query?
3. **Relevance**: Is the response focused on what was asked?
4. **Depth**: Does it provide meaningful analysis beyond surface-level information?
5. **Actionability**: Does it provide clear, actionable insights?
6. **Source Attribution**: Does it cite sources and distinguish facts from inference?

## Source Material
{source_context}

## Query
{query}

## Agent Response
{response}

Output your evaluation as JSON:
{{
  "accuracy": <1-10>,
  "completeness": <1-10>,
  "relevance": <1-10>,
  "depth": <1-10>,
  "actionability": <1-10>,
  "source_attribution": <1-10>,
  "overall": <1-10>,
  "reasoning": "<brief explanation>"
}}"""

    def __init__(self):
        settings = get_settings()
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    def evaluate_response(
        self,
        query: str,
        response: str,
        source_context: str = "",
    ) -> dict:
        """Evaluate a single agent response using LLM-as-judge."""
        prompt = self.JUDGE_PROMPT.format(
            source_context=source_context[:5000],
            query=query,
            response=response[:5000],
        )

        result = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system="You are an impartial evaluation judge. Output valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        try:
            scores = json.loads(result.content[0].text)
        except json.JSONDecodeError:
            scores = {"error": "Failed to parse evaluation", "raw": result.content[0].text}

        return scores

    def evaluate_factual_accuracy(
        self,
        response: str,
        source_documents: list[str],
    ) -> dict:
        """Check if claims in the response are supported by source documents."""
        sources_text = "\n\n---\n\n".join(doc[:2000] for doc in source_documents[:5])

        prompt = f"""Analyze the following AI-generated response and check each factual claim against the source documents.

## Source Documents
{sources_text}

## Response to Check
{response[:3000]}

For each claim in the response, determine:
- SUPPORTED: The claim is directly supported by the source documents
- UNSUPPORTED: The claim cannot be verified from the sources
- CONTRADICTED: The claim contradicts the source documents

Output JSON:
{{
  "total_claims": <number>,
  "supported": <number>,
  "unsupported": <number>,
  "contradicted": <number>,
  "accuracy_score": <0-1>,
  "details": [
    {{"claim": "...", "verdict": "SUPPORTED|UNSUPPORTED|CONTRADICTED", "evidence": "..."}}
  ]
}}"""

        result = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system="You are a fact-checking system. Output valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        try:
            return json.loads(result.content[0].text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse", "raw": result.content[0].text}

    def evaluate_batch(self, test_cases: list[dict]) -> dict:
        """Evaluate a batch of test cases and return averaged scores."""
        all_scores = []
        for case in test_cases:
            scores = self.evaluate_response(
                query=case["query"],
                response=case["response"],
                source_context=case.get("source_context", ""),
            )
            if "error" not in scores:
                all_scores.append(scores)

        if not all_scores:
            return {"error": "No valid evaluations"}

        import numpy as np
        metrics = ["accuracy", "completeness", "relevance", "depth", "actionability", "source_attribution", "overall"]
        avg = {}
        for m in metrics:
            values = [s.get(m, 0) for s in all_scores if m in s]
            avg[m] = round(np.mean(values), 2) if values else 0

        avg["num_evaluated"] = len(all_scores)
        return avg

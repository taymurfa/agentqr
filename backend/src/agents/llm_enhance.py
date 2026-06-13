"""Optional LLM enhancement for strategy hypotheses.

Calls OpenAI if a key is configured; otherwise falls back to the deterministic
template hypothesis. The pipeline must remain fully functional without an API key.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from config.settings import get_settings


SYSTEM_PROMPT = (
    "You are a buy-side quant strategist writing concise strategy memos. "
    "Given a strategy template and its backtest stats, write a 2-3 sentence "
    "investment hypothesis explaining the economic intuition for *why* this "
    "strategy works. No hedging language, no disclaimers, no headers. "
    "Plain prose only."
)


async def enhance_hypothesis(
    command: str,
    signal_type: str,
    universe: list[str],
    template_hypothesis: str,
    backtest_summary: dict,
    timeout_s: float = 8.0,
) -> str:
    """Return an enriched hypothesis, or `template_hypothesis` if no LLM is configured."""
    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        return template_hypothesis

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        user = (
            f"Original command: {command}\n"
            f"Signal: {signal_type}\n"
            f"Universe: {', '.join(universe)}\n"
            f"Template hypothesis: {template_hypothesis}\n"
            f"Backtest stats: Sharpe {backtest_summary.get('sharpe_ratio')}, "
            f"AnnRet {backtest_summary.get('annualized_return')}%, "
            f"MaxDD {backtest_summary.get('max_drawdown')}%, "
            f"AnnVol {backtest_summary.get('annualized_volatility')}%."
        )
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.openai_model or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                max_tokens=240,
                temperature=0.4,
            ),
            timeout=timeout_s,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or template_hypothesis
    except Exception as e:
        print(f"[llm_enhance] fallback to template, reason: {e}")
        return template_hypothesis

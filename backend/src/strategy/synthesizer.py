"""Strategy synthesizer: combines agent outputs into actionable recommendations."""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from config.settings import get_settings
from src.database.models import Strategy


class StrategySynthesizer:
    """Combines research from multiple agents into trading strategy recommendations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    async def synthesize(
        self,
        agent_outputs: list[dict],
        tickers: list[str],
        sector: Optional[str] = None,
    ) -> dict:
        """Generate a strategy recommendation from agent outputs."""
        context = self._build_synthesis_context(agent_outputs)

        prompt = f"""Based on the following multi-agent research outputs, synthesize a concrete trading strategy.

Tickers under analysis: {', '.join(tickers)}
{'Sector: ' + sector if sector else ''}

Provide:
1. **Strategy Name**: A descriptive name for this strategy
2. **Recommendation**: BUY / SELL / HOLD / WATCH for each ticker
3. **Rationale**: Why this recommendation, citing specific data points
4. **Confidence Level**: 0-100% with justification
5. **Risk Assessment**: Key risks and how they affect the strategy
6. **Position Sizing Suggestion**: Based on confidence and risk
7. **Entry/Exit Criteria**: Specific price levels or conditions
8. **Time Horizon**: Short (1-4 weeks), Medium (1-6 months), Long (6+ months)

Output as JSON with these fields."""

        response = self.client.chat.completions.create(
            model=self.settings.openai_model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": "You are a quantitative strategy synthesizer. Output valid JSON."},
                {"role": "user", "content": f"{prompt}\n\n{context}"}
            ],
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content or "{}"


        try:
            strategy_data = json.loads(content)
        except json.JSONDecodeError:
            strategy_data = {
                "name": f"Research Strategy - {', '.join(tickers)}",
                "recommendation": "Review",
                "rationale": content,
                "confidence": 50,
            }

        # Persist strategy
        strategy = Strategy(
            name=strategy_data.get("name", f"Strategy {datetime.utcnow().strftime('%Y%m%d')}"),
            sector=sector,
            tickers=tickers,
            recommendation=strategy_data.get("recommendation", "Review"),
            rationale=strategy_data.get("rationale", ""),
            confidence=strategy_data.get("confidence"),
            risk_assessment=strategy_data.get("risk_assessment", ""),
            agent_outputs={r.get("agent", "unknown"): r.get("content", "")[:2000] for r in agent_outputs},
        )
        self.db.add(strategy)
        await self.db.commit()
        await self.db.refresh(strategy)

        return {
            "strategy_id": str(strategy.id),
            **strategy_data,
        }

    def _build_synthesis_context(self, agent_outputs: list[dict]) -> str:
        parts = []
        for output in agent_outputs:
            agent = output.get("agent", "unknown")
            content = output.get("content", "")
            parts.append(f"## {agent.replace('_', ' ').title()}\n\n{content}")
        return "\n\n---\n\n".join(parts)

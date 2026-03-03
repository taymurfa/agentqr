# CLAUDE.md — Agentic Quant Researcher

Multi-agent RAG system for equity research. 4 AI agents (Orchestrator, Sector Researcher, Fundamental Analyst, Technical Analyst) ingest SEC filings, compute indicators, and deliver buy/hold/sell recommendations.

**Stack:** FastAPI (Python 3.11+) backend, Next.js 14 (TypeScript) frontend, Anthropic Claude, Pinecone vector DB, fastembed (local embeddings), yfinance, SQLAlchemy async, Tailwind CSS.

## Run Locally
- **Backend:** `cd backend && source .venv/bin/activate && pip install -r requirements.txt && uvicorn main:app --port 8000`
- **Frontend:** `cd frontend && npm install && npm run dev` (runs on :3000)
- **Env:** Copy `.env.example` → `.env`. Required keys: `ANTHROPIC_API_KEY`, `PINECONE_API_KEY`, `SEC_EDGAR_USER_AGENT`.

## Key Conventions
- **Python imports:** Always absolute from `backend/` root (`from src.agents.base_agent import BaseAgent`). Never relative.
- **Async everywhere.** All DB ops, LLM calls, and handlers use `async def`/`await`.
- **Math never done by LLM.** Financial ratios and indicators computed by Python (`ta` library, yfinance). Claude only interprets results.
- **Agents run sequentially** in the orchestrator to avoid DB locking.
- **Graceful degradation:** If Pinecone/yfinance fails, agents continue with local data.
- **Frontend:** Named exports, `"use client"` on stateful components, props typed with `interface`, Tailwind + `cn()` utility, npm (not yarn).

## Pitfalls
- yfinance must be >= 0.2.52. Pinecone index must be 384-dim. SEC EDGAR rate limit: 10 req/s. No auth on any endpoint. No tests exist yet. No linting configured.

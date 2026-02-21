# Agentic Quant Researcher

> A multi-agent AI research system that reads SEC filings, computes real technical indicators, and synthesizes institutional-quality equity research reports — automatically.

---

## What It Does

Most retail investors don't have time to read a 200-page 10-K or run a DCF model. This system deploys a pipeline of specialized AI agents that work together as an automated research desk:

| Agent | What it does |
|---|---|
| **Sector Researcher** | RAG search over SEC 10-K/10-Q filings, extracts risk factors, competitive positioning, and management guidance |
| **Fundamental Analyst** | Live P/E, ROE, Debt/Equity, profit margins, EPS growth, full income statement + balance sheet parsing |
| **Technical Analyst** | RSI(14), MACD(12,26,9), Bollinger Bands, SMA/EMA crossovers, ADX, ATR + 2-year backtest (Sharpe, Max Drawdown, Win Rate) |
| **Orchestrator** | Synthesizes all three into a unified Buy/Hold/Sell recommendation with a confidence score and risk matrix |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Next.js 14 Frontend                 │
│     Research Pages · Chat · Strategies · Dashboard  │
└──────────────────────┬──────────────────────────────┘
                       │ REST + SSE (streaming chat)
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│  Agents · RAG Pipeline · Ingestion · Data APIs      │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  yfinance    │  │  SEC EDGAR   │  (data sources) │
│  │  Polygon.io  │  │  Pinecone    │  (vector store) │
│  └──────────────┘  └──────────────┘                 │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  SQLite/PG   │  │  fastembed   │  (local embed)  │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  Anthropic API  │  Claude — agent reasoning
              └─────────────────┘
```

**Key design decisions:**
- **Local embeddings** via `fastembed` (BAAI/bge-small-en-v1.5, 384-dim) — no embedding API cost, no rate limits
- **yfinance ≥ 1.2.0** — earlier versions (0.2.x) are broken due to a Yahoo Finance API format change; `curl_cffi` is required
- **Namespace-per-ticker** Pinecone isolation — fast, focused vector retrieval per company
- **Async-first FastAPI** — `AsyncAnthropic` client so 30–60s LLM calls never block the event loop
- **Deterministic math** — all indicators and backtests use the `ta` library, not LLM inference

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.11+** | [python.org](https://python.org) |
| **Node.js 18+** | [nodejs.org](https://nodejs.org) |
| **Anthropic API key** | [console.anthropic.com](https://console.anthropic.com) — Claude powers all agents |
| **Pinecone API key** | [app.pinecone.io](https://app.pinecone.io) — free Serverless tier is sufficient |
| **Polygon.io key** | Optional — Yahoo Finance is used as default fallback |

---

## Setup & Running Locally

### 1 — Clone the repo

```bash
git clone https://github.com/your-username/agentic-quant-researcher.git
cd agentic-quant-researcher
```

### 2 — Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate — Windows
.venv\Scripts\activate

# Activate — macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Open `.env` and fill in at minimum:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `PINECONE_API_KEY` — from [app.pinecone.io](https://app.pinecone.io)
- `PINECONE_INDEX_NAME` — any name, e.g. `quant-researcher` (created automatically on first run)
- `SEC_EDGAR_USER_AGENT` — required by EDGAR: `"Your Name your@email.com"`

```bash
# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000
```

- API: **http://localhost:8000**
- Swagger docs: **http://localhost:8000/docs**

### 3 — Frontend

```bash
cd frontend

npm install

cp .env.example .env.local
# NEXT_PUBLIC_API_URL is already set to http://localhost:8000

npm run dev
```

App: **http://localhost:3000**

---

## Usage Guide

### Step 1 — Ingest a company

Go to **Research** → search for a ticker → click **Ingest**. This:
1. Fetches SEC 10-K / 10-Q filings from EDGAR
2. Downloads OHLCV price history and financial ratios from Yahoo Finance
3. Chunks and embeds documents → stores in Pinecone (namespace = ticker)
4. Saves fundamentals to SQLite

Ingestion takes ~30–90 seconds per company.

### Step 2 — Run research

On any company page, click **Run Research**. The three agents run sequentially (~45–90 seconds total), then the Orchestrator synthesises a final report with:

- 🎯 Price targets (bull / base / bear)
- 📊 All computed indicator readings with signals
- 💰 Full valuation table (P/E, EV/EBITDA, DCF context, peer comparison)
- ⚠️ Risk factor matrix with severity ratings
- 📈 2-year backtest (SMA crossover strategy) with Sharpe ratio and max drawdown

### Step 3 — Chat interface

Use the **Chat** tab for targeted queries:

```
Research AAPL — full analysis
/technical TSLA
/fundamental MSFT
Compare NVDA vs AMD
What are the key risks for ACN?
```

---

## Project Structure

```
├── backend/
│   ├── api/
│   │   └── routes/              # FastAPI endpoints (research, companies, chat, etc.)
│   ├── config/
│   │   ├── prompts/             # Agent system prompts (markdown, easy to tune)
│   │   └── settings.py          # Pydantic settings (reads .env)
│   ├── src/
│   │   ├── agents/
│   │   │   ├── orchestrator.py  # Master agent — plans, delegates, synthesizes
│   │   │   ├── sector_researcher.py
│   │   │   ├── fundamental_analyst.py
│   │   │   ├── technical_analyst.py
│   │   │   └── tools/           # AnalysisTools, DataTools, SearchTools
│   │   ├── database/            # SQLAlchemy async models + session
│   │   ├── ingestion/           # SEC EDGAR fetcher, yfinance client, market data
│   │   └── knowledge_base/      # fastembed embeddings, Pinecone vector store, chunking
│   ├── workers/                 # Background ingestion worker (arq)
│   ├── main.py                  # FastAPI app entrypoint
│   ├── requirements.txt
│   ├── .env.example             # ← copy this to .env
│   └── .env                     # ← git-ignored, never committed
│
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # Chat, layout, charts, research cards
│   │   ├── hooks/               # useChat (SSE streaming)
│   │   └── lib/                 # API client, formatters
│   ├── .env.example             # ← copy this to .env.local
│   └── package.json
│
└── paper/                       # Academic research paper (LaTeX + HTML)
```

---

## Environment Variables

### Backend — `backend/.env`

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key — [console.anthropic.com](https://console.anthropic.com) |
| `PINECONE_API_KEY` | ✅ | Vector store — [app.pinecone.io](https://app.pinecone.io) |
| `PINECONE_ENVIRONMENT` | ✅ | e.g. `us-east-1` |
| `PINECONE_INDEX_NAME` | ✅ | Index name (created automatically, e.g. `quant-researcher`) |
| `DATABASE_URL` | ✅ | `sqlite+aiosqlite:///quant_researcher.db` for local; PostgreSQL URL for production |
| `SEC_EDGAR_USER_AGENT` | ✅ | `"Your Name your@email.com"` — required by EDGAR fair-use policy |
| `ANTHROPIC_MODEL` | ⬜ | Default: `claude-sonnet-4-5` |
| `POLYGON_API_KEY` | ⬜ | Optional premium OHLCV data. Yahoo Finance is used if this is blank. |

### Frontend — `frontend/.env.local`

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL — default: `http://localhost:8000` |

---

## Important: yfinance Version

**Do not use yfinance `0.2.x`** — Yahoo Finance changed their API format and all `0.2.x` versions return empty data silently. This project requires **yfinance `>=1.2.0`** (already pinned in `requirements.txt`), which uses `curl_cffi` for proper API access.

```bash
# Verify you have the correct version
pip show yfinance  # should be 1.2.0+
```

---

## Production Deployment

| Service | Recommendation |
|---|---|
| **Backend** | [Railway](https://railway.app) or any Docker host. Set `DATABASE_URL` to a PostgreSQL URL. |
| **Frontend** | [Vercel](https://vercel.com). Set `NEXT_PUBLIC_API_URL` to your Railway backend URL. |
| **Database** | Railway PostgreSQL addon, Supabase, or Neon. |
| **Vector DB** | Pinecone Serverless (free tier) — no changes needed. |

---

## Team

| Name | Role |
|---|---|
| Ayush Agarwal | Team Lead, Architecture |
| Dhruv Jhamb | Backend & Agent Logic |
| Hamza Adwan | Data Pipeline & RAG |
| Aarush Agarwal | Frontend & UI |
| Taymur Faruqui | Research & Paper |

---

## License

MIT

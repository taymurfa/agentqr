# Agentic Quant Researcher

> A multi-agent, RAG-powered quantitative research system that reads SEC filings, computes deterministic technical indicators, and synthesizes institutional-grade equity research reports — automatically.

![License](https://img.shields.io/badge/license-MIT-blue) ![Python](https://img.shields.io/badge/python-3.11+-green) ![Next.js](https://img.shields.io/badge/Next.js-14-black) ![TypeScript](https://img.shields.io/badge/TypeScript-strict-blue)

---

## What It Does

Most retail investors don't have time to read a 200-page 10-K or run a DCF model. This project bridges that gap by deploying a pipeline of specialized AI agents that work together as an automated research desk:

| Agent | Role |
|---|---|
| **Sector Researcher** | Queries SEC 10-K/10-Q filings via RAG vector search, extracts risk factors, management guidance, and competitive positioning |
| **Fundamental Analyst** | Computes P/E, ROE, Debt/Equity, profit margins, DCF framework, and a 1–10 financial health score from live Yahoo Finance data |
| **Technical Analyst** | Runs RSI, MACD, Bollinger Bands, SMA crossovers, ATR, and a 2-year SMA backtest (Sharpe, Max Drawdown, Win Rate) |
| **Orchestrator** | Synthesizes all three agent outputs into a unified Buy/Hold/Sell recommendation with confidence score |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js 14 Frontend                   │
│    Dashboard · Research Pages · Chat · Strategies        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WebSocket (SSE streaming)
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │  Ingestion │  │    Agents    │  │   Chat Engine    │ │
│  │  Pipeline  │  │ Orchestrator │  │ (streaming SSE)  │ │
│  └─────┬──────┘  └─────┬────────┘  └──────────────────┘ │
│        │               │                                  │
│  ┌─────▼──────┐  ┌─────▼──────┐                          │
│  │ SEC EDGAR  │  │  Pinecone  │  ← vector search (RAG)  │
│  │  yfinance  │  │  SQLite /  │                          │
│  │  Polygon   │  │ PostgreSQL │  ← companies, history   │
│  └────────────┘  └────────────┘                          │
└─────────────────────────────────────────────────────────┘
              ┌────────────────────┐
              │  Anthropic Claude  │  agent reasoning
              └────────────────────┘
              ┌────────────────────┐
              │  fastembed (local) │  384-dim embeddings, free
              └────────────────────┘
```

**Key design decisions:**
- **Local embeddings** via `fastembed` (BAAI/bge-small-en-v1.5, 384-dim) — no Voyage AI bill, no rate limits
- **Namespace-per-ticker** Pinecone isolation for fast, focused vector retrieval
- **Async-first** — `AsyncAnthropic` so the FastAPI loop is never blocked during LLM calls
- **Deterministic math** — indicators and backtests use the `ta` library, never inferred by the LLM

---

## Prerequisites

| Dependency | Version | Where to get it |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Anthropic API Key | — | [console.anthropic.com](https://console.anthropic.com) |
| Pinecone API Key | — | [app.pinecone.io](https://app.pinecone.io) |
| Polygon API Key | optional | [polygon.io](https://polygon.io) — Yahoo Finance used as fallback |

> ⚠️ **yfinance note:** `yfinance==0.2.50` is broken (Yahoo changed their API format). The `requirements.txt` pins `>=0.2.52`. Always install from `requirements.txt`, not manually.

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/your-org/agentic-quant-researcher.git
cd agentic-quant-researcher
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate
.venv\Scripts\activate        # Windows PowerShell
source .venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
# Open .env and set ANTHROPIC_API_KEY, PINECONE_API_KEY, etc.

# Run the API server
uvicorn main:app --host 0.0.0.0 --port 8000
```

API is live at **http://localhost:8000** · Docs at **http://localhost:8000/docs**

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file (default value works for local dev)
cp .env.example .env.local

# Run the dev server
npm run dev
```

App is live at **http://localhost:3000**

---

## Usage

### Ingest a Company
`Research` tab → search a ticker → click **Ingest**

This downloads SEC 10-K/10-Q filings, fetches OHLCV + ratios from Yahoo Finance, embeds and stores everything in Pinecone, and saves fundamentals to the local database.

### Run Full Research
On any company page → **Run Research** (~45–90 seconds)

All three agents run sequentially, then the Orchestrator synthesizes a report with price targets, indicator readings, risk factor matrix, and backtested strategy performance.

### Chat Interface
Use the **Chat** tab:
```
Research AAPL — full analysis    → all three agents
/technical TSLA                  → Technical Analyst only
/fundamental MSFT                → Fundamental Analyst only
Compare AAPL vs MSFT             → side-by-side comparison
```

---

## Environment Variables

### Backend (`.env`)

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key for all agent reasoning |
| `PINECONE_API_KEY` | ✅ | Vector store for SEC filing embeddings |
| `PINECONE_INDEX_NAME` | ✅ | Index name (e.g. `quant-researcher-local`) |
| `DATABASE_URL` | ✅ | `sqlite+aiosqlite:///quant_researcher.db` for local dev |
| `SEC_EDGAR_USER_AGENT` | ✅ | `"Your Name your@email.com"` — required by EDGAR fair-use policy |
| `POLYGON_API_KEY` | ⬜ | Optional premium market data; Yahoo Finance is the fallback |
| `ANTHROPIC_MODEL` | ⬜ | Claude model (default: `claude-sonnet-4-5`) |

### Frontend (`.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend URL (default: `http://localhost:8000`) |

---

## Project Structure

```
├── backend/
│   ├── api/routes/          # FastAPI route handlers (companies, research, chat, monitoring)
│   ├── config/
│   │   ├── prompts/         # Agent system prompts (markdown)
│   │   └── settings.py      # Pydantic settings — reads .env
│   ├── src/
│   │   ├── agents/          # Orchestrator + 3 specialist agents
│   │   │   └── tools/       # AnalysisTools (indicators), DataTools, SearchTools
│   │   ├── database/        # SQLAlchemy async models + session
│   │   ├── ingestion/       # SEC EDGAR fetcher, yfinance/Polygon market data client
│   │   └── knowledge_base/  # fastembed embeddings + Pinecone vector store
│   ├── main.py              # FastAPI app entrypoint
│   ├── requirements.txt
│   ├── .env.example
│   └── .env                 # ← never committed (gitignored)
│
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   ├── components/      # UI components (chat, layout, charts)
│   │   ├── hooks/           # useChat (WebSocket/SSE streaming)
│   │   └── lib/             # API client, utils
│   ├── .env.example
│   └── .env.local           # ← never committed (gitignored)
│
└── paper/                   # Academic research paper (LaTeX + HTML)
```

---

## Production Deployment

| Layer | Platform | Notes |
|---|---|---|
| Backend | [Railway](https://railway.app) | Set `DATABASE_URL` to a PostgreSQL connection string |
| Frontend | [Vercel](https://vercel.com) | Set `NEXT_PUBLIC_API_URL` to your Railway URL |
| Database | Railway PostgreSQL addon | Or any managed Postgres provider |
| Vector DB | Pinecone Serverless | Index auto-created on first run; dimension = 384 |

---

## Known Issues / Gotchas

- **yfinance ≥ 0.2.52 required** — older versions fail silently with empty DataFrames due to Yahoo API changes
- **Pinecone dimension mismatch** — if you previously used a 1024-dim index (Voyage AI), the app will automatically delete and recreate it at 384-dim on startup
- **Windows + Uvicorn** — run single-worker mode (`uvicorn main:app` without `--workers N`); multi-worker mode is unstable on Windows due to multiprocessing fork issues
- **SEC EDGAR rate limits** — EDGAR allows ~10 req/s; the ingestion pipeline respects this but large batches may be slow

---

## Team

| Name | Role |
|---|---|
| Ayush Agarwal | Team Lead |
| **Aarush Agarwal** | **Primary Developer** — full-stack implementation, agents, RAG pipeline, UI |
| Dhruv Jhamb | Member |
| Hamza Adwan | Member |
| Taymur Faruqui | Member |

---

## License

MIT — see [LICENSE](LICENSE) for details.

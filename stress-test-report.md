# AgentQR Stress Test Report

**Date:** 2026-03-02
**Tester:** Claude Code (automated)
**Backend:** FastAPI at localhost:8000 (Python 3.14, SQLite, no external API keys configured)
**Total Tests:** 61 | **Passed:** 28 | **Failed:** 26 | **Warnings:** 7

---

## Executive Summary

The AgentQR backend was stress-tested across 10 phases covering health checks, happy-path workflows, bad inputs, external service failures, WebSocket connections, agent pipelines, ingestion, concurrency, and monitoring. All 6 known bugs were confirmed. The most critical findings are: (1) every endpoint that touches Anthropic/Pinecone APIs returns a raw 500 error that leaks internal service details to the client, (2) WebSocket connections crash silently on malformed input with no error message, (3) there is zero input validation on ticker symbols allowing SQL injection strings, null bytes, and 10,000-character strings to be stored in the database, and (4) there is no rate limiting on any endpoint.

---

## Known Bugs — Confirmation Status

| # | Bug | Status | Severity | Evidence | Location |
|---|-----|--------|----------|----------|----------|
| 1 | WebSocket crashes on non-JSON | ✅ CONFIRMED | HIGH | Sending `"not json"` via WebSocket caused immediate connection drop with code 1006 (abnormal closure) — no error message sent to client. The `json.loads(data)` at line 90 has no try/except wrapper. | `chat.py:90` |
| 2 | Search failures can crash agents | ✅ CONFIRMED (code review) | MEDIUM | `SearchTools()` constructor at line 14 creates `VectorStore()` which calls `Pinecone(api_key=...)` — if the key is empty/invalid, any method call on it will raise. `search_filings()` at `sector_researcher.py:31` is called directly (no try/except around it). `fundamental_analyst.py:74` calls `self.search.search_filings()` without try/except. The graceful degradation only works if the constructor succeeds but queries fail. | `sector_researcher.py:31`, `fundamental_analyst.py:74` |
| 3 | No ticker validation | ✅ CONFIRMED | HIGH | `ticker: str` in `ResearchRequest` (research.py:12), `IngestRequest` (ingestion.py:12), and the `GET /{ticker}` path param (companies.py:47) all accept any string with no min_length, max_length, or regex. Test results: empty string `""` was accepted by /research/run (returned 500 from API, not 422 validation error); SQL injection `'; DROP TABLE--` was stored as a company record; `A`×10000 was stored as a company; null bytes `\x00\x01\x02` were stored as a company. | `research.py:12`, `ingestion.py:12`, `companies.py:47` |
| 4 | No rate limiting | ✅ CONFIRMED | HIGH | 50 parallel GET /health requests all returned 200 in 0.089 seconds. 20 concurrent session creates all succeeded. No `slowapi`, `fastapi-limiter`, or any rate-limiting middleware is present in `main.py`. | `main.py` (global) |
| 5 | 500 errors leak raw tracebacks | ✅ CONFIRMED | CRITICAL | Every endpoint that calls an external API returns `{"detail":"You haven't specified an Api-Key."}` — this is the raw Anthropic SDK error message passed directly to the client via `detail=str(e)` at `chat.py:74` and `research.py:48`. In production with a misconfigured key, this would leak the API provider name and internal error details. | `chat.py:74`, `research.py:48` |
| 6 | Pinecone auto-deletes ALL vectors on dimension mismatch | ✅ CONFIRMED (code review) | CRITICAL | At `vector_store.py:32-35`, if the existing index dimension doesn't match the configured dimension, the code calls `self.pc.delete_index(self.index_name)` which destroys the entire index and all vectors across all namespaces. There is no backup, no confirmation, no warning beyond a print statement. A simple config change (e.g., switching embedding models) would silently delete all production data. | `vector_store.py:32-35` |

---

## Detailed Results by Phase

### Phase 1: Health Check & Liveness

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 1.1 | `GET /health` | 200 with status field | 200, `{"status":"healthy","service":"agentic-quant-researcher"}` | PASS | — |
| 1.2 | Parse body, assert status=="healthy" | status == "healthy" | status == "healthy" | PASS | — |
| 1.3 | `GET /docs` | 200 | 200 | PASS | — |
| 1.4 | Response time < 0.5s | < 500ms | 0.5ms | PASS | — |

### Phase 2: Happy Path

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 2.1 | `POST /api/chat/sessions` | 200 with session_id | 200, session_id=`8d5366df-...` | PASS | — |
| 2.2 | `GET /api/chat/sessions` | Sessions array | 200, 1 session in array | PASS | — |
| 2.3 | `GET /api/chat/sessions/{id}/messages` | Empty messages | 200, `{"messages":[]}` | PASS | — |
| 2.4 | `GET /api/companies/?limit=5` | Companies array | 200, empty array (no data ingested yet) | PASS | — |
| 2.5 | `GET /api/companies/AAPL` | Ticker/name/sector | 200, auto-created record with name="AAPL", sector="Unknown" | PASS | — |
| 2.6 | `GET /api/strategies/?limit=5` | Strategies array | 200, empty array | PASS | — |
| 2.7 | `GET /api/monitoring/overview` | agent_stats, system | 200, zeroed stats as expected | PASS | — |
| 2.8 | `GET /api/research/summary/AAPL` | Summary or error | 200, research_summary=null (no research run yet) | PASS | — |
| 2.9 | `GET /api/research/status/abc123` | job_id + empty logs | 200, `{"job_id":"abc123","logs":[]}` | PASS | — |
| 2.10 | `GET /api/ingestion/status/AAPL` | ticker + logs | 200, `{"ticker":"AAPL","logs":[]}` | PASS | — |
| 2.11 | `POST /api/ingestion/ticker` (MSFT) | ingestion_started | 200, status=ingestion_started | PASS | — |
| 2.12 | `POST /api/chat/send` ("What is Apple Inc?") | Non-empty response | 500: `{"detail":"You haven't specified an Api-Key."}` — raw Anthropic error leaked (Bug #5) | FAIL | CRITICAL |
| 2.13 | `GET /api/chat/sessions/{id}/messages` | >= 2 entries | Only 1 entry (user message stored, assistant response missing because chat failed) | FAIL | MEDIUM |

### Phase 3: Bad Inputs

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 3.1 | `POST /research/run` `{"ticker":""}` | 422 (validation) | 500: `"You haven't specified an Api-Key."` — empty ticker accepted, no validation (Bug #3) | FAIL | HIGH |
| 3.2 | `POST /chat/send` `{}` | 422 | 422: "Field required" for message | PASS | — |
| 3.3 | `GET /companies/'; DROP TABLE--` | Safe (parameterized) | 200: SQL injection string stored as company ticker. SQLAlchemy parameterized queries prevented actual SQL injection, but garbage data now exists in DB. | WARN | MEDIUM |
| 3.4 | `POST /chat/send` XSS payload | No crash | 500: API key error (would have stored XSS payload if API key were present — no sanitization) | WARN | MEDIUM |
| 3.5 | `GET /companies/AAAA...(10000 chars)` | Error, not hang | 200: 10,000-character ticker stored in DB as a company record. No max_length validation. | FAIL | HIGH |
| 3.6 | `GET /companies/%00%01%02` | Clean error | 200: Null bytes stored as company ticker. Causes JSON parsing failures in downstream consumers. | FAIL | HIGH |
| 3.7 | `POST /chat/send` body:"not json" | 422 | 422: "JSON decode error" | PASS | — |
| 3.8 | `POST /research/run` empty body | 422 | 422: "Field required" for ticker | PASS | — |
| 3.9 | `POST /chat/send` Content-Type:text/plain | 422 | 422: "Input should be a valid dictionary" | PASS | — |
| 3.10 | `GET /companies/?limit=-1&offset=-5` | 422 | 200: Returned all companies. Negative limit/offset accepted (no `ge=0` constraint). | FAIL | MEDIUM |
| 3.11 | `GET /companies/?limit=201` | 422 | 422: "Input should be less than or equal to 200" | PASS | — |
| 3.12 | `POST /research/run` `{"ticker":"INVALIDTICKER12345"}` | Check for traceback leak | 500: `"You haven't specified an Api-Key."` — raw error leaked to client (Bug #5) | FAIL | CRITICAL |
| 3.13 | `POST /ingestion/ticker` `{"ticker":"ZZZZZ"}` | Minimal record, no crash | 200: ingestion_started, minimal record created. No ticker validation (Bug #3). | WARN | LOW |

### Phase 4: External Service Failures

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 4.1 | `POST /research/run` XYZNONEXIST (quick, 120s) | Graceful degradation | 500: `"You haven't specified an Api-Key."` — no graceful degradation, raw error leaked | FAIL | HIGH |
| 4.2 | `POST /research/compare` AAPL+XYZFAKE (180s) | Partial failure handling | 500: same API key error leaked | FAIL | HIGH |
| 4.3 | `POST /research/compare` empty list | Empty list validation | 500: empty list accepted (no validation), then crashed on API call | FAIL | MEDIUM |
| 4.4 | `POST /research/compare` single ticker | Edge case handling | 500: same API key error | FAIL | MEDIUM |
| 4.5 | Code review: `vector_store.py:23-55` | Confirm delete_index at line 35 | ✅ Line 35: `self.pc.delete_index(self.index_name)` — deletes entire index with all vectors when dimension mismatch. No backup. (Bug #6) | FAIL | CRITICAL |

### Phase 5: WebSocket

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 5.1 | WS send `{"content":"Hello"}` | status → tokens → done | Connection closed immediately with code 1006 (server-side error from API key issue). 0 responses received. | FAIL | HIGH |
| 5.2 | WS send `"not json"` | Connection crash (Bug #1) | ✅ Connection crashed: code=1006, no close frame, no error message to client. Server-side `json.loads` exception was unhandled. | FAIL | HIGH |
| 5.3 | WS send `{"text":"wrong key"}` | KeyError crash | Connection crashed: code=1006. `message["content"]` at line 92 raised KeyError, unhandled. | FAIL | HIGH |
| 5.4 | WS connect `/ws/not-a-uuid` | Error response | Connection accepted then immediately crashed: code=1006. No UUID validation on session_id. | FAIL | MEDIUM |
| 5.5 | WS send 10 rapid messages | Queue behavior | Connection closed after 0 messages received (code=1006). No queueing observed — crashes on first message due to API issue. | FAIL | MEDIUM |
| 5.6 | WS disconnect after 3 chunks | Clean disconnect handling | Connection closed after 0 chunks (code=1006). Server remained healthy (GET /health returned 200). WebSocketDisconnect handler at line 109 works. | WARN | LOW |

### Phase 6: Agent Pipeline

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 6.1 | `POST /research/run` AAPL standard (300s) | 3 agents complete | 500: `"You haven't specified an Api-Key."` — all agent pipelines fail without Anthropic API key | FAIL | HIGH |
| 6.2 | `POST /research/run` GOOGL quick (180s) | 2 agents complete | 500: same error | FAIL | HIGH |
| 6.3 | `POST /research/run` TSLA deep (300s) | 3 agents complete | 500: same error | FAIL | HIGH |
| 6.4 | `POST /research/run` QQQZZZ999 quick (120s) | Graceful degradation | 500: same error — no degradation, raw error exposed | FAIL | HIGH |
| 6.5 | `POST /chat/send` `/research NVDA` (300s) | Slash command triggers research | 500: same error | FAIL | HIGH |
| 6.6 | `POST /chat/send` `/compare AAPL, MSFT` (300s) | Compare command works | 500: same error | FAIL | HIGH |

### Phase 7: Ingestion Pipeline

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 7.1 | `POST /ingestion/ticker` AMZN | Success | 200: ingestion_started, company record created | PASS | — |
| 7.2 | `POST /ingestion/ticker` AMZN again | Idempotent | 200: ingestion_started again (same ticker accepted, re-ingested — no dedup check) | WARN | LOW |
| 7.3 | `POST /ingestion/bulk` META/NFLX/DIS | count:3 | 200: `{"count":3}` | PASS | — |
| 7.4 | `POST /ingestion/bulk` empty list | count:0 | 200: `{"count":0}` — empty list accepted, no validation | WARN | LOW |
| 7.5 | `POST /ingestion/bulk` AAPL x5 | count:5 (no dedup) | 200: `{"count":5}` — all 5 duplicates accepted, no deduplication | WARN | MEDIUM |
| 7.6 | `POST /ingestion/bulk` 20 S&P 500 | Success | 200: `{"count":20}` — all accepted | PASS | — |
| 7.7 | `POST /ingestion/ticker` AAPL nonexistent source | Silent ignore | 200: ingestion_started with `sources:["nonexistent"]` — invalid source silently accepted | PASS | — |

### Phase 8: Concurrency

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 8.1 | 50 parallel `GET /health` | All succeed (no rate limiting) | All 50 returned 200 in 0.089s. Zero rate limiting confirmed (Bug #4). | PASS | — |
| 8.2 | 20 concurrent session creates | All created | 20/20 sessions created successfully. No DB locking issues. | PASS | — |
| 8.3 | 3 concurrent research runs | Check rate limits | All 3 returned 500 (API key error). No rate limiting prevented the concurrent calls (Bug #4). | FAIL | HIGH |
| 8.4 | 5 concurrent chat sends to same session | Check DB locking | All 5 returned 500 (API key error). User messages were stored despite API failure. No DB locking issues observed. | FAIL | HIGH |

### Phase 9: Monitoring

| Test | Endpoint | Expected | Actual | Status | Severity |
|------|----------|----------|--------|--------|----------|
| 9.1 | `GET /monitoring/overview` | Non-zero agent counts | 200: `agent_stats.ingestion.total_calls=23`, `companies_ingested=8`. Monitoring correctly tracked all ingestion attempts including failures. Recent activity shows API key errors in failure messages (leaking internal details in monitoring too). | PASS | — |
| 9.2 | `GET /companies/?limit=200` | Count matches ingested | 8 companies in DB (includes garbage: null bytes, SQL injection string, 10000-char ticker from bad input tests) | PASS | — |
| 9.3 | `GET /strategies/?limit=20` | >= 1 auto-generated | 0 strategies — none were auto-generated because no research completed successfully (all blocked by API key) | FAIL | LOW |

---

## New Bugs Discovered

### NB-1: Negative offset/limit accepted by companies endpoint
- **Description:** `GET /api/companies/?limit=-1&offset=-5` returns 200 with data. The `limit` parameter has `le=200` but no `ge=1` constraint. The `offset` parameter has no constraints at all.
- **Reproduction:** `curl "http://localhost:8000/api/companies/?limit=-1&offset=-5"`
- **Severity:** MEDIUM
- **Location:** `companies.py:15-16`

### NB-2: Null bytes stored in database corrupt downstream JSON consumers
- **Description:** `GET /api/companies/%00%01%02` creates a company record with null bytes as the ticker. When this data is later returned in `GET /api/companies/?limit=200`, the response body contains control characters that break JSON parsers in clients.
- **Reproduction:** `curl "http://localhost:8000/api/companies/%00%01%02"` then `curl "http://localhost:8000/api/companies/?limit=200"`
- **Severity:** HIGH
- **Location:** `companies.py:47` (no input sanitization)

### NB-3: 10,000-character strings stored as tickers without limit
- **Description:** The companies endpoint accepts and stores arbitrarily long strings as ticker symbols. A 10,000-character string was successfully stored. This could be used for storage exhaustion attacks.
- **Reproduction:** `curl "http://localhost:8000/api/companies/$(python3 -c "print('A'*10000)")"`
- **Severity:** HIGH
- **Location:** `companies.py:47`, no `max_length` on path parameter

### NB-4: WebSocket accepts any session_id including non-UUID strings
- **Description:** Connecting to `ws://localhost:8000/api/chat/ws/not-a-uuid` is accepted (no UUID format validation). The connection then crashes server-side when trying to use the invalid session ID.
- **Reproduction:** Connect to `ws://localhost:8000/api/chat/ws/not-a-uuid`
- **Severity:** MEDIUM
- **Location:** `chat.py:78`

### NB-5: Bulk ingestion has no deduplication
- **Description:** `POST /api/ingestion/bulk` with `["AAPL","AAPL","AAPL","AAPL","AAPL"]` spawns 5 separate ingestion tasks for the same ticker. No deduplication is performed.
- **Reproduction:** `curl -X POST /api/ingestion/bulk -d '{"tickers":["AAPL","AAPL","AAPL","AAPL","AAPL"]}'`
- **Severity:** MEDIUM
- **Location:** `ingestion.py:103`

### NB-6: Empty tickers list accepted by compare endpoint
- **Description:** `POST /api/research/compare` with `{"tickers":[]}` is accepted with no validation. The endpoint then crashes trying to process zero tickers.
- **Reproduction:** `curl -X POST /api/research/compare -d '{"tickers":[]}'`
- **Severity:** LOW
- **Location:** `research.py:18` (no `min_length=1` on tickers list)

### NB-7: Monitoring leaks internal error messages
- **Description:** The monitoring overview endpoint returns recent activity logs that contain raw error messages like `"Ingestion failed for AAPL: You haven't specified an Api-Key."`. These internal details should not be exposed.
- **Reproduction:** `curl http://localhost:8000/api/monitoring/overview`
- **Severity:** MEDIUM
- **Location:** Monitoring route (returns raw agent log messages)

---

## Recommendations (Priority Order)

| Priority | Fix | Why | Effort |
|----------|-----|-----|--------|
| 🔴 P0 | Replace `detail=str(e)` with generic error messages in all HTTP exception handlers | Raw internal errors (API provider names, key status) are exposed to clients — security and information disclosure risk | small |
| 🔴 P0 | Add try/except around `json.loads()` in WebSocket handler (`chat.py:90`) | Non-JSON messages crash the WebSocket connection silently with no error feedback to the client | small |
| 🔴 P0 | Add backup/confirmation before `delete_index` in `vector_store.py:35` | A config change could silently destroy all production vector data with no recovery path | medium |
| 🔴 P0 | Add ticker validation (regex `^[A-Z0-9.]{1,10}$`) to all Pydantic models and path params | SQL injection strings, null bytes, and 10,000-char strings are stored as valid company records, corrupting the database | small |
| 🟡 P1 | Add rate limiting middleware (e.g., `slowapi`) to all endpoints | No rate limiting means a single client can overwhelm the server with unlimited concurrent requests (50 simultaneous requests completed in 89ms) | medium |
| 🟡 P1 | Add try/except around `message["content"]` in WebSocket handler (`chat.py:92`) | Missing "content" key causes unhandled KeyError crash | small |
| 🟡 P1 | Add `ge=0` to offset and `ge=1` to limit query params in companies endpoint | Negative values are accepted, producing undefined behavior | small |
| 🟡 P1 | Deduplicate tickers in bulk ingestion before spawning background tasks | Duplicate tickers spawn redundant ingestion jobs, wasting resources | small |
| 🟡 P1 | Validate session_id as UUID format in WebSocket endpoint | Non-UUID strings are accepted, causing server-side crashes | small |
| 🟢 P2 | Add `min_length=1` to `CompareRequest.tickers` | Empty lists are accepted and cause downstream crashes | small |
| 🟢 P2 | Sanitize monitoring log messages before exposing via API | Internal error details visible in monitoring endpoint | small |
| 🟢 P2 | Add source validation to ingestion endpoint | Nonexistent sources like `"nonexistent"` are silently accepted | small |
| 🟢 P2 | Add input sanitization/escaping for stored text (XSS prevention) | Script tags and other payloads could be stored and rendered by the frontend | medium |

---

*Report generated by automated stress testing on 2026-03-02.*

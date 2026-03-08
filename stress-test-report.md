# Stress Test Report

**2026-03-02** — Dhruv Jhamb
**Setup:** localhost:8000, SQLite, no API keys configured
**Scope:** 61 tests — all endpoints, WebSocket, agents, ingestion, concurrency

---

## 4 Bugs That Actually Break Things

### 1. WebSocket handler has no error handling — chat crashes on any bad input

`chat.py:90` — `json.loads(data)` is bare. No try/except. Send anything that isn't perfect JSON and the connection drops silently. Same issue at `:92` — `data["content"]` is a bare dict access, so a missing key is also a silent crash.

**Repro:**
```bash
# non-JSON — silent crash
wscat -c ws://localhost:8000/api/chat/ws/$(uuidgen) -x "hello"

# wrong key — silent crash
wscat -c ws://localhost:8000/api/chat/ws/$(uuidgen) -x '{"text":"hello"}'
```

**Fix:** Wrap the whole message handler in try/except, use `.get()` for key access.

---

### 2. `vector_store.py:32-35` — Pinecone index gets nuked on dimension mismatch

If the embedding dimension doesn't match the existing index, `self.pc.delete_index(self.index_name)` runs automatically. Deletes every vector, every namespace, all ingested filing data. No backup, no prompt, no log warning.

**Repro:** Change `EMBEDDING_DIM` from 384 to anything else, restart the server.

**Fix:** Raise an error instead of auto-deleting. Or at minimum, log a giant warning and require an env var like `ALLOW_INDEX_RESET=true` to proceed.

---

### 3. Null bytes in input corrupt the database

`companies.py:47` accepts any string as a ticker. Sending `\x00\x01\x02` creates a company record that breaks JSON serialization on every subsequent API response that includes it. One bad record poisons the whole companies endpoint.

**Repro:**
```bash
curl -X POST localhost:8000/api/companies/ \
  -H "Content-Type: application/json" \
  -d '{"ticker":"\u0000\u0001\u0002"}'
```

**Fix:** Reject non-printable chars at the route level. A simple `if not ticker.isascii() or not ticker.isprintable()` check.

---

### 4. Agents crash entirely if Pinecone connection fails

`sector_researcher.py:31` and `fundamental_analyst.py:74` — search tool constructors assume Pinecone is reachable. If the connection itself fails (bad key, network issue), the entire agent crashes. The "graceful degradation" pattern only handles query-level failures, not connection-level ones.

**Repro:** Set `PINECONE_API_KEY=garbage`, then run any research endpoint.

**Fix:** Wrap search tool init in try/except. If it fails, set `self.search_tools = None` and skip vector search in the agent loop.

---

## What Passed

Everything that doesn't touch the WebSocket or external services works fine:
- Server startup, health check (0.5ms)
- Session CRUD, company listing, ingestion, monitoring
- 50 concurrent health checks handled in 89ms, 20 concurrent session creates with no DB locking
- Ingestion pipeline works end-to-end
- Graceful disconnect handling on WebSocket (server stays up)

---

## Not Bugs, Just Not Built Yet

These showed up in testing but they're clearly unimplemented features, not broken code:

- No ticker validation (no length limit, no character filter, no real-ticker check)
- No rate limiting on any endpoint
- No bulk ingestion deduplication
- No input bounds on pagination params (`limit=-1` works)
- `detail=str(e)` leaks raw exceptions (production hardening, not a dev blocker)
- Monitoring shows raw error strings (same — production concern)

---

*61 tests, 4 real bugs, rest is expected for current stage.*

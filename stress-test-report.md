# Stress Test Report

**2026-03-02** — Dhruv Jhamb (Claude Code)
**Setup:** localhost:8000, SQLite, no API keys configured
**Scope:** 61 tests — all endpoints, WebSocket, agents, ingestion, concurrency

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

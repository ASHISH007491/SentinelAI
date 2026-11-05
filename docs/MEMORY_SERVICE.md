# SentinelAI — AI Memory Service (Phase 2, Prompt 017)

Persistent, session-isolated memory for agents and workflows. PostgreSQL-backed
(any SQLAlchemy engine), with short/long-term memory, conversation / project /
execution history, retrieval, and context compression. No agent logic — summarisation
is delegated to an injectable callable. Lives at `backend/app/ai/memory/`.

## Storage

A single table `memory_records` (`app/models/memory.py`, Alembic migration
`fbd467ed2f97`):

| Column | Purpose |
|--------|---------|
| `session_id` | **session isolation** — every read is scoped to it (indexed) |
| `user_id` / `project_id` | optional ownership; project history spans sessions |
| `scope` | `short_term` / `long_term` / `conversation` / `project` / `execution` |
| `role` | conversation role (user/assistant/system) |
| `content` | JSON payload (`{"text": ...}` or arbitrary dict) |
| `importance` | float ranking hint |
| `is_summary` | marks compressed summary records |
| `expires_at` | short-term TTL (recall excludes expired by default) |

## MemoryService

Constructed with a SQLAlchemy session factory (DI) and an optional summariser:

```python
from sqlalchemy.orm import sessionmaker
from app.ai.memory import MemoryService
from app.db.session import get_engine

service = MemoryService(sessionmaker(bind=get_engine()))
```

| Capability | Method |
|------------|--------|
| Write memory | `remember(session_id, content, scope=, role=, key=, importance=, ttl_s=, user_id=, project_id=)` |
| Conversation history | `add_message(session_id, role, content)`, `conversation(session_id)` |
| Execution history | `execution_history(session_id)` |
| Project history (cross-session) | `project_history(project_id)` |
| Retrieval | `recall(session_id, scope=, limit=, include_expired=, newest_first=)` |
| Search | `search(session_id, query)` |
| Short-term TTL | `ttl_s=` on `remember`; `purge_expired(session_id)` |
| Context compression | `compress(session_id, scope=, keep_last=)` → `Summary` |
| Forget | `forget_session(session_id)` |

### Short-term vs long-term

Short-term memories carry a TTL (`ttl_s`) and are excluded from `recall` once
expired (until `purge_expired`). Long-term memories are durable. Both live in the
same table, distinguished by `scope`.

### Context compression / summarisation

`compress()` takes the older memories of a scope (keeping the most recent
`keep_last`), runs them through the summariser, writes a single `LONG_TERM` summary
record (`is_summary=True`), and deletes the compressed ones — bounding context size
over long sessions. The summariser is injectable:

```python
# default: deterministic concat+truncate (no dependencies)
# production: back it with the LLM service
service = MemoryService(factory, summarizer=lambda texts: llm.complete("\n".join(texts)).text)
```

## Tests

`backend/tests/ai/test_memory_service.py` — 11 tests (SQLite, same SQLAlchemy code
path as Postgres): persistence + scopes, dict round-trip, **session isolation**,
conversation/execution/project history, search, **short-term TTL expiry + purge**,
**compression** (default + injected summariser + nothing-to-compress), and forget.

```
cd backend && pytest tests/ai/test_memory_service.py -q
```

## Notes

- Tests run on SQLite; production uses PostgreSQL via the same models/migration.
- `search` is substring-based for now; swap for full-text or pgvector embeddings later.
- Not yet wired into the running pipeline (tracked); the service is standalone and
  injected wherever memory is needed.

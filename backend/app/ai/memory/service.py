"""MemoryService: persistent, session-isolated memory with retrieval + compression.

Backed by PostgreSQL (any SQLAlchemy engine) via an injected session factory.
Supports short-term (TTL) and long-term (durable) memory, conversation / project /
execution history, retrieval/search, and context compression (summarisation of old
short-term memories into a single long-term summary). Summarisation is delegated to
an injectable callable, so the service has no agent/LLM logic of its own.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.core.logging import get_logger
from app.ai.memory.models import MemoryItem, Summary
from app.models.memory import MemoryRecord, MemoryScope

logger = get_logger(__name__)

SessionFactory = Callable[[], Session]
Summarizer = Callable[[list[str]], str]


def default_summarizer(texts: list[str]) -> str:
    """Deterministic, dependency-free summariser (concatenate + truncate).

    Swap for an LLM-backed callable (e.g. LLMService.complete) in production.
    """
    joined = " ".join(t.strip() for t in texts if t.strip())
    return (joined[:497] + "...") if len(joined) > 500 else joined


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_item(record: MemoryRecord) -> MemoryItem:
    return MemoryItem(
        id=record.id,
        session_id=record.session_id,
        scope=record.scope,
        role=record.role,
        key=record.mem_key,
        content=record.content or {},
        importance=record.importance,
        is_summary=record.is_summary,
        created_at=record.created_at,
        expires_at=record.expires_at,
    )


class MemoryService:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        summarizer: Summarizer | None = None,
        short_term_cap: int = 0,
    ) -> None:
        self._session_factory = session_factory
        self._summarize = summarizer or default_summarizer
        # When > 0, remember() auto-compresses short-term once it exceeds this many
        # records, keeping the most recent half. 0 disables auto-compression.
        self._short_term_cap = short_term_cap

    # -- session helper ------------------------------------------------------
    def _run(self, fn):
        session = self._session_factory()
        try:
            result = fn(session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # -- writing -------------------------------------------------------------
    def remember(
        self,
        session_id: str,
        content: dict | str,
        *,
        scope: MemoryScope = MemoryScope.SHORT_TERM,
        role: str | None = None,
        key: str | None = None,
        importance: float = 0.0,
        ttl_s: float | None = None,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> MemoryItem:
        payload = {"text": content} if isinstance(content, str) else dict(content)
        expires = _now() + timedelta(seconds=ttl_s) if ttl_s else None

        def _op(session: Session) -> MemoryItem:
            record = MemoryRecord(
                session_id=session_id, user_id=user_id, project_id=project_id,
                scope=scope, role=role, mem_key=key, content=payload,
                importance=importance, expires_at=expires,
            )
            session.add(record)
            session.flush()
            return _to_item(record)

        item = self._run(_op)
        if self._short_term_cap and scope is MemoryScope.SHORT_TERM:
            self._maybe_auto_compress(session_id)
        return item

    def add_message(self, session_id: str, role: str, content: str, **kw) -> MemoryItem:
        """Convenience for conversation history."""
        return self.remember(session_id, content, scope=MemoryScope.CONVERSATION, role=role, **kw)

    # -- reading -------------------------------------------------------------
    def recall(
        self,
        session_id: str,
        *,
        scope: MemoryScope | None = None,
        limit: int = 50,
        include_expired: bool = False,
        newest_first: bool = False,
    ) -> list[MemoryItem]:
        def _op(session: Session) -> list[MemoryItem]:
            stmt = select(MemoryRecord).where(MemoryRecord.session_id == session_id)
            if scope is not None:
                stmt = stmt.where(MemoryRecord.scope == scope)
            if not include_expired:
                stmt = stmt.where(
                    or_(MemoryRecord.expires_at.is_(None), MemoryRecord.expires_at > _now())
                )
            order = MemoryRecord.id.desc() if newest_first else MemoryRecord.id.asc()
            rows = session.scalars(stmt.order_by(order).limit(limit)).all()
            return [_to_item(r) for r in rows]

        return self._run(_op)

    def conversation(self, session_id: str, *, limit: int = 50) -> list[MemoryItem]:
        return self.recall(session_id, scope=MemoryScope.CONVERSATION, limit=limit)

    def execution_history(self, session_id: str, *, limit: int = 50) -> list[MemoryItem]:
        return self.recall(session_id, scope=MemoryScope.EXECUTION, limit=limit)

    def project_history(self, project_id: int, *, limit: int = 100) -> list[MemoryItem]:
        """Project history spans sessions — scoped by project_id, not session_id."""
        def _op(session: Session) -> list[MemoryItem]:
            stmt = (
                select(MemoryRecord)
                .where(MemoryRecord.project_id == project_id)
                .where(MemoryRecord.scope == MemoryScope.PROJECT)
                .order_by(MemoryRecord.id.asc())
                .limit(limit)
            )
            return [_to_item(r) for r in session.scalars(stmt).all()]

        return self._run(_op)

    def search(self, session_id: str, query: str, *, limit: int = 20) -> list[MemoryItem]:
        """Naive substring retrieval over stored text."""

        def _op(session: Session) -> list[MemoryItem]:
            stmt = (
                select(MemoryRecord)
                .where(MemoryRecord.session_id == session_id)
                .order_by(MemoryRecord.id.asc())
            )
            rows = session.scalars(stmt).all()
            hits = [r for r in rows if query.lower() in str(r.content).lower()]
            return [_to_item(r) for r in hits[:limit]]

        return self._run(_op)

    # -- maintenance ---------------------------------------------------------
    def purge_expired(self, session_id: str | None = None) -> int:
        def _op(session: Session) -> int:
            stmt = select(MemoryRecord).where(
                MemoryRecord.expires_at.is_not(None), MemoryRecord.expires_at <= _now()
            )
            if session_id is not None:
                stmt = stmt.where(MemoryRecord.session_id == session_id)
            rows = session.scalars(stmt).all()
            for r in rows:
                session.delete(r)
            return len(rows)

        return self._run(_op)

    def forget_session(self, session_id: str) -> int:
        def _op(session: Session) -> int:
            rows = session.scalars(
                select(MemoryRecord).where(MemoryRecord.session_id == session_id)
            ).all()
            for r in rows:
                session.delete(r)
            return len(rows)

        return self._run(_op)

    def recall_important(
        self, session_id: str, *, scope: MemoryScope | None = None, limit: int = 10
    ) -> list[MemoryItem]:
        """Retrieve the highest-importance (then most recent) non-expired memories."""
        items = self.recall(session_id, scope=scope, limit=10_000)
        items.sort(key=lambda i: (i.importance, i.id or 0), reverse=True)
        return items[:limit]

    def _maybe_auto_compress(self, session_id: str) -> None:
        active = self.recall(session_id, scope=MemoryScope.SHORT_TERM, limit=10_000)
        if len(active) > self._short_term_cap:
            # Keep the most recent half; compress the rest (importance-aware).
            self.compress(session_id, scope=MemoryScope.SHORT_TERM,
                          keep_last=max(1, self._short_term_cap // 2))

    # -- context compression -------------------------------------------------
    def compress(
        self,
        session_id: str,
        *,
        scope: MemoryScope = MemoryScope.SHORT_TERM,
        keep_last: int = 0,
    ) -> Summary | None:
        """Summarise older `scope` memories into one LONG_TERM summary record.

        The summarised records are deleted (compressed); the most recent `keep_last`
        are retained. Returns the Summary, or None if there was nothing to compress.
        """
        def _op(session: Session) -> Summary | None:
            rows = session.scalars(
                select(MemoryRecord)
                .where(MemoryRecord.session_id == session_id, MemoryRecord.scope == scope)
                .order_by(MemoryRecord.id.asc())
            ).all()
            recent = set(r.id for r in (rows[-keep_last:] if keep_last > 0 else []))
            # Preserve high-importance memories from compression (importance >= 0.8).
            to_compress = [r for r in rows if r.id not in recent and r.importance < 0.8]
            if len(to_compress) < 1:
                return None

            texts = self._texts(to_compress)
            summary_text = self._summarize(texts)
            session.add(MemoryRecord(
                session_id=session_id, scope=MemoryScope.LONG_TERM,
                content={"text": summary_text}, is_summary=True,
                mem_key=f"summary:{scope.value}",
            ))
            for r in to_compress:
                session.delete(r)
            logger.info(
                "compressed session=%s scope=%s count=%d",
                session_id, scope.value, len(to_compress),
            )
            return Summary(session_id=session_id, scope=scope, text=summary_text,
                           compressed_count=len(to_compress))

        return self._run(_op)

    @staticmethod
    def _texts(records: Iterable[MemoryRecord]) -> list[str]:
        out = []
        for r in records:
            text = (r.content or {}).get("text", "")
            out.append(f"{r.role}: {text}" if r.role else str(text))
        return out

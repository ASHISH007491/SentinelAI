"""Tests for the AI Memory Service (SQLite-backed; same SQLAlchemy code as Postgres)."""
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (register all models incl. MemoryRecord)
from app.ai.memory import MemoryService, Summary
from app.db.session import Base
from app.models.memory import MemoryScope


@pytest.fixture()
def service():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return MemoryService(factory)


# --- persistence + scopes ---
def test_remember_and_recall_persists(service):
    item = service.remember("s1", "hello", scope=MemoryScope.LONG_TERM, importance=0.8)
    assert item.id > 0 and item.text == "hello"
    recalled = service.recall("s1", scope=MemoryScope.LONG_TERM)
    assert len(recalled) == 1 and recalled[0].text == "hello"
    assert recalled[0].importance == 0.8


def test_dict_content_round_trips(service):
    service.remember("s1", {"finding": "RCE", "cvss": 9.8}, scope=MemoryScope.EXECUTION)
    items = service.execution_history("s1")
    assert items[0].content == {"finding": "RCE", "cvss": 9.8}


# --- session isolation ---
def test_session_isolation(service):
    service.remember("s1", "secret-a", scope=MemoryScope.LONG_TERM)
    service.remember("s2", "secret-b", scope=MemoryScope.LONG_TERM)
    assert [i.text for i in service.recall("s1")] == ["secret-a"]
    assert [i.text for i in service.recall("s2")] == ["secret-b"]


# --- conversation / execution / project history ---
def test_conversation_history(service):
    service.add_message("s1", "user", "hi")
    service.add_message("s1", "assistant", "hello back")
    conv = service.conversation("s1")
    assert [(m.role, m.text) for m in conv] == [("user", "hi"), ("assistant", "hello back")]


def test_project_history_spans_sessions(service):
    service.remember("s1", "p-event-1", scope=MemoryScope.PROJECT, project_id=7)
    service.remember("s2", "p-event-2", scope=MemoryScope.PROJECT, project_id=7)
    service.remember("s3", "other", scope=MemoryScope.PROJECT, project_id=9)
    hist = service.project_history(7)
    assert [i.text for i in hist] == ["p-event-1", "p-event-2"]


# --- retrieval / search ---
def test_search(service):
    service.remember("s1", "SQL injection in /search", scope=MemoryScope.LONG_TERM)
    service.remember("s1", "TLS misconfiguration", scope=MemoryScope.LONG_TERM)
    hits = service.search("s1", "injection")
    assert len(hits) == 1 and "injection" in hits[0].text


# --- short-term TTL ---
def test_short_term_ttl_expiry(service):
    service.remember("s1", "ephemeral", scope=MemoryScope.SHORT_TERM, ttl_s=0.05)
    assert len(service.recall("s1", scope=MemoryScope.SHORT_TERM)) == 1
    time.sleep(0.06)
    assert service.recall("s1", scope=MemoryScope.SHORT_TERM) == []          # excluded
    assert len(service.recall("s1", scope=MemoryScope.SHORT_TERM, include_expired=True)) == 1
    assert service.purge_expired("s1") == 1
    assert service.recall("s1", scope=MemoryScope.SHORT_TERM, include_expired=True) == []


# --- context compression / summarization ---
def test_compress_summarizes_and_replaces(service):
    for i in range(5):
        service.remember("s1", f"event {i}", scope=MemoryScope.SHORT_TERM)
    summary = service.compress("s1", scope=MemoryScope.SHORT_TERM, keep_last=2)
    assert isinstance(summary, Summary)
    assert summary.compressed_count == 3
    # the 3 oldest short-term are gone, 2 remain
    assert len(service.recall("s1", scope=MemoryScope.SHORT_TERM)) == 2
    # a long-term summary record now exists
    longterm = service.recall("s1", scope=MemoryScope.LONG_TERM)
    assert len(longterm) == 1 and longterm[0].is_summary
    assert "event 0" in longterm[0].text


def test_compress_with_injected_summarizer():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    svc = MemoryService(factory, summarizer=lambda texts: f"SUMMARY[{len(texts)}]")
    svc.remember("s1", "a", scope=MemoryScope.SHORT_TERM)
    svc.remember("s1", "b", scope=MemoryScope.SHORT_TERM)
    summary = svc.compress("s1")
    assert summary.text == "SUMMARY[2]"


def test_compress_nothing_returns_none(service):
    assert service.compress("empty-session") is None


# --- forget ---
def test_forget_session(service):
    service.remember("s1", "x")
    service.remember("s1", "y")
    assert service.forget_session("s1") == 2
    assert service.recall("s1", include_expired=True) == []


# --- importance-aware retrieval + compression ---
def test_recall_important_ranks_by_importance(service):
    service.remember("s1", "low", scope=MemoryScope.LONG_TERM, importance=0.1)
    service.remember("s1", "high", scope=MemoryScope.LONG_TERM, importance=0.9)
    service.remember("s1", "mid", scope=MemoryScope.LONG_TERM, importance=0.5)
    top = service.recall_important("s1", limit=2)
    assert [i.text for i in top] == ["high", "mid"]


def test_compress_preserves_high_importance(service):
    service.remember("s1", "trivial-1", scope=MemoryScope.SHORT_TERM, importance=0.0)
    service.remember("s1", "critical", scope=MemoryScope.SHORT_TERM, importance=0.95)
    service.remember("s1", "trivial-2", scope=MemoryScope.SHORT_TERM, importance=0.0)
    summary = service.compress("s1", scope=MemoryScope.SHORT_TERM)
    assert summary.compressed_count == 2          # only the two trivial ones
    remaining = service.recall("s1", scope=MemoryScope.SHORT_TERM)
    assert [i.text for i in remaining] == ["critical"]   # high-importance preserved


def test_auto_compression_when_cap_exceeded():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.session import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    svc = MemoryService(sessionmaker(bind=engine), short_term_cap=4)
    for i in range(6):
        svc.remember("s1", f"e{i}", scope=MemoryScope.SHORT_TERM)
    # auto-compression kept short-term bounded and produced a long-term summary
    short = svc.recall("s1", scope=MemoryScope.SHORT_TERM)
    assert len(short) <= 4
    summaries = [i for i in svc.recall("s1", scope=MemoryScope.LONG_TERM) if i.is_summary]
    assert len(summaries) >= 1

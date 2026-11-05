"""Run execution service: drives the real agent pipeline over uploaded artefacts.

Reads artefact bytes from storage, threads findings through detection ->
prioritisation -> advisor -> report (or the single-agent baseline), and persists
each agent's structured output plus per-agent token/latency tracing for the eval.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.base import AgentContext
from app.agents.registry import pipeline_for
from app.ai.guardrail import PromptGuard
from app.core.llm_client import LLMClient
from app.models.agent_output import AgentOutput
from app.models.run import Run, RunStatus

_MAX_ARTEFACT_CHARS = 200_000


def _read_artefacts(run: Run) -> tuple[str, list[str]]:
    """Concatenate readable artefact text (best-effort) and collect filenames."""
    chunks: list[str] = []
    names: list[str] = []
    for art in run.artefacts:
        names.append(art.filename)
        try:
            data = Path(art.storage_path).read_bytes()
            chunks.append(data.decode("utf-8", errors="replace"))
        except OSError:
            continue
    return ("\n".join(chunks)[:_MAX_ARTEFACT_CHARS], names)


def execute_run(db: Session, run: Run, llm: LLMClient | None = None) -> Run:
    llm = llm or LLMClient()
    run.status = RunStatus.RUNNING
    db.add(run)
    db.commit()

    try:
        text, names = _read_artefacts(run)
        # Every artefact is attacker-controlled content (phishing bodies, uploaded code,
        # scan output) -- strip injected directives before any agent ever sees it. Same
        # PromptGuard.sanitise() call validated in eval's Track D (60%->12% ASR on email,
        # 100%->0% on code); this is what makes that defence real instead of eval-only.
        clean_text = PromptGuard().sanitise(text).clean_text
        ctx = AgentContext(
            workflow=run.workflow.value,
            artefact_text=clean_text,
            artefact_names=names,
            llm=llm,
        )
        agents = pipeline_for(run.workflow.value)

        for agent in agents:
            started = time.perf_counter()
            result = agent.run(ctx)
            latency_ms = (time.perf_counter() - started) * 1000

            db.add(AgentOutput(
                run_id=run.id,
                agent_name=agent.name,
                output={
                    "agent": result.agent,
                    "summary": result.summary,
                    "findings": [f.model_dump() for f in result.findings],
                    "data": result.data,
                },
                prompt_tokens=ctx.usage.prompt_tokens,
                completion_tokens=ctx.usage.completion_tokens,
                latency_ms=latency_ms,
            ))

        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
    except Exception:
        run.status = RunStatus.FAILED
        db.add(run)
        db.commit()
        raise

    db.add(run)
    db.commit()
    db.refresh(run)
    return run

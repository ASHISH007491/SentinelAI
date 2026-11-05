"""Advisor agent: turn prioritised findings into executive recommendations.

Uses the LLM for narrative when available; otherwise derives a concise,
template-based summary from the top findings so it always returns something useful.
"""
from __future__ import annotations

import logging

from app.agents.base import Agent, AgentContext
from app.agents.schemas import AgentResult

logger = logging.getLogger("sentinelai.agent.advisor")


class AdvisorAgent(Agent):
    name = "advisor"

    def run(self, ctx: AgentContext) -> AgentResult:
        findings = ctx.findings
        if not findings:
            return AgentResult(agent=self.name, summary="No issues detected — posture looks clean.")

        top = findings[: min(5, len(findings))]
        criticals = sum(1 for f in findings if f.severity in ("critical", "high"))

        if ctx.llm.available:
            bullet = "\n".join(f"- [{f.severity}] {f.title} (CVSS {f.cvss})" for f in top)
            prompt = (
                "You are a CISO advisor. Given these prioritised findings, write a 3-sentence "
                "executive summary and the single most important next action.\n\n" + bullet
            )
            try:
                resp = ctx.llm.complete(prompt, max_tokens=400)
                ctx.record_usage(resp.usage)
                if resp.text.strip():
                    return AgentResult(agent=self.name, summary=resp.text.strip(),
                                       data={"priority_actions": [f.recommendation for f in top]})
            except Exception:
                logger.warning(
                    "advisor LLM summary failed; using template fallback", exc_info=True
                )  # fall through to template

        summary = (
            f"{len(findings)} finding(s) identified, {criticals} at high or critical severity. "
            f"Address \"{top[0].title}\" first: {top[0].recommendation}"
        )
        return AgentResult(agent=self.name, summary=summary,
                           data={"priority_actions": [f.recommendation for f in top]})

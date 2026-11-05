"""Reporting / output layer: consolidate agent findings into one analyst report.

The fifth SentinelAI component. It turns the specialist agents' structured outputs into
a single SecurityReport (structured + rendered), and is where the *advisory* value
lives: grounded, rule-based remediation recommendations derived from the findings
(not free-text LLM advice), which keeps the output defensible and testable.
"""
from app.ai.reporting.builder import ReportBuilder
from app.ai.reporting.models import Finding, SecurityReport, Severity

__all__ = ["Finding", "ReportBuilder", "SecurityReport", "Severity"]

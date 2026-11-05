"""Concrete SentinelAI specialist agents, built on BaseAgent.

These are the real domain agents the platform coordinates: vulnerability
prioritisation (a two-step risk-signal -> ranking decomposition), phishing investigation
(a two-step extract -> verdict decomposition), and secure-code review (a two-step
pattern-scan -> confirm+fix decomposition). Each returns strict JSON and inherits
BaseAgent's timeout/retry/metrics. No engine logic here — only the per-task prompting
+ parsing.
"""
from app.ai.agents.specialists.code_review import CodeReviewAgent
from app.ai.agents.specialists.indicator_extraction import IndicatorExtractionAgent
from app.ai.agents.specialists.pattern_scan import PatternScanAgent
from app.ai.agents.specialists.phishing_verdict import PhishingVerdictAgent
from app.ai.agents.specialists.prioritisation import PrioritisationAgent
from app.ai.agents.specialists.risk_signal import RiskSignalAgent

__all__ = [
    "CodeReviewAgent",
    "IndicatorExtractionAgent",
    "PatternScanAgent",
    "PhishingVerdictAgent",
    "PrioritisationAgent",
    "RiskSignalAgent",
]

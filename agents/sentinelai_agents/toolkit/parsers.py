"""Shared parsers (SBOM/CVE feeds, email headers, source files).

Used by BOTH architectures so the comparison isolates orchestration, not tooling.
"""
from __future__ import annotations


def parse_cve_feed(raw: str) -> list[dict]:
    raise NotImplementedError

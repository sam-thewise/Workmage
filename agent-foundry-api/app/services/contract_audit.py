"""Deterministic + LLM-assisted contract audit helpers."""
from __future__ import annotations

from typing import Any


def run_static_audit_checks(source_payload: dict[str, Any]) -> dict[str, Any]:
    """Perform deterministic checks on verified source."""
    source = str(source_payload.get("source_code") or "")
    findings: list[dict[str, Any]] = []
    lowered = source.lower()

    if not source_payload.get("verified"):
        findings.append({"severity": "high", "code": "unverified_contract", "message": "Contract source is unverified"})
    if "delegatecall(" in lowered:
        findings.append({"severity": "medium", "code": "delegatecall_usage", "message": "delegatecall usage detected"})
    if "tx.origin" in lowered:
        findings.append({"severity": "high", "code": "tx_origin_auth", "message": "tx.origin authorization pattern detected"})
    if "selfdestruct(" in lowered:
        findings.append({"severity": "high", "code": "selfdestruct_usage", "message": "selfdestruct usage detected"})

    risk_score = 0
    for f in findings:
        risk_score += {"low": 10, "medium": 25, "high": 50}.get(f["severity"], 0)
    return {
        "findings": findings,
        "risk_score": min(100, risk_score),
        "status": "blocked" if any(f["severity"] == "high" for f in findings) else "review",
    }

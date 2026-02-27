"""ERC-8004 trust signal normalization."""
from __future__ import annotations

from typing import Any


def compute_trust_tier(trust_score: int) -> str:
    """Map trust score to policy tier."""
    if trust_score >= 80:
        return "high"
    if trust_score >= 50:
        return "medium"
    if trust_score > 0:
        return "low"
    return "unknown"


def normalize_trust_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize incoming ERC-8004-aligned refs and score."""
    score = int(payload.get("trust_score") or 0)
    return {
        "identity_registry_ref": payload.get("identity_registry_ref"),
        "reputation_registry_ref": payload.get("reputation_registry_ref"),
        "validation_registry_ref": payload.get("validation_registry_ref"),
        "trust_score": score,
        "tier": compute_trust_tier(score),
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }

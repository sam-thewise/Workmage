"""Policy and risk checks for simulated/live actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings


@dataclass
class PolicyResult:
    allowed: bool
    reason: str = ""
    details: dict[str, Any] | None = None


def evaluate_action_policy(policy: dict[str, Any], request: dict[str, Any], trust_score: int = 0) -> PolicyResult:
    """Evaluate a proposed action against policy controls."""
    if settings.ACTIONS_ENABLE_LIVE_TX is False and request.get("mode") == "live":
        return PolicyResult(False, "Live transactions are disabled")

    max_spend_wei = int(policy.get("max_spend_wei") or settings.ACTIONS_DEFAULT_MAX_SPEND_WEI)
    requested_spend_wei = int(request.get("amount_wei") or 0)
    if requested_spend_wei > max_spend_wei:
        return PolicyResult(
            False,
            "Requested spend exceeds max_spend_wei",
            {"requested_spend_wei": requested_spend_wei, "max_spend_wei": max_spend_wei},
        )

    max_gas_wei = int(policy.get("max_gas_wei") or settings.ACTIONS_DEFAULT_MAX_GAS_WEI)
    requested_gas_wei = int(request.get("max_gas_wei") or 0)
    if requested_gas_wei > max_gas_wei:
        return PolicyResult(
            False,
            "Requested gas exceeds max_gas_wei",
            {"requested_gas_wei": requested_gas_wei, "max_gas_wei": max_gas_wei},
        )

    allowed_tokens = set(policy.get("allowed_tokens") or [])
    token_in = request.get("token_in")
    token_out = request.get("token_out")
    if allowed_tokens and any(t and t not in allowed_tokens for t in (token_in, token_out)):
        return PolicyResult(False, "Token not in allowlist")

    allowed_routers = set(policy.get("allowed_routers") or [])
    router = request.get("router")
    if allowed_routers and router and router not in allowed_routers:
        return PolicyResult(False, "Router not in allowlist")

    min_trust_score = int(policy.get("min_trust_score") or settings.ACTIONS_MIN_TRUST_SCORE)
    if trust_score < min_trust_score:
        return PolicyResult(False, "Agent trust score below minimum", {"trust_score": trust_score})

    return PolicyResult(True, "allowed")

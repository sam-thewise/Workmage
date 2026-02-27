"""Basic conformance tests for action infrastructure primitives."""
from app.services.policy_engine import evaluate_action_policy
from app.services.trust_signals import compute_trust_tier


def test_policy_denies_spend_over_limit():
    result = evaluate_action_policy(
        {"max_spend_wei": 10},
        {"amount_wei": 11, "max_gas_wei": 0, "mode": "simulation"},
        trust_score=100,
    )
    assert result.allowed is False


def test_policy_allows_minimal_simulation():
    result = evaluate_action_policy(
        {"max_spend_wei": 100, "max_gas_wei": 100},
        {"amount_wei": 10, "max_gas_wei": 10, "mode": "simulation"},
        trust_score=100,
    )
    assert result.allowed is True


def test_trust_tier_mapping():
    assert compute_trust_tier(85) == "high"
    assert compute_trust_tier(55) == "medium"
    assert compute_trust_tier(5) == "low"
    assert compute_trust_tier(0) == "unknown"

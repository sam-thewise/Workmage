"""Generic action orchestration persistence helpers."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action_runtime import (
    ActionAnalysis,
    ActionDecision,
    ActionExecution,
    ActionSignal,
    AuditTrail,
    PolicyEvent,
)


async def create_signal(
    db: AsyncSession,
    source: str,
    signal_type: str,
    payload: dict[str, Any],
    network: str = "avalanche",
    dedupe_key: str | None = None,
) -> ActionSignal:
    record = ActionSignal(
        source=source,
        signal_type=signal_type,
        payload=payload,
        network=network,
        dedupe_key=dedupe_key,
    )
    db.add(record)
    await db.flush()
    return record


async def create_analysis(
    db: AsyncSession,
    analyzer: str,
    result: dict[str, Any],
    signal_id: int | None = None,
    summary: str | None = None,
    status: str = "completed",
) -> ActionAnalysis:
    record = ActionAnalysis(
        signal_id=signal_id,
        analyzer=analyzer,
        result=result,
        summary=summary,
        status=status,
    )
    db.add(record)
    await db.flush()
    return record


async def create_decision(
    db: AsyncSession,
    decider: str,
    decision: str,
    metadata: dict[str, Any],
    signal_id: int | None = None,
    analysis_id: int | None = None,
    reason: str | None = None,
) -> ActionDecision:
    record = ActionDecision(
        signal_id=signal_id,
        analysis_id=analysis_id,
        decider=decider,
        decision=decision,
        decision_metadata=metadata,
        reason=reason,
    )
    db.add(record)
    await db.flush()
    return record


async def create_execution(
    db: AsyncSession,
    mode: str,
    status: str,
    request: dict[str, Any],
    receipt: dict[str, Any],
    network: str = "avalanche",
    decision_id: int | None = None,
    agent_id: int | None = None,
    tx_hash: str | None = None,
) -> ActionExecution:
    record = ActionExecution(
        decision_id=decision_id,
        agent_id=agent_id,
        network=network,
        mode=mode,
        status=status,
        request=request,
        receipt=receipt,
        tx_hash=tx_hash,
    )
    db.add(record)
    await db.flush()
    return record


async def create_policy_event(
    db: AsyncSession,
    action: str,
    outcome: str,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
    execution_id: int | None = None,
    agent_id: int | None = None,
) -> PolicyEvent:
    record = PolicyEvent(
        agent_id=agent_id,
        execution_id=execution_id,
        action=action,
        outcome=outcome,
        reason=reason,
        details=details or {},
    )
    db.add(record)
    await db.flush()
    return record


async def create_audit_trail(
    db: AsyncSession,
    actor_type: str,
    event_type: str,
    payload: dict[str, Any],
    actor_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> AuditTrail:
    record = AuditTrail(
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(record)
    await db.flush()
    return record

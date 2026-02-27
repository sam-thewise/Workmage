"""Action infrastructure runtime tables.

Revision ID: 007
Revises: 006
Create Date: 2026-02-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "action_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("signal_type", sa.String(length=120), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_signals_source", "action_signals", ["source"])
    op.create_index("ix_action_signals_signal_type", "action_signals", ["signal_type"])
    op.create_index("ix_action_signals_dedupe_key", "action_signals", ["dedupe_key"])

    op.create_table(
        "action_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("analyzer", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("result", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["action_signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_analyses_signal_id", "action_analyses", ["signal_id"])
    op.create_index("ix_action_analyses_analyzer", "action_analyses", ["analyzer"])

    op.create_table(
        "action_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("decider", sa.String(length=120), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decision_metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["action_signals.id"]),
        sa.ForeignKeyConstraint(["analysis_id"], ["action_analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_decisions_signal_id", "action_decisions", ["signal_id"])
    op.create_index("ix_action_decisions_analysis_id", "action_decisions", ["analysis_id"])
    op.create_index("ix_action_decisions_decider", "action_decisions", ["decider"])

    op.create_table(
        "action_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("tx_hash", sa.String(length=100), nullable=True),
        sa.Column("request", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("receipt", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["action_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_executions_decision_id", "action_executions", ["decision_id"])
    op.create_index("ix_action_executions_agent_id", "action_executions", ["agent_id"])
    op.create_index("ix_action_executions_status", "action_executions", ["status"])

    op.create_table(
        "policy_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["action_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_events_agent_id", "policy_events", ["agent_id"])
    op.create_index("ix_policy_events_execution_id", "policy_events", ["execution_id"])
    op.create_index("ix_policy_events_outcome", "policy_events", ["outcome"])

    op.create_table(
        "audit_trails",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_trails_actor_type", "audit_trails", ["actor_type"])
    op.create_index("ix_audit_trails_actor_id", "audit_trails", ["actor_id"])
    op.create_index("ix_audit_trails_event_type", "audit_trails", ["event_type"])

    op.create_table(
        "action_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["action_executions.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_approvals_execution_id", "action_approvals", ["execution_id"])
    op.create_index("ix_action_approvals_requested_by_user_id", "action_approvals", ["requested_by_user_id"])
    op.create_index("ix_action_approvals_approved_by_user_id", "action_approvals", ["approved_by_user_id"])

    op.create_table(
        "agent_wallets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("wallet_type", sa.String(length=32), nullable=False),
        sa.Column("nft_contract", sa.String(length=120), nullable=True),
        sa.Column("nft_token_id", sa.String(length=120), nullable=True),
        sa.Column("wallet_address", sa.String(length=120), nullable=False),
        sa.Column("signer_address", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("wallet_metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_address"),
    )
    op.create_index("ix_agent_wallets_agent_id", "agent_wallets", ["agent_id"])
    op.create_index("ix_agent_wallets_owner_user_id", "agent_wallets", ["owner_user_id"])
    op.create_index("ix_agent_wallets_wallet_address", "agent_wallets", ["wallet_address"])

    op.create_table(
        "wallet_funding_intents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("intent_type", sa.String(length=20), nullable=False),
        sa.Column("asset", sa.String(length=64), nullable=False),
        sa.Column("amount_wei", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("tx_hash", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("intent_metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["agent_wallets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_funding_intents_wallet_id", "wallet_funding_intents", ["wallet_id"])
    op.create_index("ix_wallet_funding_intents_user_id", "wallet_funding_intents", ["user_id"])

    op.create_table(
        "agent_trust_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("identity_registry_ref", sa.String(length=255), nullable=True),
        sa.Column("reputation_registry_ref", sa.String(length=255), nullable=True),
        sa.Column("validation_registry_ref", sa.String(length=255), nullable=True),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=24), nullable=False),
        sa.Column("trust_metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index("ix_agent_trust_profiles_agent_id", "agent_trust_profiles", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_action_approvals_approved_by_user_id", table_name="action_approvals")
    op.drop_index("ix_action_approvals_requested_by_user_id", table_name="action_approvals")
    op.drop_index("ix_action_approvals_execution_id", table_name="action_approvals")
    op.drop_table("action_approvals")

    op.drop_index("ix_agent_trust_profiles_agent_id", table_name="agent_trust_profiles")
    op.drop_table("agent_trust_profiles")

    op.drop_index("ix_wallet_funding_intents_user_id", table_name="wallet_funding_intents")
    op.drop_index("ix_wallet_funding_intents_wallet_id", table_name="wallet_funding_intents")
    op.drop_table("wallet_funding_intents")

    op.drop_index("ix_agent_wallets_wallet_address", table_name="agent_wallets")
    op.drop_index("ix_agent_wallets_owner_user_id", table_name="agent_wallets")
    op.drop_index("ix_agent_wallets_agent_id", table_name="agent_wallets")
    op.drop_table("agent_wallets")

    op.drop_index("ix_audit_trails_event_type", table_name="audit_trails")
    op.drop_index("ix_audit_trails_actor_id", table_name="audit_trails")
    op.drop_index("ix_audit_trails_actor_type", table_name="audit_trails")
    op.drop_table("audit_trails")

    op.drop_index("ix_policy_events_outcome", table_name="policy_events")
    op.drop_index("ix_policy_events_execution_id", table_name="policy_events")
    op.drop_index("ix_policy_events_agent_id", table_name="policy_events")
    op.drop_table("policy_events")

    op.drop_index("ix_action_executions_status", table_name="action_executions")
    op.drop_index("ix_action_executions_agent_id", table_name="action_executions")
    op.drop_index("ix_action_executions_decision_id", table_name="action_executions")
    op.drop_table("action_executions")

    op.drop_index("ix_action_decisions_decider", table_name="action_decisions")
    op.drop_index("ix_action_decisions_analysis_id", table_name="action_decisions")
    op.drop_index("ix_action_decisions_signal_id", table_name="action_decisions")
    op.drop_table("action_decisions")

    op.drop_index("ix_action_analyses_analyzer", table_name="action_analyses")
    op.drop_index("ix_action_analyses_signal_id", table_name="action_analyses")
    op.drop_table("action_analyses")

    op.drop_index("ix_action_signals_dedupe_key", table_name="action_signals")
    op.drop_index("ix_action_signals_signal_type", table_name="action_signals")
    op.drop_index("ix_action_signals_source", table_name="action_signals")
    op.drop_table("action_signals")

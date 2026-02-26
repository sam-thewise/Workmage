"""Chain marketplace listing and purchase polymorphism.

Revision ID: 006
Revises: 005
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Chains: listing + moderation metadata
    op.add_column("chains", sa.Column("expert_id", sa.Integer(), nullable=True))
    op.add_column("chains", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("chains", sa.Column("price_cents", sa.Integer(), nullable=True))
    op.add_column("chains", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("chains", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("chains", sa.Column("tags", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("chains", sa.Column("approval_status", sa.String(length=20), nullable=True))
    op.add_column("chains", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("chains", sa.Column("moderated_by_id", sa.Integer(), nullable=True))
    op.add_column("chains", sa.Column("rejection_reason", sa.Text(), nullable=True))

    op.create_foreign_key("fk_chains_expert_id", "chains", "users", ["expert_id"], ["id"])
    op.create_foreign_key(
        "fk_chains_moderated_by_id", "chains", "users", ["moderated_by_id"], ["id"]
    )

    # Backfill existing chains as draft expert-owned chains by original creator.
    op.execute("UPDATE chains SET expert_id = buyer_id WHERE expert_id IS NULL")
    op.execute("UPDATE chains SET price_cents = 0 WHERE price_cents IS NULL")
    op.execute("UPDATE chains SET status = 'draft' WHERE status IS NULL")
    op.execute("UPDATE chains SET approval_status = 'draft' WHERE approval_status IS NULL")

    op.alter_column("chains", "price_cents", nullable=False, server_default="0")
    op.alter_column("chains", "status", nullable=False, server_default="draft")
    op.alter_column("chains", "approval_status", nullable=False, server_default="draft")

    # Purchases: support purchasing chains as first-class items.
    op.add_column("purchases", sa.Column("chain_id", sa.Integer(), nullable=True))
    op.add_column(
        "purchases",
        sa.Column("payout_plan", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_foreign_key("fk_purchases_chain_id", "purchases", "chains", ["chain_id"], ["id"])
    op.alter_column("purchases", "agent_id", existing_type=sa.Integer(), nullable=True)

    op.create_check_constraint(
        "ck_purchases_item_type",
        "purchases",
        "(agent_id IS NOT NULL AND chain_id IS NULL) OR (agent_id IS NULL AND chain_id IS NOT NULL)",
    )
    op.create_index(
        "uq_purchases_buyer_agent",
        "purchases",
        ["buyer_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("agent_id IS NOT NULL"),
    )
    op.create_index(
        "uq_purchases_buyer_chain",
        "purchases",
        ["buyer_id", "chain_id"],
        unique=True,
        postgresql_where=sa.text("chain_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_purchases_buyer_chain", table_name="purchases")
    op.drop_index("uq_purchases_buyer_agent", table_name="purchases")
    op.drop_constraint("ck_purchases_item_type", "purchases", type_="check")
    op.alter_column("purchases", "agent_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("fk_purchases_chain_id", "purchases", type_="foreignkey")
    op.drop_column("purchases", "payout_plan")
    op.drop_column("purchases", "chain_id")

    op.drop_constraint("fk_chains_moderated_by_id", "chains", type_="foreignkey")
    op.drop_constraint("fk_chains_expert_id", "chains", type_="foreignkey")
    op.drop_column("chains", "rejection_reason")
    op.drop_column("chains", "moderated_by_id")
    op.drop_column("chains", "moderated_at")
    op.drop_column("chains", "approval_status")
    op.drop_column("chains", "tags")
    op.drop_column("chains", "category")
    op.drop_column("chains", "status")
    op.drop_column("chains", "price_cents")
    op.drop_column("chains", "description")
    op.drop_column("chains", "expert_id")

"""Saved outputs table for chain reuse by slug.

Revision ID: 014
Revises: 013
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_outputs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_chain_run_id", sa.String(length=64), nullable=True),
        sa.Column("source_node_id", sa.String(length=64), nullable=True),
        sa.Column("source_agent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slug", name="uq_saved_outputs_user_slug"),
    )
    op.create_index("ix_saved_outputs_user_id", "saved_outputs", ["user_id"])
    op.create_index("ix_saved_outputs_slug", "saved_outputs", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_saved_outputs_slug", table_name="saved_outputs")
    op.drop_index("ix_saved_outputs_user_id", table_name="saved_outputs")
    op.drop_table("saved_outputs")

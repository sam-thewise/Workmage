"""Chain approval requests and chain runs tables.

Revision ID: 016
Revises: 015
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chain_approval_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approval_node_id", sa.String(length=64), nullable=False),
        sa.Column("state_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chain_approval_requests_chain_id", "chain_approval_requests", ["chain_id"])
    op.create_index("ix_chain_approval_requests_user_id", "chain_approval_requests", ["user_id"])
    op.create_index("ix_chain_approval_requests_status", "chain_approval_requests", ["status"])

    op.create_table(
        "chain_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("approval_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["chain_approval_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chain_runs_user_id", "chain_runs", ["user_id"])
    op.create_index("ix_chain_runs_chain_id", "chain_runs", ["chain_id"])
    op.create_index("ix_chain_runs_status", "chain_runs", ["status"])
    op.create_index("ix_chain_runs_read_at", "chain_runs", ["read_at"])
    op.create_index("ix_chain_runs_created_at", "chain_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chain_runs_created_at", table_name="chain_runs")
    op.drop_index("ix_chain_runs_read_at", table_name="chain_runs")
    op.drop_index("ix_chain_runs_status", table_name="chain_runs")
    op.drop_index("ix_chain_runs_chain_id", table_name="chain_runs")
    op.drop_index("ix_chain_runs_user_id", table_name="chain_runs")
    op.drop_table("chain_runs")
    op.drop_index("ix_chain_approval_requests_status", table_name="chain_approval_requests")
    op.drop_index("ix_chain_approval_requests_user_id", table_name="chain_approval_requests")
    op.drop_index("ix_chain_approval_requests_chain_id", table_name="chain_approval_requests")
    op.drop_table("chain_approval_requests")

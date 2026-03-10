"""Workspace personalities - tone configs scoped to workspace, optionally per-chain.

Revision ID: 022
Revises: 021
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_personalities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_run_id", sa.Integer(), nullable=True),
        sa.Column("source_node_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chain_id"], ["chains.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspace_personalities_workspace_id",
        "workspace_personalities",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_personalities_chain_id",
        "workspace_personalities",
        ["chain_id"],
    )
    # Unique: workspace-level (chain_id IS NULL): (workspace_id, name)
    op.create_index(
        "uq_workspace_personalities_workspace_name",
        "workspace_personalities",
        ["workspace_id", "name"],
        unique=True,
        postgresql_where=sa.text("chain_id IS NULL"),
    )
    # Unique: chain-level: (workspace_id, chain_id, name)
    op.create_index(
        "uq_workspace_personalities_workspace_chain_name",
        "workspace_personalities",
        ["workspace_id", "chain_id", "name"],
        unique=True,
        postgresql_where=sa.text("chain_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workspace_personalities_workspace_chain_name",
        table_name="workspace_personalities",
    )
    op.drop_index(
        "uq_workspace_personalities_workspace_name",
        table_name="workspace_personalities",
    )
    op.drop_index(
        "ix_workspace_personalities_chain_id",
        table_name="workspace_personalities",
    )
    op.drop_index(
        "ix_workspace_personalities_workspace_id",
        table_name="workspace_personalities",
    )
    op.drop_table("workspace_personalities")

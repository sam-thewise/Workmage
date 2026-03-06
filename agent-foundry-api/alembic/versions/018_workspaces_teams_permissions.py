"""Workspaces, members, secrets, run share links; chains.workspace_id and backfill.

Revision ID: 018
Revises: 017
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    op.add_column(
        "chains",
        sa.Column("workspace_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chains_workspace_id",
        "chains",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_chains_workspace_id", "chains", ["workspace_id"])

    op.create_table(
        "workspace_secrets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=True),
        sa.Column("key_name", sa.String(length=255), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chain_id"], ["chains.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_secrets_workspace_id", "workspace_secrets", ["workspace_id"])
    op.create_index("ix_workspace_secrets_chain_id", "workspace_secrets", ["chain_id"])

    op.create_table(
        "run_share_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["chain_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_share_links_token", "run_share_links", ["token"], unique=True)
    op.create_index("ix_run_share_links_run_id", "run_share_links", ["run_id"])

    # Backfill: create default workspace per user who has chains (as buyer or expert), assign each chain to its buyer's workspace
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT DISTINCT buyer_id FROM chains "
            "UNION SELECT expert_id FROM chains WHERE expert_id IS NOT NULL"
        )
    )
    user_ids = [row[0] for row in result]
    for uid in user_ids:
        conn.execute(
            sa.text(
                """
                INSERT INTO workspaces (name, slug, created_at, updated_at)
                VALUES ('Personal', NULL, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
                """
            )
        )
        workspace_id_result = conn.execute(sa.text("SELECT lastval()"))
        workspace_id = workspace_id_result.scalar()
        conn.execute(
            sa.text(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                VALUES (:wid, :uid, 'owner', NOW() AT TIME ZONE 'UTC')
                """
            ),
            {"wid": workspace_id, "uid": uid},
        )
        # Assign chains to this user's workspace only when they are the buyer (each chain has one workspace = buyer's)
        conn.execute(
            sa.text("UPDATE chains SET workspace_id = :wid WHERE buyer_id = :uid"),
            {"wid": workspace_id, "uid": uid},
        )


def downgrade() -> None:
    op.drop_index("ix_run_share_links_run_id", table_name="run_share_links")
    op.drop_index("ix_run_share_links_token", table_name="run_share_links")
    op.drop_table("run_share_links")
    op.drop_index("ix_workspace_secrets_chain_id", table_name="workspace_secrets")
    op.drop_index("ix_workspace_secrets_workspace_id", table_name="workspace_secrets")
    op.drop_table("workspace_secrets")
    op.drop_index("ix_chains_workspace_id", table_name="chains")
    op.drop_constraint("fk_chains_workspace_id", "chains", type_="foreignkey")
    op.drop_column("chains", "workspace_id")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")

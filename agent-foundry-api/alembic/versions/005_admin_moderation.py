"""Admin panel, moderator role, agent moderation

Revision ID: 005
Revises: 004
Create Date: 2024-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'moderator'")
    op.add_column("agents", sa.Column("approval_status", sa.String(20), nullable=True))
    op.execute("UPDATE agents SET approval_status = 'approved' WHERE status = 'listed'")
    op.execute("UPDATE agents SET approval_status = 'draft' WHERE approval_status IS NULL")
    op.alter_column("agents", "approval_status", nullable=False, server_default="draft")
    op.add_column("agents", sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agents", sa.Column("moderated_by_id", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_agents_moderated_by", "agents", "users", ["moderated_by_id"], ["id"]
    )
    op.create_table(
        "moderator_invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_moderator_invites_token", "moderator_invites", ["token"], unique=True)
    op.create_index("ix_moderator_invites_email", "moderator_invites", ["email"])


def downgrade() -> None:
    op.drop_index("ix_moderator_invites_email", table_name="moderator_invites")
    op.drop_index("ix_moderator_invites_token", table_name="moderator_invites")
    op.drop_table("moderator_invites")
    op.drop_constraint("fk_agents_moderated_by", "agents", type_="foreignkey")
    op.drop_column("agents", "rejection_reason")
    op.drop_column("agents", "moderated_by_id")
    op.drop_column("agents", "moderated_at")
    op.drop_column("agents", "approval_status")

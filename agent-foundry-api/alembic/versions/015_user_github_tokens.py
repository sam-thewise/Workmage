"""Add user_github_tokens table.

Revision ID: 015
Revises: 014
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_github_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_github_tokens_user_id"),
    )
    op.create_index("ix_user_github_tokens_user_id", "user_github_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_github_tokens_user_id", table_name="user_github_tokens")
    op.drop_table("user_github_tokens")

"""User personality profiles for content voice.

Revision ID: 013
Revises: 012
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_personality_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profile_text", sa.Text(), nullable=False),
        sa.Column("source_sample", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_personality_profiles_user_id"),
    )
    op.create_index(
        "ix_user_personality_profiles_user_id",
        "user_personality_profiles",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_personality_profiles_user_id",
        table_name="user_personality_profiles",
    )
    op.drop_table("user_personality_profiles")

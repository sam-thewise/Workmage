"""Content drafts table for X/social approval flow.

Revision ID: 012
Revises: 011
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target_handle", sa.String(length=120), nullable=True),
        sa.Column("target_url", sa.String(length=512), nullable=True),
        sa.Column("source_chain_run_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("edited_body", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_drafts_user_id", "content_drafts", ["user_id"])
    op.create_index("ix_content_drafts_type", "content_drafts", ["type"])
    op.create_index("ix_content_drafts_status", "content_drafts", ["status"])
    op.create_index("ix_content_drafts_source_chain_run_id", "content_drafts", ["source_chain_run_id"])
    op.create_index("ix_content_drafts_target_handle", "content_drafts", ["target_handle"])


def downgrade() -> None:
    op.drop_index("ix_content_drafts_target_handle", table_name="content_drafts")
    op.drop_index("ix_content_drafts_source_chain_run_id", table_name="content_drafts")
    op.drop_index("ix_content_drafts_status", table_name="content_drafts")
    op.drop_index("ix_content_drafts_type", table_name="content_drafts")
    op.drop_index("ix_content_drafts_user_id", table_name="content_drafts")
    op.drop_table("content_drafts")

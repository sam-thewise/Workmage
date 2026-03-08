"""Wizard use cases table and chain slug.

Revision ID: 020
Revises: 019
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chains",
        sa.Column("slug", sa.String(length=120), nullable=True),
    )
    op.create_index("ix_chains_slug", "chains", ["slug"], unique=True)

    op.create_table(
        "wizard_use_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chain_slug", sa.String(length=120), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "inject_as",
            sa.String(length=32),
            nullable=False,
            server_default="slugs",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_wizard_use_cases_slug"),
    )
    op.create_index("ix_wizard_use_cases_slug", "wizard_use_cases", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_wizard_use_cases_slug", table_name="wizard_use_cases")
    op.drop_table("wizard_use_cases")
    op.drop_index("ix_chains_slug", table_name="chains")
    op.drop_column("chains", "slug")

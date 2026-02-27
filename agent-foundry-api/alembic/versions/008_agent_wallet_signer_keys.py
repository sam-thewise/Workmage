"""Agent wallet signer keys (managed keys storage).

Revision ID: 008
Revises: 007
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_wallet_signer_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["agent_wallets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_id"),
    )
    op.create_index("ix_agent_wallet_signer_keys_wallet_id", "agent_wallet_signer_keys", ["wallet_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_wallet_signer_keys_wallet_id", table_name="agent_wallet_signer_keys")
    op.drop_table("agent_wallet_signer_keys")

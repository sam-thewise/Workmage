"""Mint payment intents and watcher state tables.

Revision ID: 011
Revises: 010
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mint_payment_intents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("recipient_address", sa.String(length=120), nullable=False),
        sa.Column("required_avax_wei", sa.String(length=120), nullable=False),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payment_tx_hash", sa.String(length=100), nullable=True),
        sa.Column("mint_tx_hash", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet_id"], ["agent_wallets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mint_payment_intents_recipient_address", "mint_payment_intents", ["recipient_address"])
    op.create_index("ix_mint_payment_intents_wallet_id", "mint_payment_intents", ["wallet_id"])
    op.create_index("ix_mint_payment_intents_network", "mint_payment_intents", ["network"])
    op.create_index("ix_mint_payment_intents_recipient_network", "mint_payment_intents", ["recipient_address", "network"])

    op.create_table(
        "mint_payment_watcher_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("last_block_number", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("network"),
    )
    op.create_index("ix_mint_payment_watcher_state_network", "mint_payment_watcher_state", ["network"])


def downgrade() -> None:
    op.drop_index("ix_mint_payment_watcher_state_network", table_name="mint_payment_watcher_state")
    op.drop_table("mint_payment_watcher_state")
    op.drop_index("ix_mint_payment_intents_recipient_network", table_name="mint_payment_intents")
    op.drop_index("ix_mint_payment_intents_network", table_name="mint_payment_intents")
    op.drop_index("ix_mint_payment_intents_wallet_id", table_name="mint_payment_intents")
    op.drop_index("ix_mint_payment_intents_recipient_address", table_name="mint_payment_intents")
    op.drop_table("mint_payment_intents")

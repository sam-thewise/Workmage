"""Add runner_user_id to action_executions for per-runner wallet resolution.

Revision ID: 010
Revises: 009
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "action_executions",
        sa.Column("runner_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_action_executions_runner_user_id",
        "action_executions",
        "users",
        ["runner_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_action_executions_runner_user_id",
        "action_executions",
        ["runner_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_executions_runner_user_id", table_name="action_executions")
    op.drop_constraint(
        "fk_action_executions_runner_user_id",
        "action_executions",
        type_="foreignkey",
    )
    op.drop_column("action_executions", "runner_user_id")

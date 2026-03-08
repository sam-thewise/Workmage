"""WizardUseCase model for config-driven wizard use cases."""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WizardUseCase(Base):
    """Use case config for the setup wizard: maps goals to chains and params."""

    __tablename__ = "wizard_use_cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chain_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    params: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False
    )  # list of {slug, label, type, required, ...}
    inject_as: Mapped[str] = mapped_column(
        String(32), default="slugs", nullable=False
    )  # slugs | user_input | run_history
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

"""Saved output model for persisting chain/agent outputs by slug (per user)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SavedOutput(Base):
    """User-scoped named output (e.g. personality, trend_report) for reuse in chains."""

    __tablename__ = "saved_outputs"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_saved_outputs_user_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_chain_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="saved_outputs", foreign_keys=[user_id]
    )

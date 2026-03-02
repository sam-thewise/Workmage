"""Content draft model for X/social approval flow (post and reply drafts)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ContentDraft(Base):
    """Draft post or reply for human review/approval before publishing to X."""

    __tablename__ = "content_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # post | reply
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target_handle: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    target_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_chain_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", index=True
    )  # draft | pending_approval | approved | rejected
    edited_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="content_drafts")

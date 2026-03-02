"""User personality profile for X/content voice (analyzed from tweets, editable)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserPersonalityProfile(Base):
    """One per user: voice/beliefs/do's and don'ts for content generation."""

    __tablename__ = "user_personality_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    profile_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="personality_profile", foreign_keys=[user_id]
    )

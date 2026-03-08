"""Agent model."""
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.purchase import Purchase
    from app.models.agent_run import AgentRun


class AgentStatus(str, enum.Enum):
    """Agent status enum."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    LISTED = "listed"
    REJECTED = "rejected"


class Agent(Base):
    """Agent listing model."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=AgentStatus.DRAFT.value, nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    approval_status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    expert: Mapped["User"] = relationship(
        "User", back_populates="agents", foreign_keys=[expert_id]
    )
    moderated_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[moderated_by_id], back_populates="agents_moderated"
    )
    purchases: Mapped[list["Purchase"]] = relationship(
        "Purchase", back_populates="agent"
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun", back_populates="agent", foreign_keys="AgentRun.agent_id"
    )

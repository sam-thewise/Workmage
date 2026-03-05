"""Chain run model - persisted run results and status for notifications and history."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chain import AgentChain
    from app.models.chain_approval import ChainApprovalRequest


class ChainRun(Base):
    """Persisted chain run: status, result content/error, and optional approval link."""

    __tablename__ = "chain_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id"), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_id: Mapped[int | None] = mapped_column(
        ForeignKey("chain_approval_requests.id"), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="chain_runs", foreign_keys=[user_id])
    chain: Mapped["AgentChain"] = relationship("AgentChain", back_populates="runs")
    approval: Mapped["ChainApprovalRequest | None"] = relationship(
        "ChainApprovalRequest", back_populates="chain_run", foreign_keys=[approval_id]
    )

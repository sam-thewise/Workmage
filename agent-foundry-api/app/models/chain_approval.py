"""Chain approval request model - persisted state when execution hits an approval node."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chain import AgentChain
    from app.models.chain_run import ChainRun


class ChainApprovalRequest(Base):
    """Approval request when a chain run hits an approval node. Stores outputs and state for resume."""

    __tablename__ = "chain_approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chain_id: Mapped[int] = mapped_column(ForeignKey("chains.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    outputs: Mapped[dict] = mapped_column(JSONB, nullable=False)  # node_id -> content
    approval_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    chain: Mapped["AgentChain"] = relationship("AgentChain", back_populates="approval_requests")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    decided_by: Mapped["User | None"] = relationship("User", foreign_keys=[decided_by_user_id])
    chain_run: Mapped["ChainRun | None"] = relationship(
        "ChainRun", back_populates="approval", foreign_keys="ChainRun.approval_id", uselist=False
    )

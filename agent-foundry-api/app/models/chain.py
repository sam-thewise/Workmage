"""AgentChain model for chain listings and execution definitions."""
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.purchase import Purchase
    from app.models.chain_approval import ChainApprovalRequest
    from app.models.chain_run import ChainRun
    from app.models.workspace import Workspace
    from app.models.workspace_secret import WorkspaceSecret


class ChainStatus(str, enum.Enum):
    """Chain status enum."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    LISTED = "listed"
    REJECTED = "rejected"


class AgentChain(Base):
    """Chain definition and listing metadata."""

    __tablename__ = "chains"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expert_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=ChainStatus.DRAFT.value, nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace: Mapped["Workspace | None"] = relationship(
        "Workspace", back_populates="chains", foreign_keys=[workspace_id]
    )
    buyer: Mapped["User"] = relationship("User", back_populates="chains", foreign_keys=[buyer_id])
    expert: Mapped["User | None"] = relationship(
        "User", back_populates="chains_authored", foreign_keys=[expert_id]
    )
    moderated_by: Mapped["User | None"] = relationship(
        "User", back_populates="chains_moderated", foreign_keys=[moderated_by_id]
    )
    purchases: Mapped[list["Purchase"]] = relationship(
        "Purchase", back_populates="chain"
    )
    approval_requests: Mapped[list["ChainApprovalRequest"]] = relationship(
        "ChainApprovalRequest", back_populates="chain"
    )
    runs: Mapped[list["ChainRun"]] = relationship(
        "ChainRun", back_populates="chain"
    )
    workspace_secrets: Mapped[list["WorkspaceSecret"]] = relationship(
        "WorkspaceSecret", back_populates="chain", foreign_keys="WorkspaceSecret.chain_id"
    )

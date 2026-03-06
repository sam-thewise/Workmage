"""Workspace secret model - encrypted secrets scoped to workspace, optionally per-chain."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import Workspace
    from app.models.chain import AgentChain


class WorkspaceSecret(Base):
    """Encrypted secret scoped to workspace; optional chain_id for per-team."""

    __tablename__ = "workspace_secrets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    chain_id: Mapped[int | None] = mapped_column(
        ForeignKey("chains.id", ondelete="CASCADE"), nullable=True
    )
    key_name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="secrets")
    chain: Mapped["AgentChain | None"] = relationship(
        "AgentChain", back_populates="workspace_secrets", foreign_keys=[chain_id]
    )

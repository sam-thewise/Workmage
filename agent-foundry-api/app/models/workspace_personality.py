"""Workspace personality model - tone configs scoped to workspace, optionally per-chain."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import Workspace
    from app.models.chain import AgentChain


class WorkspacePersonality(Base):
    """Personality (tone/voice) config scoped to workspace; optional chain_id for team-level."""

    __tablename__ = "workspace_personalities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    chain_id: Mapped[int | None] = mapped_column(
        ForeignKey("chains.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    source_run_id: Mapped[int | None] = mapped_column(nullable=True)
    source_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace", back_populates="personalities", foreign_keys=[workspace_id]
    )
    chain: Mapped["AgentChain | None"] = relationship(
        "AgentChain", back_populates="workspace_personalities", foreign_keys=[chain_id]
    )

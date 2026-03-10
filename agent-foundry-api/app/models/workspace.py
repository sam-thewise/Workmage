"""Workspace model - container for members, chains, secrets, and runs."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace_member import WorkspaceMember
    from app.models.workspace_secret import WorkspaceSecret
    from app.models.workspace_personality import WorkspacePersonality
    from app.models.chain import AgentChain


class Workspace(Base):
    """Workspace: container for members, teams (chains), secrets, and runs."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )
    secrets: Mapped[list["WorkspaceSecret"]] = relationship(
        "WorkspaceSecret", back_populates="workspace", cascade="all, delete-orphan"
    )
    personalities: Mapped[list["WorkspacePersonality"]] = relationship(
        "WorkspacePersonality", back_populates="workspace", cascade="all, delete-orphan",
        foreign_keys="WorkspacePersonality.workspace_id",
    )
    chains: Mapped[list["AgentChain"]] = relationship(
        "AgentChain", back_populates="workspace", foreign_keys="AgentChain.workspace_id"
    )

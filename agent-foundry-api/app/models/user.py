"""User and related models."""
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, DateTime, Integer, TypeDecorator
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.chain import AgentChain
    from app.models.content_draft import ContentDraft
    from app.models.user_personality import UserPersonalityProfile
    from app.models.saved_output import SavedOutput
    from app.models.moderator_invite import ModeratorInvite
    from app.models.purchase import Purchase
    from app.models.subscription import Subscription
    from app.models.user_llm_key import UserLLMKey
    from app.models.user_github_token import UserGitHubToken
    from app.models.chain_run import ChainRun


class UserRole(str, enum.Enum):
    """User role enum."""

    BUYER = "buyer"
    EXPERT = "expert"
    MODERATOR = "moderator"
    ADMIN = "admin"


class UserRoleType(TypeDecorator):
    """Store UserRole as PostgreSQL enum values (not names)."""

    impl = ENUM("buyer", "expert", "moderator", "admin", name="userrole", create_type=False)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, UserRole):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return UserRole(value)


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        UserRoleType(),
        default=UserRole.BUYER,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Expert profile (when role is expert)
    expert_profile: Mapped["ExpertProfile | None"] = relationship(
        "ExpertProfile", back_populates="user", uselist=False
    )
    # Agents created by expert
    agents: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="expert", foreign_keys="Agent.expert_id"
    )
    # Purchases (as buyer)
    purchases: Mapped[list["Purchase"]] = relationship(
        "Purchase", back_populates="buyer"
    )
    # Subscription (as buyer)
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="buyer", uselist=False
    )
    # BYOK LLM keys
    llm_keys: Mapped[list["UserLLMKey"]] = relationship(
        "UserLLMKey", back_populates="user"
    )
    # GitHub token for MCP GitHub tools (one per user, encrypted at rest)
    github_token: Mapped["UserGitHubToken | None"] = relationship(
        "UserGitHubToken", back_populates="user", uselist=False
    )
    # Chains (as buyer)
    chains: Mapped[list["AgentChain"]] = relationship(
        "AgentChain", back_populates="buyer", foreign_keys="AgentChain.buyer_id"
    )
    # Chains authored by this expert
    chains_authored: Mapped[list["AgentChain"]] = relationship(
        "AgentChain", back_populates="expert", foreign_keys="AgentChain.expert_id"
    )
    # Moderator invites sent by this admin
    moderator_invites_sent: Mapped[list["ModeratorInvite"]] = relationship(
        "ModeratorInvite", back_populates="invited_by", foreign_keys="ModeratorInvite.invited_by_id"
    )
    # Agents moderated by this user (admin/mod)
    agents_moderated: Mapped[list["Agent"]] = relationship(
        "Agent", back_populates="moderated_by", foreign_keys="Agent.moderated_by_id"
    )
    # Chains moderated by this user (admin/mod)
    chains_moderated: Mapped[list["AgentChain"]] = relationship(
        "AgentChain", back_populates="moderated_by", foreign_keys="AgentChain.moderated_by_id"
    )
    # Content drafts (X/social approval flow)
    content_drafts: Mapped[list["ContentDraft"]] = relationship(
        "ContentDraft", back_populates="user", foreign_keys="ContentDraft.user_id"
    )
    # Personality profile for content voice (one per user)
    personality_profile: Mapped["UserPersonalityProfile | None"] = relationship(
        "UserPersonalityProfile",
        back_populates="user",
        uselist=False,
        foreign_keys="UserPersonalityProfile.user_id",
    )
    # Saved outputs (slug -> content) for chain reuse
    saved_outputs: Mapped[list["SavedOutput"]] = relationship(
        "SavedOutput", back_populates="user", foreign_keys="SavedOutput.user_id"
    )
    # Chain runs (persisted results and notifications)
    chain_runs: Mapped[list["ChainRun"]] = relationship(
        "ChainRun", back_populates="user", foreign_keys="ChainRun.user_id"
    )


class ExpertProfile(Base):
    """Expert profile for payout and profile info."""

    __tablename__ = "expert_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_connect_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="expert_profile")

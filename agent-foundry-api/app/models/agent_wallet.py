"""Agent wallet, funding rail, and trust metadata models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentWallet(Base):
    """ERC-6551 oriented wallet record for an agent."""

    __tablename__ = "agent_wallets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    network: Mapped[str] = mapped_column(String(32), nullable=False, default="avalanche")
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False, default=43114)
    wallet_type: Mapped[str] = mapped_column(String(32), nullable=False, default="erc6551")
    nft_contract: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nft_token_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    wallet_address: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    signer_address: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    wallet_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    signer_key: Mapped["AgentWalletSignerKey | None"] = relationship(
        "AgentWalletSignerKey",
        back_populates="wallet",
        uselist=False,
        lazy="raise",
    )


class AgentWalletSignerKey(Base):
    """Encrypted private key for platform-managed agent wallets only."""

    __tablename__ = "agent_wallet_signer_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("agent_wallets.id"), nullable=False, unique=True, index=True
    )
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    wallet: Mapped["AgentWallet"] = relationship("AgentWallet", back_populates="signer_key")


class WalletFundingIntent(Base):
    """Funding/withdrawal intent records for hybrid custody workflows."""

    __tablename__ = "wallet_funding_intents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("agent_wallets.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    intent_type: Mapped[str] = mapped_column(String(20), nullable=False)  # fund|withdraw
    asset: Mapped[str] = mapped_column(String(64), nullable=False, default="AVAX")
    amount_wei: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="requested")
    tx_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AgentTrustProfile(Base):
    """ERC-8004-aligned trust metadata for admission and policy tiering."""

    __tablename__ = "agent_trust_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False, unique=True, index=True)
    identity_registry_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reputation_registry_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_registry_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tier: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    trust_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

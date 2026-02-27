"""Shared agent NFT contract deployment record (per chain)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentNftContract(Base):
    """Deployed shared agent identity NFT contract per network (used for ERC-721 mint + ERC-6551 TBA)."""

    __tablename__ = "agent_nft_contracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    network: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_address: Mapped[str] = mapped_column(String(120), nullable=False)
    deploy_tx_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_guid: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contract_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

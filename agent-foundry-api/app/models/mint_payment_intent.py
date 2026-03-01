"""Mint payment intent model for user-paid Workmage Agent NFT mints."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MintPaymentIntent(Base):
    """Pending mint payment: user pays AVAX, watcher mints NFT to recipient."""

    __tablename__ = "mint_payment_intents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("agent_wallets.id"), nullable=False, index=True)
    recipient_address: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    required_avax_wei: Mapped[str] = mapped_column(String(120), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending_payment"
    )  # pending_payment | paid | minted | expired | failed
    payment_tx_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mint_tx_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    wallet: Mapped["AgentWallet"] = relationship("AgentWallet", back_populates="mint_payment_intents")

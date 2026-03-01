"""Mint payment watcher state: last processed block per network."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MintPaymentWatcherState(Base):
    """Tracks last processed block for mint payment events per network."""

    __tablename__ = "mint_payment_watcher_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    network: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    last_block_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

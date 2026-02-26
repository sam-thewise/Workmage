"""Purchase model."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.agent import Agent
    from app.models.chain import AgentChain


class Purchase(Base):
    """Marketplace purchase by a buyer."""

    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint(
            "(agent_id IS NOT NULL AND chain_id IS NULL) OR (agent_id IS NULL AND chain_id IS NOT NULL)",
            name="ck_purchases_item_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    chain_id: Mapped[int | None] = mapped_column(ForeignKey("chains.id"), nullable=True)
    payout_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    buyer: Mapped["User"] = relationship("User", back_populates="purchases")
    agent: Mapped["Agent | None"] = relationship("Agent", back_populates="purchases")
    chain: Mapped["AgentChain | None"] = relationship("AgentChain", back_populates="purchases")

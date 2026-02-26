"""Subscription model for run quotas."""
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class SubscriptionTier(str, enum.Enum):
    """Subscription tier names."""

    FREE = "free"
    STANDARD = "standard"
    PRO = "pro"


class Subscription(Base):
    """Buyer subscription for run quotas."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    runs_per_period: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    period: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    runs_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    buyer: Mapped["User"] = relationship("User", back_populates="subscription")

"""Purchase schemas."""
from datetime import datetime

from pydantic import BaseModel


class PurchaseCreate(BaseModel):
    """Create purchase (initiate checkout)."""

    agent_id: int | None = None
    chain_id: int | None = None


class PurchaseResponse(BaseModel):
    """Purchase response."""

    id: int
    agent_id: int | None = None
    chain_id: int | None = None
    purchased_at: datetime

    class Config:
        from_attributes = True


class CheckoutResponse(BaseModel):
    """Stripe checkout or direct purchase response."""

    success: bool
    purchase_id: int | None = None
    checkout_url: str | None = None
    message: str | None = None

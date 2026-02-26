"""Agent Pydantic schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base agent schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(default=0, ge=0)
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    manifest_raw: str = Field(..., description="OASF manifest as JSON or YAML string")
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    price_cents: int = Field(default=0, ge=0)
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class AgentUpdate(BaseModel):
    """Schema for partial agent update."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    price_cents: int | None = Field(None, ge=0)
    category: str | None = None
    tags: list[str] | None = None
    manifest_raw: str | None = None


class AgentResponse(AgentBase):
    """Schema for agent response."""

    id: int
    expert_id: int
    manifest: dict[str, Any]
    status: str
    approval_status: str | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Schema for agent list item."""

    id: int
    name: str
    description: str | None
    price_cents: int
    status: str
    approval_status: str | None = None
    rejection_reason: str | None = None
    category: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

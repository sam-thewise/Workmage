"""Chain schemas."""
from typing import Any

from pydantic import BaseModel, Field


class ChainNode(BaseModel):
    """Node in chain definition."""
    id: str
    agent_id: int
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    role: str | None = None


class ChainEdge(BaseModel):
    """Edge in chain definition."""
    source: str
    target: str
    source_port: str = "output"
    target_port: str = "input"


class ChainDefinition(BaseModel):
    """Chain graph definition."""
    nodes: list[ChainNode] = Field(default_factory=list)
    edges: list[ChainEdge] = Field(default_factory=list)


class ChainCreate(BaseModel):
    """Create chain request."""
    name: str
    definition: dict[str, Any]


class ChainUpdate(BaseModel):
    """Update chain request."""
    name: str | None = None
    definition: dict[str, Any] | None = None


class ChainResponse(BaseModel):
    """Chain response with optional agent details."""
    id: int
    name: str
    definition: dict[str, Any]
    created_at: str | None
    updated_at: str | None
    agents: list[dict[str, Any]] | None = None


class ChainRunRequest(BaseModel):
    """Run chain request."""
    user_input: str
    model: str = "openai/gpt-4"
    use_byok: bool = False

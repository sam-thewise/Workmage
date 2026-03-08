"""Chain schemas."""
from typing import Any

from pydantic import BaseModel, Field


class ChainNode(BaseModel):
    """Node in chain definition. Agent nodes have agent_id; slug nodes have type='slug' and slug; approval nodes have type='approval'."""
    id: str
    agent_id: int | None = None  # None for slug and approval nodes
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    role: str | None = None
    type: str | None = None  # "slug" | "approval" | None (agent)
    slug: str | None = None
    content: str | None = None  # optional fixed content for slug nodes ("set slug content")
    lane: str | None = None  # "setup" | "main"
    save_to_slug: str | None = None  # for setup-lane agent nodes
    input_from_slug: str | None = None  # prefill agent input from saved output (optional)
    title: str | None = None  # for approval nodes: optional title shown with the result
    message: str | None = None  # for approval nodes: optional message shown with the result


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
    description: str | None = None
    price_cents: int = Field(default=0, ge=0)
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    definition: dict[str, Any]
    workspace_id: int | None = None
    slug: str | None = None  # for wizard use case lookup


class ChainUpdate(BaseModel):
    """Update chain request."""

    name: str | None = None
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    category: str | None = None
    tags: list[str] | None = None
    definition: dict[str, Any] | None = None
    slug: str | None = None


class ChainListResponse(BaseModel):
    """Marketplace/list chain response."""

    id: int
    name: str
    description: str | None = None
    price_cents: int
    status: str
    approval_status: str | None = None
    category: str | None = None
    slug: str | None = None
    created_at: str | None
    updated_at: str | None = None


class ChainResponse(BaseModel):
    """Chain response with optional agent details."""

    id: int
    name: str
    description: str | None = None
    price_cents: int = 0
    status: str = "draft"
    approval_status: str | None = None
    category: str | None = None
    slug: str | None = None
    tags: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    definition: dict[str, Any]
    created_at: str | None
    updated_at: str | None
    agents: list[dict[str, Any]] | None = None


class InputRunRef(BaseModel):
    """Reference to a prior run (chain or agent) for use as input to a comparison chain."""
    source: str  # "chain" | "agent"
    run_id: int


class ChainRunRequest(BaseModel):
    """Run chain request."""
    user_input: str
    model: str = "openai/gpt-5.2"
    use_byok: bool = False
    run_type: str | None = None  # "setup" for first-run lane only; default = main lane
    input_run_refs: list[InputRunRef] | None = None  # prior runs to inject as input (e.g. for comparison)

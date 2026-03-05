"""Chain compatibility service - input/output format matching for agent chaining."""
from typing import Any


DEFAULT_FORMATS = ["text/plain"]


def get_agent_formats(agent: Any) -> tuple[list[str], list[str]]:
    """
    Extract input_formats and output_formats from agent manifest.
    Defaults to ["text/plain"] if missing (backward compatible).
    """
    manifest = getattr(agent, "manifest", None) or {}
    if not isinstance(manifest, dict):
        return (DEFAULT_FORMATS.copy(), DEFAULT_FORMATS.copy())

    def _parse_formats(key: str) -> list[str]:
        val = manifest.get(key)
        if val is not None and isinstance(val, list):
            return [str(x) for x in val if isinstance(x, str)]
        return DEFAULT_FORMATS.copy()

    return (_parse_formats("input_formats"), _parse_formats("output_formats"))


def can_chain(from_agent: Any, to_agent: Any) -> bool:
    """
    Returns True if from_agent's output can feed to_agent's input.
    Valid when output_formats(from) ∩ input_formats(to) ≠ ∅.
    """
    _, out_formats = get_agent_formats(from_agent)
    in_formats, _ = get_agent_formats(to_agent)
    return bool(set(out_formats) & set(in_formats))


def validate_chain_definition(
    nodes: list[dict],
    edges: list[dict],
    agent_lookup: dict[int, Any],
) -> list[str]:
    """
    Validate chain definition. Returns list of error messages (empty if valid).
    Checks: all agents exist and purchased, edges compatible, no cycles.
    """
    errors: list[str] = []

    node_by_id: dict[str, dict] = {}
    for n in nodes:
        nid = n.get("id")
        if not nid:
            errors.append("Node missing id")
            continue
        node_by_id[nid] = n
        node_type = n.get("type")
        agent_id = n.get("agent_id")
        if node_type == "slug":
            if not n.get("slug"):
                errors.append(f"Slug node {nid} missing slug")
        elif node_type == "approval":
            if agent_id is not None:
                errors.append(f"Approval node {nid} must not have agent_id")
        elif agent_id is None:
            errors.append(f"Node {nid} missing agent_id")
        elif agent_id not in agent_lookup:
            errors.append(f"Agent {agent_id} not found or not purchased")

    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if not src or not tgt:
            errors.append("Edge missing source or target")
            continue
        if src not in node_by_id or tgt not in node_by_id:
            errors.append(f"Edge references unknown node: {src} -> {tgt}")
            continue
        src_agent_id = node_by_id[src].get("agent_id")
        tgt_agent_id = node_by_id[tgt].get("agent_id")
        src_type = node_by_id[src].get("type")
        tgt_type = node_by_id[tgt].get("type")
        # Only check agent format compatibility when both endpoints are agents (not approval/slug)
        if src_agent_id is not None and tgt_agent_id is not None and src_type != "approval" and tgt_type != "approval":
            src_agent = agent_lookup.get(src_agent_id)
            tgt_agent = agent_lookup.get(tgt_agent_id)
            if src_agent and tgt_agent and not can_chain(src_agent, tgt_agent):
                errors.append(
                    f"Agent {tgt_agent_id} cannot accept output from agent {src_agent_id} (format mismatch)"
                )

    if not errors and _has_cycle(nodes, edges):
        errors.append("Chain contains a cycle")

    return errors


def _has_cycle(nodes: list[dict], edges: list[dict]) -> bool:
    """Detect cycle in directed graph using DFS."""
    node_ids = {n.get("id") for n in nodes if n.get("id")}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src and tgt and src in adj:
            adj[src].append(tgt)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in node_ids}

    def dfs(nid: str) -> bool:
        color[nid] = GRAY
        for child in adj.get(nid, []):
            if color.get(child) == GRAY:
                return True
            if color.get(child) == WHITE and dfs(child):
                return True
        color[nid] = BLACK
        return False

    for nid in node_ids:
        if color.get(nid) == WHITE and dfs(nid):
            return True
    return False

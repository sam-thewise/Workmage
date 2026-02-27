"""Celery tasks for agent execution."""
from app.worker.celery_app import celery_app
from app.worker.sandbox import run_agent_in_sandbox


def _topological_order(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Return node IDs in topological order. Entry nodes first."""
    node_ids = {n["id"] for n in nodes if n.get("id")}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src and tgt and src in adj:
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1
    queue = [nid for nid in node_ids if in_degree[nid] == 0]
    result: list[str] = []
    while queue:
        nid = queue.pop(0)
        result.append(nid)
        for child in adj.get(nid, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    return result


@celery_app.task(bind=True)
def run_chain_task(
    self,
    chain_id: int,
    user_input: str,
    model: str,
    api_key: str | None,
    buyer_id: int | None = None,
) -> dict:
    """Execute chain in topological order. Pass outputs to next agents."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.models.agent import Agent
    from app.models.chain import AgentChain
    from app.models.subscription import Subscription

    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        chain_result = db.execute(select(AgentChain).where(AgentChain.id == chain_id))
        chain = chain_result.scalar_one_or_none()
    if not chain:
        return {"status": "error", "content": "Chain not found"}

    defn = chain.definition
    nodes = {n["id"]: n for n in defn.get("nodes", []) if n.get("id")}
    edges = defn.get("edges", [])
    order = _topological_order(list(nodes.values()), edges)
    incoming: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in edges:
        tgt = e.get("target")
        src = e.get("source")
        if tgt and src:
            incoming[tgt].append(src)
    outputs: dict[str, str] = {}
    agg_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for nid in order:
        node = nodes.get(nid)
        if not node:
            continue
        agent_id = node.get("agent_id")
        if agent_id is None:
            continue
        with Session() as db:
            agent_result = db.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_result.scalar_one_or_none()
        if not agent:
            return {"status": "error", "content": f"Agent {agent_id} not found"}
        preds = incoming.get(nid, [])
        user_input_val = user_input if not preds else ""
        input_parts: list[dict] = []
        if preds:
            for p in preds:
                if p in outputs:
                    input_parts.append({"content": outputs[p], "format": "text/plain"})
        content, usage = run_agent_in_sandbox(
            manifest=agent.manifest,
            user_input=user_input_val,
            model=model,
            api_key=api_key,
            input_parts=input_parts if input_parts else None,
        )
        if usage:
            agg_usage["prompt_tokens"] = agg_usage.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
            agg_usage["completion_tokens"] = agg_usage.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)
        if isinstance(content, str) and any(
            x in content for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
        ):
            return {"status": "completed", "content": content, "usage": agg_usage}
        outputs[nid] = content or ""

    sink_nodes = [nid for nid in nodes if not any(e.get("source") == nid for e in edges)]
    final_content = "\n\n---\n\n".join(outputs.get(nid, "") for nid in sink_nodes) if sink_nodes else "\n\n".join(outputs.values())
    if buyer_id:
        with Session() as db:
            sub = db.execute(select(Subscription).where(Subscription.buyer_id == buyer_id)).scalar_one_or_none()
            if sub:
                sub.runs_used += 1
                db.commit()
    return {"status": "completed", "content": final_content, "usage": agg_usage}


@celery_app.task(bind=True)
def run_agent_task(
    self,
    agent_id: int,
    user_input: str,
    model: str,
    api_key: str | None,
    buyer_id: int | None = None,
) -> dict:
    """Execute agent in Docker sandbox. Increment runs_used if platform (buyer_id set)."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.models.agent import Agent
    from app.models.subscription import Subscription

    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        result = db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
    if not agent:
        return {"status": "error", "content": "Agent not found"}
    content, usage = run_agent_in_sandbox(
        manifest=agent.manifest,
        user_input=user_input,
        model=model,
        api_key=api_key,
    )
    if buyer_id:
        with Session() as db:
            sub = db.execute(select(Subscription).where(Subscription.buyer_id == buyer_id)).scalar_one_or_none()
            if sub:
                sub.runs_used += 1
                db.commit()
    return {"status": "completed", "content": content, "usage": usage}


@celery_app.task(bind=True)
def run_reference_liquidity_pipeline(
    self,
    network: str = "avalanche",
    from_block: str = "latest",
    to_block: str = "latest",
    token_contract: str | None = None,
) -> dict:
    """Reference capability: scan liquidity logs and optionally run source audit."""
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.models.action_runtime import ActionAnalysis, ActionSignal
    from app.services.contract_audit import run_static_audit_checks
    from app.services.contract_source import fetch_verified_source
    from app.services.liquidity_watcher import default_factory_addresses, fetch_pair_created_logs
    from app.worker.orchestration import make_checkpoint_key, normalize_job_result

    async def _run() -> dict:
        rpc_url = settings.AVALANCHE_FUJI_RPC_URL if network == "fuji" else settings.AVALANCHE_RPC_URL
        if not rpc_url:
            return normalize_job_result("error", error=f"Missing RPC URL for network `{network}`")
        factories = default_factory_addresses()
        if not factories:
            return normalize_job_result("error", error="No ACTIONS_FACTORY_ADDRESSES configured")
        logs = await fetch_pair_created_logs(
            rpc_url=rpc_url,
            factory_addresses=factories,
            from_block=from_block,
            to_block=to_block,
        )
        source_payload = None
        audit_result = None
        if token_contract:
            source_payload = await fetch_verified_source(token_contract)
            audit_result = run_static_audit_checks(source_payload)
        return normalize_job_result(
            "completed",
            data={
                "checkpoint_key": make_checkpoint_key(
                    "reference_liquidity_pipeline",
                    {"network": network, "from_block": from_block, "to_block": to_block, "token_contract": token_contract},
                ),
                "logs": logs[:50],
                "source": source_payload,
                "audit": audit_result,
            },
        )

    result = asyncio.run(_run())
    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        sig = ActionSignal(
            source="reference_liquidity_watcher",
            network=network,
            signal_type="pair_created",
            payload={"result_status": result.get("status"), "log_count": len(result.get("data", {}).get("logs", []))},
        )
        db.add(sig)
        db.flush()
        db.add(
            ActionAnalysis(
                signal_id=sig.id,
                analyzer="reference_liquidity_pipeline",
                status=result.get("status", "completed"),
                result=result,
                summary="Reference liquidity scan pipeline output",
            )
        )
        db.commit()
    return result

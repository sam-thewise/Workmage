"""Celery tasks for agent execution."""
from app.worker.celery_app import celery_app
from app.worker.sandbox import run_agent_in_sandbox


@celery_app.task(bind=True)
def process_mint_payments_for_network(self, network: str = "avalanche") -> dict:
    """Watch for MintPaymentReceived events and trigger mints to matching intents."""
    from app.services.mint_payment_watcher import process_mint_payments_for_network as _process

    return _process(network)


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


def _get_saved_content(db, user_id: int, slug: str) -> str:
    """Resolve saved output content by slug; fallback to UserPersonalityProfile for 'personality'."""
    from sqlalchemy import select
    from app.models.saved_output import SavedOutput
    from app.models.user_personality import UserPersonalityProfile
    res = db.execute(select(SavedOutput).where(SavedOutput.user_id == user_id, SavedOutput.slug == slug))
    row = res.scalar_one_or_none()
    if row and row.content:
        return row.content
    if slug == "personality":
        res = db.execute(select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user_id))
        profile = res.scalar_one_or_none()
        if profile and profile.profile_text:
            return profile.profile_text
    return ""


@celery_app.task(bind=True)
def run_chain_task(
    self,
    chain_id: int,
    user_input: str,
    model: str,
    api_key: str | None,
    buyer_id: int | None = None,
    personality_text: str | None = None,
    run_type: str | None = None,
    run_owner_id: int | None = None,
    github_token: str | None = None,
) -> dict:
    """Execute chain: run_type='setup' runs only setup-lane nodes and saves to slugs; else runs main lane (slug nodes contribute saved content)."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.models.agent import Agent
    from app.models.chain import AgentChain
    from app.models.subscription import Subscription
    from app.models.saved_output import SavedOutput

    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        chain_result = db.execute(select(AgentChain).where(AgentChain.id == chain_id))
        chain = chain_result.scalar_one_or_none()
    if not chain:
        return {"status": "error", "content": "Chain not found"}

    defn = chain.definition
    all_nodes = {n["id"]: n for n in defn.get("nodes", []) if n.get("id")}
    edges = defn.get("edges", [])

    if run_type == "setup":
        setup_node_ids = {nid for nid, n in all_nodes.items() if n.get("lane") == "setup"}
        if not setup_node_ids:
            return {"status": "completed", "content": "No setup nodes in this chain.", "usage": {}}
        setup_nodes = {nid: all_nodes[nid] for nid in setup_node_ids}
        setup_edges = [e for e in edges if e.get("source") in setup_node_ids and e.get("target") in setup_node_ids]
        order = _topological_order(list(setup_nodes.values()), setup_edges)
        incoming = {nid: [] for nid in setup_nodes}
        for e in setup_edges:
            tgt, src = e.get("target"), e.get("source")
            if tgt and src:
                incoming[tgt].append(src)
        outputs: dict[str, str] = {}
        agg_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        run_owner = run_owner_id or buyer_id
        for nid in order:
            node = setup_nodes.get(nid)
            if not node or node.get("type") == "slug":
                continue
            agent_id = node.get("agent_id")
            if agent_id is None:
                continue
            save_slug = node.get("save_to_slug")
            if not save_slug:
                continue
            with Session() as db:
                agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
            if not agent:
                return {"status": "error", "content": f"Agent {agent_id} not found"}
            preds = incoming.get(nid, [])
            user_input_val = user_input if not preds else ""
            input_parts = [{"content": outputs[p], "format": "text/plain"} for p in preds if p in outputs]
            content, usage = run_agent_in_sandbox(
                manifest=agent.manifest,
                user_input=user_input_val,
                model=model,
                api_key=api_key,
                input_parts=input_parts if input_parts else None,
                github_token=github_token,
            )
            if usage:
                agg_usage["prompt_tokens"] = agg_usage.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
                agg_usage["completion_tokens"] = agg_usage.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)
            if isinstance(content, str) and any(
                x in content for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
            ):
                return {"status": "completed", "content": content, "usage": agg_usage}
            outputs[nid] = content or ""
            if run_owner and (content or "").strip():
                with Session() as db:
                    res = db.execute(
                        select(SavedOutput).where(SavedOutput.user_id == run_owner, SavedOutput.slug == save_slug)
                    )
                    existing = res.scalar_one_or_none()
                    if existing:
                        existing.content = (content or "").strip()
                    else:
                        db.add(SavedOutput(user_id=run_owner, slug=save_slug, content=(content or "").strip()))
                    db.commit()
        return {"status": "completed", "content": f"Setup saved to slugs: {[setup_nodes[n].get('save_to_slug') for n in order if setup_nodes.get(n, {}).get('save_to_slug')]}", "usage": agg_usage}

    main_node_ids = {
        nid for nid, n in all_nodes.items()
        if n.get("lane") != "setup" and (n.get("type") == "slug" or n.get("agent_id") is not None)
    }
    if not main_node_ids:
        return {"status": "completed", "content": "No main-lane nodes. Add agents or slug nodes to the main lane, or run setup first.", "usage": {}}
    main_nodes = {nid: all_nodes[nid] for nid in main_node_ids}
    main_edges = [e for e in edges if e.get("source") in main_node_ids and e.get("target") in main_node_ids]
    order = _topological_order(list(main_nodes.values()), main_edges)
    incoming = {nid: [] for nid in main_nodes}
    for e in main_edges:
        tgt, src = e.get("target"), e.get("source")
        if tgt and src:
            incoming[tgt].append(src)
    outputs = {}
    agg_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    run_owner = run_owner_id or buyer_id

    for nid in order:
        node = main_nodes.get(nid)
        if not node:
            continue
        if node.get("type") == "slug":
            set_content = (node.get("content") or "").strip()
            if set_content:
                outputs[nid] = set_content
            else:
                slug_name = node.get("slug") or ""
                if run_owner and slug_name:
                    with Session() as db:
                        outputs[nid] = _get_saved_content(db, run_owner, slug_name)
                else:
                    outputs[nid] = ""
            continue
        agent_id = node.get("agent_id")
        if agent_id is None:
            continue
        with Session() as db:
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
        if not agent:
            return {"status": "error", "content": f"Agent {agent_id} not found"}
        preds = incoming.get(nid, [])
        user_input_val = user_input if not preds else ""
        input_parts = []
        for p in preds:
            if p in outputs and (outputs[p] or "").strip():
                input_parts.append({"content": outputs[p], "format": "text/plain"})
        input_from_slug = (node.get("input_from_slug") or "").strip()
        if input_from_slug and run_owner:
            with Session() as db:
                slug_content = _get_saved_content(db, run_owner, input_from_slug)
            if (slug_content or "").strip():
                input_parts.append({"content": slug_content.strip(), "format": "text/plain"})
        if personality_text and personality_text.strip():
            input_parts.append({
                "content": "User voice/beliefs (use for tone and stance in generated content):\n\n" + personality_text.strip(),
                "format": "text/plain",
            })
        content, usage = run_agent_in_sandbox(
            manifest=agent.manifest,
            user_input=user_input_val,
            model=model,
            api_key=api_key,
            input_parts=input_parts if input_parts else None,
            github_token=github_token,
        )
        if usage:
            agg_usage["prompt_tokens"] = agg_usage.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
            agg_usage["completion_tokens"] = agg_usage.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)
        if isinstance(content, str) and any(
            x in content for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:")
        ):
            return {"status": "completed", "content": content, "usage": agg_usage}
        outputs[nid] = content or ""

    sink_nodes = [nid for nid in main_nodes if not any(e.get("source") == nid for e in main_edges)]
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
    github_token: str | None = None,
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
        github_token=github_token,
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


def _parse_content_writer_output(content: str) -> list[tuple[str, str, str | None, str | None]]:
    """Parse X Content Writer output into list of (type, body, target_handle, target_url)."""
    import json
    import re
    items: list[tuple[str, str, str | None, str | None]] = []
    raw = (content or "").strip()
    # Try to extract JSON from markdown code block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if json_match:
        raw = json_match.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for p in data.get("posts") or []:
                body = p.get("body") if isinstance(p, dict) else str(p)
                if body:
                    items.append(("post", body, None, None))
            for r in data.get("replies") or []:
                if not isinstance(r, dict):
                    continue
                body = r.get("body") or r.get("text") or ""
                if body:
                    items.append(
                        (
                            "reply",
                            body,
                            r.get("target_handle"),
                            r.get("target_url"),
                        )
                    )
    except (json.JSONDecodeError, TypeError):
        pass
    if not items and (content or "").strip():
        items.append(("post", (content or "").strip(), None, None))
    return items


@celery_app.task(bind=True)
def run_x_authority_scheduled(self) -> dict:
    """Run the X Authority chain (if configured), parse output, and create ContentDraft rows for the user."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings
    from app.models.content_draft import ContentDraft
    from app.models.chain import AgentChain

    chain_id = getattr(settings, "X_AUTHORITY_CHAIN_ID", 0) or 0
    user_id = getattr(settings, "X_AUTHORITY_USER_ID", 0) or 0
    if not chain_id or not user_id:
        return {"status": "skipped", "reason": "X_AUTHORITY_CHAIN_ID or X_AUTHORITY_USER_ID not set"}

    user_input = getattr(settings, "X_AUTHORITY_INPUT", "") or "Latest trends and suggested posts to reply to."
    model = getattr(settings, "X_AUTHORITY_MODEL", "openai/gpt-5.2") or "openai/gpt-5.2"
    api_key = None
    if model.startswith("openai/"):
        api_key = getattr(settings, "OPENAI_API_KEY", "") or None
    elif model.startswith("anthropic/"):
        api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or None

    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        chain = db.execute(select(AgentChain).where(AgentChain.id == chain_id)).scalar_one_or_none()
    if not chain:
        return {"status": "error", "reason": "Chain not found"}

    from app.models.user_personality import UserPersonalityProfile
    personality_text = None
    with Session() as db:
        res = db.execute(
            select(UserPersonalityProfile).where(UserPersonalityProfile.user_id == user_id)
        )
        profile = res.scalar_one_or_none()
        if profile and (profile.profile_text or "").strip():
            personality_text = profile.profile_text.strip()

    result = run_chain_task.apply(
        args=[chain_id, user_input, model, api_key, user_id],
        kwargs={"personality_text": personality_text},
    ).get(timeout=600)

    if result.get("status") != "completed":
        return {"status": "error", "reason": result.get("content", "Chain run failed")}

    content = result.get("content") or ""
    parsed = _parse_content_writer_output(content)
    if not parsed:
        return {"status": "completed", "drafts_created": 0, "reason": "No posts/replies parsed"}

    Session = sessionmaker(bind=create_engine(settings.DATABASE_SYNC_URL), autocommit=False, autoflush=False)
    with Session() as db:
        for typ, body, target_handle, target_url in parsed:
            draft = ContentDraft(
                user_id=user_id,
                type=typ,
                body=body,
                target_handle=target_handle,
                target_url=target_url,
                source_chain_run_id="x_authority_scheduled",
                status="draft",
            )
            db.add(draft)
        db.commit()

    return {"status": "completed", "drafts_created": len(parsed)}

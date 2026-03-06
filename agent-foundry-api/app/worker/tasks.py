"""Celery tasks for agent execution."""
import logging

from celery import Task
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)
PROMPT_DEBUG_LIMIT = 4000


class ChainRunTask(Task):
    """Base task that persists run failure to chain_runs when task raises."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        run_id = kwargs.get("run_id")
        if run_id is not None:
            _update_chain_run(run_id, "error", error=str(exc))
        super().on_failure(exc, task_id, args, kwargs, einfo)


def _truncate_debug(value: str, limit: int = PROMPT_DEBUG_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...[truncated {len(value) - limit} chars]"


def _log_prompt_debug(
    *,
    phase: str,
    task_name: str,
    model: str,
    manifest_name: str,
    user_input: str,
    input_parts: list[dict] | None = None,
) -> None:
    """Log incoming prompt payload for debugging prompt plumbing."""
    lines = [
        f"[prompt-debug] phase={phase} task={task_name} model={model} manifest={manifest_name}",
        "[prompt-debug] user_input:",
        _truncate_debug((user_input or "").strip() or "(empty)"),
    ]
    if input_parts:
        lines.append(f"[prompt-debug] input_parts_count={len(input_parts)}")
        for idx, part in enumerate(input_parts, start=1):
            label = (part or {}).get("label") or f"part_{idx}"
            content = ((part or {}).get("content") or "").strip()
            lines.append(f"[prompt-debug] input_part[{idx}] label={label}")
            lines.append(_truncate_debug(content or "(empty)"))
    else:
        lines.append("[prompt-debug] input_parts_count=0")
    logger.info("\n".join(lines))


def _log_setup_graph_debug(
    *,
    all_nodes: dict[str, dict],
    setup_node_ids: set[str],
    included_node_ids: set[str],
    edges: list[dict],
    setup_edges: list[dict],
) -> None:
    """Log setup graph filtering so lane mismatches are obvious."""
    all_nodes_count = len(all_nodes)
    included_sorted = sorted(included_node_ids)
    setup_sorted = sorted(setup_node_ids)
    dropped_edges = []
    setup_edge_keys = {(e.get("source"), e.get("target")) for e in setup_edges}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if (src, tgt) in setup_edge_keys:
            continue
        if tgt in setup_node_ids:
            src_node = all_nodes.get(src, {}) if src else {}
            dropped_edges.append(
                f"{src}->{tgt} (src_type={src_node.get('type')} src_lane={src_node.get('lane')})"
            )
    logger.info(
        "[setup-debug] all_nodes=%s setup_node_ids=%s included_node_ids=%s setup_edges=%s dropped_to_setup=%s",
        all_nodes_count,
        setup_sorted,
        included_sorted,
        len(setup_edges),
        dropped_edges if dropped_edges else "[]",
    )


@celery_app.task(bind=True)
def process_mint_payments_for_network(self, network: str = "avalanche") -> dict:
    """Watch for MintPaymentReceived events and trigger mints to matching intents."""
    from app.services.mint_payment_watcher import process_mint_payments_for_network as _process

    return _process(network)


AUDIT_PREVIEW_MAX = 500


def _audit_entry(
    node_id: str,
    label: str,
    node_type: str,
    status: str,
    output_preview: str | None = None,
    usage: dict | None = None,
    duration_ms: int | None = None,
) -> dict:
    """Build one audit trail entry (serializable for JSONB)."""
    entry = {"node_id": node_id, "label": label, "type": node_type, "status": status}
    if output_preview is not None:
        entry["output_preview"] = output_preview[:AUDIT_PREVIEW_MAX] if output_preview else ""
    if usage:
        entry["usage"] = dict(usage)
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    return entry


def _update_chain_run(
    run_id: int | None,
    status: str,
    content: str | None = None,
    error: str | None = None,
    usage: dict | None = None,
    approval_id: int | None = None,
    summary: str | None = None,
    audit_trail: list | None = None,
) -> None:
    """Persist chain run outcome so the run is never stuck in queued/resuming."""
    if run_id is None:
        return
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.models.chain_run import ChainRun
    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        run = db.execute(select(ChainRun).where(ChainRun.id == run_id)).scalar_one_or_none()
        if run:
            run.status = status
            if content is not None:
                run.content = content
            if error is not None:
                run.error = error
            if usage is not None:
                run.usage = usage
            if approval_id is not None:
                run.approval_id = approval_id
            if summary is not None:
                run.summary = summary
            if audit_trail is not None:
                run.audit_trail = audit_trail
            db.commit()


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


def _get_workspace_secrets_for_chain(db, workspace_id: int | None, chain_id: int | None) -> dict[str, str]:
    """Load workspace (and optional per-chain) secrets, decrypt, return key_name -> value for sandbox env."""
    if workspace_id is None:
        return {}
    from sqlalchemy import select
    from app.models.workspace_secret import WorkspaceSecret
    from app.core.key_encryption import decrypt_api_key
    q = select(WorkspaceSecret).where(WorkspaceSecret.workspace_id == workspace_id)
    # Workspace-level (chain_id IS NULL) and optionally this chain's secrets
    q = q.where(
        (WorkspaceSecret.chain_id.is_(None)) | (WorkspaceSecret.chain_id == chain_id)
    )
    rows = db.execute(q).scalars().all()
    out: dict[str, str] = {}
    for s in rows:
        try:
            out[s.key_name] = decrypt_api_key(s.encrypted_value)
        except Exception:
            logger.warning("Failed to decrypt workspace secret key_name=%s", s.key_name, exc_info=True)
    return out


@celery_app.task(bind=True, base=ChainRunTask)
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
    run_id: int | None = None,
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
        workspace_secrets = _get_workspace_secrets_for_chain(
            db, getattr(chain, "workspace_id", None), chain_id
        ) if chain else {}
    if not chain:
        _update_chain_run(run_id, "error", error="Chain not found")
        return {"status": "error", "content": "Chain not found"}

    defn = chain.definition
    all_nodes = {n["id"]: n for n in defn.get("nodes", []) if n.get("id")}
    edges = defn.get("edges", [])

    if run_type == "setup":
        setup_node_ids = {nid for nid, n in all_nodes.items() if n.get("lane") == "setup"}
        if not setup_node_ids:
            _update_chain_run(run_id, "completed", content="No setup nodes in this chain.", usage={})
            return {"status": "completed", "content": "No setup nodes in this chain.", "usage": {}}
        # Allow slug feeders into setup nodes even if the slug node is on main lane.
        feeder_slug_ids = {
            e.get("source")
            for e in edges
            if e.get("target") in setup_node_ids
            and e.get("source") in all_nodes
            and all_nodes[e.get("source")].get("type") == "slug"
        }
        included_setup_ids = setup_node_ids | {nid for nid in feeder_slug_ids if nid}
        setup_nodes = {nid: all_nodes[nid] for nid in included_setup_ids}
        setup_edges = [e for e in edges if e.get("source") in included_setup_ids and e.get("target") in setup_node_ids]
        _log_setup_graph_debug(
            all_nodes=all_nodes,
            setup_node_ids=setup_node_ids,
            included_node_ids=included_setup_ids,
            edges=edges,
            setup_edges=setup_edges,
        )
        order = _topological_order(list(setup_nodes.values()), setup_edges)
        incoming = {nid: [] for nid in setup_nodes}
        for e in setup_edges:
            tgt, src = e.get("target"), e.get("source")
            if tgt and src:
                incoming[tgt].append(src)
        outputs: dict[str, str] = {}
        agg_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        audit_trail: list[dict] = []
        run_owner = run_owner_id or buyer_id
        for nid in order:
            node = setup_nodes.get(nid)
            if not node:
                continue
            if node.get("type") == "slug":
                # Setup-lane slug nodes can feed setup agents directly.
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
                slug_label = node.get("slug") or node.get("label") or nid
                audit_trail.append(_audit_entry(nid, f"Slug: {slug_label}", "slug", "ok"))
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
                _update_chain_run(run_id, "error", error=f"Agent {agent_id} not found", audit_trail=audit_trail)
                return {"status": "error", "content": f"Agent {agent_id} not found"}
            preds = incoming.get(nid, [])
            user_input_val = user_input if not preds else ""
            input_parts = [{"content": outputs[p], "format": "text/plain"} for p in preds if p in outputs]
            logger.info(
                "[setup-debug] node=%s preds=%s resolved_input_parts=%s output_keys=%s",
                nid,
                preds,
                len(input_parts),
                sorted(outputs.keys()),
            )
            label = (agent.manifest or {}).get("name") or f"Agent #{agent_id}"
            _log_prompt_debug(
                phase=f"chain_setup_node:{nid}",
                task_name="run_chain_task",
                model=model,
                manifest_name=label,
                user_input=user_input_val,
                input_parts=input_parts if input_parts else None,
            )
            import time
            t0 = time.perf_counter()
            from app.worker.sandbox import run_agent_in_sandbox
            content, usage = run_agent_in_sandbox(
                manifest=agent.manifest,
                user_input=user_input_val,
                model=model,
                api_key=api_key,
                input_parts=input_parts if input_parts else None,
                github_token=github_token,
                extra_env=workspace_secrets,
            )
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if usage:
                agg_usage["prompt_tokens"] = agg_usage.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
                agg_usage["completion_tokens"] = agg_usage.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)
            if isinstance(content, str) and any(
                x in content for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:", "404 Not Found")
            ):
                audit_trail.append(_audit_entry(nid, label, "agent", "error", output_preview=content, usage=usage, duration_ms=duration_ms))
                _update_chain_run(run_id, "error", error=content, usage=agg_usage, audit_trail=audit_trail)
                return {"status": "error", "content": content, "usage": agg_usage}
            audit_trail.append(_audit_entry(nid, label, "agent", "ok", output_preview=content or "", usage=usage, duration_ms=duration_ms))
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
        _update_chain_run(run_id, "completed", content=f"Setup saved to slugs: {[setup_nodes[n].get('save_to_slug') for n in order if setup_nodes.get(n, {}).get('save_to_slug')]}", usage=agg_usage, audit_trail=audit_trail)
        return {"status": "completed", "content": f"Setup saved to slugs: {[setup_nodes[n].get('save_to_slug') for n in order if setup_nodes.get(n, {}).get('save_to_slug')]}", "usage": agg_usage}

    main_node_ids = {
        nid for nid, n in all_nodes.items()
        if n.get("lane") != "setup"
        and (n.get("type") == "slug" or n.get("type") == "approval" or n.get("agent_id") is not None)
    }
    if not main_node_ids:
        _update_chain_run(run_id, "completed", content="No main-lane nodes. Add agents or slug nodes to the main lane, or run setup first.", usage={})
        return {"status": "completed", "content": "No main-lane nodes. Add agents or slug nodes to the main lane, or run setup first.", "usage": {}}
    main_nodes = {nid: all_nodes[nid] for nid in main_node_ids}
    main_edges = [e for e in edges if e.get("source") in main_node_ids and e.get("target") in main_node_ids]
    order = _topological_order(list(main_nodes.values()), main_edges)
    incoming = {nid: [] for nid in main_nodes}
    for e in main_edges:
        tgt, src = e.get("target"), e.get("source")
        if tgt and src:
            incoming[tgt].append(src)
    # Preload agent names for section labels (so downstream nodes get "Output: X Trend Scout" etc.)
    agent_ids_main = {n.get("agent_id") for n in main_nodes.values() if n.get("agent_id") is not None}
    agent_labels_by_id = {}
    if agent_ids_main:
        with Session() as db:
            agents_main = db.execute(select(Agent).where(Agent.id.in_(agent_ids_main))).scalars().all()
            for a in agents_main:
                agent_labels_by_id[a.id] = (a.manifest or {}).get("name") or f"Agent #{a.id}"
    outputs = {}
    agg_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    audit_trail_main: list[dict] = []
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
            slug_label = node.get("slug") or node.get("label") or nid
            audit_trail_main.append(_audit_entry(nid, f"Slug: {slug_label}", "slug", "ok"))
            continue
        if node.get("type") == "approval":
            preds = incoming.get(nid, [])
            summary_parts = []
            title = (node.get("title") or "").strip()
            if title:
                summary_parts.append(f"# {title}\n")
            msg = (node.get("message") or "").strip()
            if msg:
                summary_parts.append(f"{msg}\n")
            for p in preds:
                if p not in outputs:
                    continue
                pred_node = main_nodes.get(p)
                if pred_node and pred_node.get("type") == "slug":
                    label = f"Slug: {pred_node.get('slug', p)}"
                elif pred_node and pred_node.get("agent_id") is not None:
                    pred_agent_id = pred_node["agent_id"]
                    label = agent_labels_by_id.get(pred_agent_id, f"Agent #{pred_agent_id}")
                else:
                    label = f"Output {len(summary_parts) + 1}"
                content = (outputs.get(p) or "").strip()
                summary_parts.append(f"## {label}\n\n{content}\n")
            summary = "\n".join(summary_parts) if summary_parts else "No predecessor output."
            next_stages = []
            for e in main_edges:
                if e.get("source") != nid:
                    continue
                tgt = e.get("target")
                if tgt not in main_nodes:
                    continue
                tgt_node = main_nodes[tgt]
                if tgt_node.get("type") == "slug":
                    label = f"Slug: {tgt_node.get('slug', tgt)}"
                elif tgt_node.get("agent_id") is not None:
                    label = agent_labels_by_id.get(tgt_node["agent_id"], f"Agent #{tgt_node['agent_id']}")
                else:
                    label = tgt
                next_stages.append({"node_id": tgt, "label": label})
            state_snapshot = {
                "main_nodes": main_nodes,
                "main_edges": main_edges,
                "order": order,
                "run_owner_id": run_owner,
                "personality_text": personality_text,
            }
            with Session() as db:
                from app.models.chain_approval import ChainApprovalRequest
                approval = ChainApprovalRequest(
                    chain_id=chain_id,
                    user_id=run_owner or 0,
                    outputs=outputs,
                    approval_node_id=nid,
                    state_snapshot=state_snapshot,
                    status="pending",
                )
                db.add(approval)
                db.commit()
                db.refresh(approval)
                approval_id = approval.id
            approval_label = (node.get("title") or node.get("message") or "Approval").strip() or "Approval"
            audit_trail_main.append(_audit_entry(nid, approval_label, "approval", "reached", output_preview=summary))
            _update_chain_run(run_id, "awaiting_approval", approval_id=approval_id, summary=summary, usage=agg_usage, audit_trail=audit_trail_main)
            return {
                "status": "awaiting_approval",
                "approval_id": approval_id,
                "summary": summary,
                "next_stages": next_stages,
                "usage": agg_usage,
            }
        agent_id = node.get("agent_id")
        if agent_id is None:
            continue
        with Session() as db:
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
        if not agent:
            _update_chain_run(run_id, "error", error=f"Agent {agent_id} not found", audit_trail=audit_trail_main)
            return {"status": "error", "content": f"Agent {agent_id} not found"}
        agent_label = agent_labels_by_id.get(agent_id, f"Agent #{agent_id}")
        preds = incoming.get(nid, [])
        user_input_val = user_input if not preds else ""
        input_parts = []
        for p in preds:
            if p not in outputs:
                continue
            pred_node = main_nodes.get(p)
            if pred_node and pred_node.get("type") == "slug":
                label = f"Slug: {pred_node.get('slug', p)}"
            elif pred_node and pred_node.get("agent_id") is not None:
                pred_agent_id = pred_node["agent_id"]
                label = f"Output: {agent_labels_by_id.get(pred_agent_id, f'Agent #{pred_agent_id}')}"
            else:
                label = f"Input from chain ({len(input_parts) + 1})"
            content = (outputs[p] or "").strip()
            input_parts.append({"content": content, "format": "text/plain", "label": label})
        input_from_slug = (node.get("input_from_slug") or "").strip()
        if input_from_slug and run_owner:
            with Session() as db:
                slug_content = _get_saved_content(db, run_owner, input_from_slug)
            if (slug_content or "").strip():
                input_parts.append({
                    "content": slug_content.strip(),
                    "format": "text/plain",
                    "label": f"Slug: {input_from_slug}",
                })
        if personality_text and personality_text.strip():
            input_parts.append({
                "content": "User voice/beliefs (use for tone and stance in generated content):\n\n" + personality_text.strip(),
                "format": "text/plain",
                "label": "Personality / voice",
            })
        _log_prompt_debug(
            phase=f"chain_main_node:{nid}",
            task_name="run_chain_task",
            model=model,
            manifest_name=agent_label,
            user_input=user_input_val,
            input_parts=input_parts if input_parts else None,
        )
        import time
        t0 = time.perf_counter()
        from app.worker.sandbox import run_agent_in_sandbox
        content, usage = run_agent_in_sandbox(
            manifest=agent.manifest,
            user_input=user_input_val,
            model=model,
            api_key=api_key,
            input_parts=input_parts if input_parts else None,
            github_token=github_token,
            extra_env=workspace_secrets,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        if usage:
            agg_usage["prompt_tokens"] = agg_usage.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
            agg_usage["completion_tokens"] = agg_usage.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)
        if isinstance(content, str) and any(
            x in content for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:", "404 Not Found")
        ):
            audit_trail_main.append(_audit_entry(nid, agent_label, "agent", "error", output_preview=content, usage=usage, duration_ms=duration_ms))
            _update_chain_run(run_id, "error", error=content, usage=agg_usage, audit_trail=audit_trail_main)
            return {"status": "error", "content": content, "usage": agg_usage}
        audit_trail_main.append(_audit_entry(nid, agent_label, "agent", "ok", output_preview=content or "", usage=usage, duration_ms=duration_ms))
        outputs[nid] = content or ""

    sink_nodes = [nid for nid in main_nodes if not any(e.get("source") == nid for e in main_edges)]
    final_content = "\n\n---\n\n".join(outputs.get(nid, "") for nid in sink_nodes) if sink_nodes else "\n\n".join(outputs.values())
    if buyer_id:
        with Session() as db:
            sub = db.execute(select(Subscription).where(Subscription.buyer_id == buyer_id)).scalar_one_or_none()
            if sub:
                sub.runs_used += 1
                db.commit()
    _update_chain_run(run_id, "completed", content=final_content, usage=agg_usage, audit_trail=audit_trail_main)
    return {"status": "completed", "content": final_content, "usage": agg_usage}


@celery_app.task(bind=True, base=ChainRunTask)
def resume_chain_task(
    self,
    approval_id: int,
    user_input: str,
    model: str,
    api_key: str | None,
    buyer_id: int | None = None,
    personality_text: str | None = None,
    github_token: str | None = None,
    next_stage_node_id: str | None = None,
    run_id: int | None = None,
) -> dict:
    """Resume chain from an approval node. Loads state from ChainApprovalRequest and runs remaining nodes."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.models.agent import Agent
    from app.models.chain import AgentChain
    from app.models.chain_approval import ChainApprovalRequest
    from app.models.subscription import Subscription

    engine = create_engine(settings.DATABASE_SYNC_URL)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with Session() as db:
        approval = db.execute(
            select(ChainApprovalRequest).where(ChainApprovalRequest.id == approval_id)
        ).scalar_one_or_none()
        chain = db.execute(select(AgentChain).where(AgentChain.id == approval.chain_id)).scalar_one_or_none() if approval else None
        workspace_secrets = _get_workspace_secrets_for_chain(
            db, getattr(chain, "workspace_id", None), approval.chain_id if approval else None
        ) if chain else {}
    if not approval or approval.status != "pending":
        _update_chain_run(run_id, "error", error="Approval not found or already decided")
        return {"status": "error", "content": "Approval not found or already decided"}
    audit_trail_resume: list[dict] = []
    if run_id:
        with Session() as db:
            from app.models.chain_run import ChainRun
            run_row = db.execute(select(ChainRun).where(ChainRun.id == run_id)).scalar_one_or_none()
            if run_row and run_row.audit_trail:
                audit_trail_resume = list(run_row.audit_trail)
    outputs = dict(approval.outputs)
    state = approval.state_snapshot or {}
    main_nodes = state.get("main_nodes", {})
    main_edges = state.get("main_edges", [])
    order = state.get("order", [])
    run_owner = state.get("run_owner_id")
    personality_text = personality_text or state.get("personality_text") or ""
    approval_node_id = approval.approval_node_id
    if approval_node_id not in order:
        _update_chain_run(run_id, "error", error="Invalid approval state: node not in order", audit_trail=audit_trail_resume)
        return {"status": "error", "content": "Invalid approval state: node not in order"}
    idx = order.index(approval_node_id)
    next_order = order[idx + 1:]
    if not next_order:
        _update_chain_run(run_id, "completed", content="", usage={}, audit_trail=audit_trail_resume)
        return {"status": "completed", "content": "", "usage": {}}
    if next_stage_node_id:
        allowed = {next_stage_node_id}
        for nid in next_order:
            if _descendant_of(nid, next_stage_node_id, main_edges):
                allowed.add(nid)
        next_order = [nid for nid in next_order if nid in allowed]
    incoming = {nid: [] for nid in main_nodes}
    for e in main_edges:
        tgt, src = e.get("target"), e.get("source")
        if tgt and src:
            incoming[tgt].append(src)
    agent_ids_main = {n.get("agent_id") for n in main_nodes.values() if n.get("agent_id") is not None}
    agent_labels_by_id = {}
    if agent_ids_main:
        with Session() as db:
            agents_main = db.execute(select(Agent).where(Agent.id.in_(agent_ids_main))).scalars().all()
            for a in agents_main:
                agent_labels_by_id[a.id] = (a.manifest or {}).get("name") or f"Agent #{a.id}"
    agg_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    for nid in next_order:
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
            slug_label = node.get("slug") or node.get("label") or nid
            audit_trail_resume.append(_audit_entry(nid, f"Slug: {slug_label}", "slug", "ok"))
            continue
        if node.get("type") == "approval":
            continue
        agent_id = node.get("agent_id")
        if agent_id is None:
            continue
        with Session() as db:
            agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
        if not agent:
            _update_chain_run(run_id, "error", error=f"Agent {agent_id} not found", audit_trail=audit_trail_resume)
            return {"status": "error", "content": f"Agent {agent_id} not found"}
        agent_label = agent_labels_by_id.get(agent_id, f"Agent #{agent_id}")
        preds = incoming.get(nid, [])
        user_input_val = user_input if not preds else ""
        input_parts = []
        for p in preds:
            if p not in outputs:
                continue
            pred_node = main_nodes.get(p)
            if pred_node and pred_node.get("type") == "slug":
                label = f"Slug: {pred_node.get('slug', p)}"
            elif pred_node and pred_node.get("agent_id") is not None:
                pred_agent_id = pred_node["agent_id"]
                label = f"Output: {agent_labels_by_id.get(pred_agent_id, f'Agent #{pred_agent_id}')}"
            else:
                label = f"Input from chain ({len(input_parts) + 1})"
            content = (outputs[p] or "").strip()
            input_parts.append({"content": content, "format": "text/plain", "label": label})
        input_from_slug = (node.get("input_from_slug") or "").strip()
        if input_from_slug and run_owner:
            with Session() as db:
                slug_content = _get_saved_content(db, run_owner, input_from_slug)
            if (slug_content or "").strip():
                input_parts.append({
                    "content": slug_content.strip(),
                    "format": "text/plain",
                    "label": f"Slug: {input_from_slug}",
                })
        if personality_text and personality_text.strip():
            input_parts.append({
                "content": "User voice/beliefs (use for tone and stance in generated content):\n\n" + personality_text.strip(),
                "format": "text/plain",
                "label": "Personality / voice",
            })
        import time
        t0 = time.perf_counter()
        from app.worker.sandbox import run_agent_in_sandbox
        content, usage = run_agent_in_sandbox(
            manifest=agent.manifest,
            user_input=user_input_val,
            model=model,
            api_key=api_key,
            input_parts=input_parts if input_parts else None,
            github_token=github_token,
            extra_env=workspace_secrets,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        if usage:
            agg_usage["prompt_tokens"] = agg_usage.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
            agg_usage["completion_tokens"] = agg_usage.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)
        if isinstance(content, str) and any(
            x in content for x in ("Docker error", "Sandbox image", "Execution error", "No response file", "Error:", "404 Not Found")
        ):
            audit_trail_resume.append(_audit_entry(nid, agent_label, "agent", "error", output_preview=content, usage=usage, duration_ms=duration_ms))
            _update_chain_run(run_id, "error", error=content, usage=agg_usage, audit_trail=audit_trail_resume)
            return {"status": "error", "content": content, "usage": agg_usage}
        audit_trail_resume.append(_audit_entry(nid, agent_label, "agent", "ok", output_preview=content or "", usage=usage, duration_ms=duration_ms))
        outputs[nid] = content or ""
    next_sink_nodes = [nid for nid in next_order if not any(e.get("source") == nid for e in main_edges)]
    final_content = "\n\n---\n\n".join(outputs.get(nid, "") for nid in next_sink_nodes) if next_sink_nodes else "\n\n".join(outputs.get(nid, "") for nid in next_order if nid in outputs)
    if buyer_id:
        with Session() as db:
            sub = db.execute(select(Subscription).where(Subscription.buyer_id == buyer_id)).scalar_one_or_none()
            if sub:
                sub.runs_used += 1
                db.commit()
    with Session() as db:
        approval = db.execute(select(ChainApprovalRequest).where(ChainApprovalRequest.id == approval_id)).scalar_one_or_none()
        if approval:
            approval.status = "approved"
            from datetime import datetime
            approval.decided_at = datetime.utcnow()
            approval.decided_by_user_id = run_owner
            db.commit()
    _update_chain_run(run_id, "completed", content=final_content, usage=agg_usage, audit_trail=audit_trail_resume)
    return {"status": "completed", "content": final_content, "usage": agg_usage}


def _descendant_of(nid: str, ancestor: str, edges: list[dict]) -> bool:
    """True if nid is a descendant of ancestor in the graph."""
    if nid == ancestor:
        return True
    adj = {}
    for e in edges:
        src = e.get("source")
        if src not in adj:
            adj[src] = []
        adj[src].append(e.get("target"))
    from collections import deque
    q = deque([ancestor])
    seen = {ancestor}
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v == nid:
                return True
            if v not in seen:
                seen.add(v)
                q.append(v)
    return False


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
    _log_prompt_debug(
        phase="single_agent",
        task_name="run_agent_task",
        model=model,
        manifest_name=(agent.manifest or {}).get("name", f"Agent #{agent_id}"),
        user_input=user_input,
        input_parts=None,
    )
    from app.worker.sandbox import run_agent_in_sandbox
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

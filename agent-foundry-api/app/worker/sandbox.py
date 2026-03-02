"""Docker sandbox execution for agents."""
import json
import logging
import os
import shutil
import uuid
from pathlib import Path

import docker
from docker.errors import ContainerError, ImageNotFound

from app.core.config import settings

AGENT_IMAGE = os.environ.get("AGENT_SANDBOX_IMAGE", "agent-sandbox:latest")
AGENT_RUNS_DIR = os.environ.get("AGENT_RUNS_DIR", "/agent-runs")
AGENT_RUNS_VOLUME = os.environ.get("AGENT_RUNS_VOLUME", "agent_foundry_runs")
AGENT_SANDBOX_NETWORK = os.environ.get("AGENT_SANDBOX_NETWORK", "").strip()
AGENT_FORWARD_SANDBOX_LOGS = os.environ.get("AGENT_FORWARD_SANDBOX_LOGS", "1").strip() not in ("0", "false", "False")
SANDBOX_LOG_LIMIT = int(os.environ.get("AGENT_SANDBOX_LOG_LIMIT", "8000") or "8000")
DEFAULT_TIMEOUT = 300  # 5 min
DEFAULT_MEMORY = "512m"
DEFAULT_CPUS = 1.0

logger = logging.getLogger(__name__)


def _resolve_sandbox_network(client: docker.DockerClient) -> str | None:
    """Resolve which Docker network sandbox containers should join.

    Priority:
    1) AGENT_SANDBOX_NETWORK env override.
    2) Current worker container's first attached network (when running in Docker).
    """
    if AGENT_SANDBOX_NETWORK:
        return AGENT_SANDBOX_NETWORK
    hostname = (os.environ.get("HOSTNAME") or "").strip()
    if not hostname:
        return None
    try:
        this_container = client.containers.get(hostname)
        networks = ((this_container.attrs or {}).get("NetworkSettings") or {}).get("Networks") or {}
        if isinstance(networks, dict) and networks:
            return next(iter(networks.keys()))
    except Exception:
        return None
    return None


def run_agent_in_sandbox(
    manifest: dict,
    user_input: str,
    model: str,
    api_key: str | None,
    timeout_sec: int = DEFAULT_TIMEOUT,
    input_parts: list[dict] | None = None,
    github_token: str | None = None,
) -> tuple[str, dict | None]:
    """Run agent in Docker sandbox. Uses shared volume (accessible by host/daemon). Returns (content, usage_dict)."""
    job_id = str(uuid.uuid4())
    base_dir = Path(AGENT_RUNS_DIR) / job_id
    input_dir = base_dir / "input"
    output_dir = base_dir / "output"
    try:
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        request = {
            "manifest": manifest,
            "user_input": user_input,
            "model": model,
            "api_key": api_key,
        }
        if input_parts:
            request["input_parts"] = input_parts
        if github_token:
            request["github_token"] = github_token
        with open(input_dir / "request.json", "w") as f:
            json.dump(request, f, indent=2)
        env = {
            "AGENT_INPUT": f"/agent-runs/{job_id}/input",
            "AGENT_OUTPUT": f"/agent-runs/{job_id}/output",
        }
        if not api_key:
            if settings.OPENAI_API_KEY:
                env["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            if settings.ANTHROPIC_API_KEY:
                env["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY
        try:
            client = docker.from_env()
            sandbox_network = _resolve_sandbox_network(client)
            logger.info(
                "[sandbox] start job_id=%s image=%s network=%s model=%s manifest=%s",
                job_id,
                AGENT_IMAGE,
                sandbox_network or "<default>",
                model,
                (manifest or {}).get("name", "Agent"),
            )
            container = client.containers.run(
                AGENT_IMAGE,
                detach=True,
                mounts=[
                    docker.types.Mount(
                        type="volume",
                        source=AGENT_RUNS_VOLUME,
                        target="/agent-runs",
                    ),
                ],
                environment=env,
                mem_limit=DEFAULT_MEMORY,
                nano_cpus=int(DEFAULT_CPUS * 1e9),
                network=sandbox_network,
                remove=False,
            )
        except ImageNotFound:
            return (f"Sandbox image not found. Build it: docker build -t {AGENT_IMAGE} ./agent-sandbox", None)
        except docker.errors.APIError as e:
            return (f"Docker error: {e}", None)
        # Wait for completion (container runs and exits)
        try:
            container.wait(timeout=timeout_sec)
        except Exception as e:
            try:
                logs = container.logs().decode() if container else ""
                container.remove(force=True)
                return (f"Execution error: {e}. Agent logs: {logs[:500]}", None)
            except Exception:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
                return (f"Execution error: {e}", None)
        if AGENT_FORWARD_SANDBOX_LOGS:
            try:
                logs = container.logs().decode(errors="replace")
                if logs:
                    if len(logs) > SANDBOX_LOG_LIMIT:
                        logs = logs[:SANDBOX_LOG_LIMIT] + f"\n...[truncated {len(logs) - SANDBOX_LOG_LIMIT} chars]"
                    logger.info("[sandbox] container_logs job_id=%s\n%s", job_id, logs)
            except Exception:
                logger.warning("[sandbox] failed to read container logs for job_id=%s", job_id, exc_info=True)
        output_file = output_dir / "response.json"
        if not output_file.exists():
            try:
                logs = container.logs().decode()
                container.remove(force=True)
                return (f"No response file produced. Agent logs: {logs[:500]}", None)
            except Exception:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
                return ("No response file produced", None)
        try:
            container.remove(force=True)
        except Exception:
            pass
        with open(output_file) as f:
            resp = json.load(f)
        return (resp.get("content", ""), resp.get("usage"))
    finally:
        if base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)

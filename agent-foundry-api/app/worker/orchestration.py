"""Worker-side orchestration helpers for idempotent pipelines."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def make_checkpoint_key(name: str, payload: dict[str, Any]) -> str:
    """Create deterministic checkpoint key for dedupe/idempotency."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{name}:{canonical}".encode("utf-8")).hexdigest()
    return f"{name}:{digest}"


def normalize_job_result(status: str, data: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    """Normalize worker outputs for consistent orchestration behavior."""
    return {
        "status": status,
        "data": data or {},
        "error": error,
    }

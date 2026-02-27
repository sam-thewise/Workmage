"""OASF manifest validation service."""
import json
from typing import Any

import yaml

OASF_REQUIRED = {"name", "version", "schema_version", "description", "authors", "created_at", "skills"}
ALLOWED_ACTIONS = {"read", "analyze", "execute"}


class ManifestValidationError(Exception):
    """Raised when manifest validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


def parse_manifest(raw: str) -> dict[str, Any]:
    """Parse manifest from JSON or YAML string."""
    raw = raw.strip()
    try:
        if raw.startswith("{"):
            return json.loads(raw)
        return yaml.safe_load(raw) or {}
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ManifestValidationError(f"Invalid JSON/YAML: {e}") from e


def validate_oasf_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate manifest against OASF record schema and return extracted metadata."""
    if not isinstance(manifest, dict):
        raise ManifestValidationError("Manifest must be a JSON object", ["Manifest must be a JSON object"])

    errors: list[str] = []

    for field in OASF_REQUIRED:
        if field not in manifest or manifest[field] is None:
            errors.append(f"Missing required field: {field}")

    if manifest.get("authors") is not None and not isinstance(manifest["authors"], list):
        errors.append("'authors' must be a list")

    if manifest.get("skills") is not None and not isinstance(manifest["skills"], list):
        errors.append("'skills' must be a list")

    if manifest.get("version") is not None:
        v = manifest["version"]
        if not isinstance(v, str) or not v:
            errors.append("'version' must be a non-empty string")

    if manifest.get("schema_version") is not None:
        sv = manifest["schema_version"]
        if not isinstance(sv, str) or not sv:
            errors.append("'schema_version' must be a non-empty string")

    if manifest.get("input_formats") is not None:
        if not isinstance(manifest["input_formats"], list) or not all(
            isinstance(x, str) for x in manifest["input_formats"]
        ):
            errors.append("'input_formats' must be a list of strings")
    if manifest.get("output_formats") is not None:
        if not isinstance(manifest["output_formats"], list) or not all(
            isinstance(x, str) for x in manifest["output_formats"]
        ):
            errors.append("'output_formats' must be a list of strings")

    _validate_modules(manifest.get("modules"), errors)
    _validate_capabilities(manifest.get("capabilities"), errors)
    _validate_execution_policy(manifest.get("execution_policy"), errors)

    if errors:
        raise ManifestValidationError("Manifest validation failed", errors)

    return manifest


def _validate_modules(modules: Any, errors: list[str]) -> None:
    if modules is None:
        return
    if not isinstance(modules, list):
        errors.append("'modules' must be a list")
        return
    for idx, mod in enumerate(modules):
        if not isinstance(mod, dict):
            errors.append(f"'modules[{idx}]' must be an object")
            continue
        mtype = str(mod.get("type") or "").lower()
        if not mtype:
            errors.append(f"'modules[{idx}].type' is required")
            continue
        if mtype == "mcp":
            _validate_mcp_module(mod, idx, errors)


def _validate_mcp_module(mod: dict[str, Any], idx: int, errors: list[str]) -> None:
    if not mod.get("name"):
        errors.append(f"'modules[{idx}].name' is required for mcp modules")
    transport = str(mod.get("transport") or "http").lower()
    if transport not in {"http", "sse", "stdio"}:
        errors.append(f"'modules[{idx}].transport' must be one of http|sse|stdio")
    url = mod.get("url")
    if transport in {"http", "sse"}:
        if not isinstance(url, str) or not url.strip():
            errors.append(f"'modules[{idx}].url' is required for {transport} transport")
    elif transport == "stdio":
        command = mod.get("command")
        if not isinstance(command, str) or not command.strip():
            errors.append(f"'modules[{idx}].command' is required for stdio transport")
    timeout_sec = mod.get("timeout_sec")
    if timeout_sec is not None and (not isinstance(timeout_sec, int) or timeout_sec <= 0):
        errors.append(f"'modules[{idx}].timeout_sec' must be a positive integer")
    retries = mod.get("retries")
    if retries is not None and (not isinstance(retries, int) or retries < 0):
        errors.append(f"'modules[{idx}].retries' must be a non-negative integer")


def _validate_capabilities(capabilities: Any, errors: list[str]) -> None:
    if capabilities is None:
        return
    if not isinstance(capabilities, list):
        errors.append("'capabilities' must be a list")
        return
    for idx, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"'capabilities[{idx}]' must be an object")
            continue
        if not capability.get("name"):
            errors.append(f"'capabilities[{idx}].name' is required")
        module_type = capability.get("module_type")
        if module_type is not None and not isinstance(module_type, str):
            errors.append(f"'capabilities[{idx}].module_type' must be a string")
        permissions = capability.get("permissions")
        if permissions is not None:
            if not isinstance(permissions, list) or not all(isinstance(x, str) for x in permissions):
                errors.append(f"'capabilities[{idx}].permissions' must be a list of strings")
            elif not set(permissions).issubset(ALLOWED_ACTIONS):
                errors.append(
                    f"'capabilities[{idx}].permissions' supports only: {', '.join(sorted(ALLOWED_ACTIONS))}"
                )


def _validate_execution_policy(execution_policy: Any, errors: list[str]) -> None:
    if execution_policy is None:
        return
    if not isinstance(execution_policy, dict):
        errors.append("'execution_policy' must be an object")
        return
    bool_keys = ("simulation_required", "allow_unverified_contracts")
    for key in bool_keys:
        val = execution_policy.get(key)
        if val is not None and not isinstance(val, bool):
            errors.append(f"'execution_policy.{key}' must be a boolean")
    int_keys = ("max_spend_wei", "max_gas_wei", "cooldown_seconds")
    for key in int_keys:
        val = execution_policy.get(key)
        if val is not None and (not isinstance(val, int) or val < 0):
            errors.append(f"'execution_policy.{key}' must be a non-negative integer")
    for key in ("allowed_tokens", "allowed_routers"):
        val = execution_policy.get(key)
        if val is not None:
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                errors.append(f"'execution_policy.{key}' must be a list of strings")


def extract_manifest_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    """Extract display/metadata from validated manifest."""
    skills = manifest.get("skills") or []
    domains = manifest.get("domains") or []
    modules = manifest.get("modules") or []

    skill_names = [s.get("name", "") for s in skills if isinstance(s, dict)]
    domain_names = [d.get("name", "") for d in domains if isinstance(d, dict)]

    mcp_tools: list[str] = []
    for mod in modules:
        if isinstance(mod, dict) and mod.get("name", "").lower().find("mcp") >= 0:
            mcp_tools.append(mod.get("name", "mcp"))

    input_formats = manifest.get("input_formats")
    output_formats = manifest.get("output_formats")
    if input_formats is not None and isinstance(input_formats, list):
        input_formats = [str(x) for x in input_formats if isinstance(x, str)]
    else:
        input_formats = ["text/plain"]
    if output_formats is not None and isinstance(output_formats, list):
        output_formats = [str(x) for x in output_formats if isinstance(x, str)]
    else:
        output_formats = ["text/plain"]

    return {
        "name": manifest.get("name", ""),
        "description": manifest.get("description", ""),
        "skills": skill_names,
        "domains": domain_names,
        "input_formats": input_formats,
        "output_formats": output_formats,
        "capabilities": {
            "streaming": _has_capability(manifest, "streaming"),
            "multi_turn": _has_capability(manifest, "multi_turn"),
        },
        "mcp_tools": mcp_tools,
    }


def _has_capability(manifest: dict[str, Any], cap: str) -> bool:
    """Check if manifest declares a capability (modules or annotations)."""
    for mod in manifest.get("modules") or []:
        if isinstance(mod, dict) and cap.lower() in str(mod.get("name", "")).lower():
            return True
    ann = manifest.get("annotations") or {}
    return bool(ann.get(cap)) if isinstance(ann, dict) else False


def validate_and_parse(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse, validate OASF manifest and return (manifest, metadata)."""
    manifest = parse_manifest(raw)
    validate_oasf_manifest(manifest)
    metadata = extract_manifest_metadata(manifest)
    return manifest, metadata

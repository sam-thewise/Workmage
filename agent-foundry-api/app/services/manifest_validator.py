"""OASF manifest validation service."""
import json
from typing import Any

import yaml

OASF_REQUIRED = {"name", "version", "schema_version", "description", "authors", "created_at", "skills"}


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

    if errors:
        raise ManifestValidationError("Manifest validation failed", errors)

    return manifest


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

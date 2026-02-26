"""Agent runner - reads request from /input, runs via LiteLLM, writes to /output.
Supports MCP tools from manifest modules (see mcp_client)."""
import json
import os
import sys

# MCP tools from manifest can be wired here when modules declare MCP servers
from mcp_client import get_mcp_tools_from_manifest

INPUT_DIR = os.environ.get("AGENT_INPUT", "/input")
OUTPUT_DIR = os.environ.get("AGENT_OUTPUT", "/output")
INPUT_FILE = os.path.join(INPUT_DIR, "request.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "response.json")


def main():
    if not os.path.exists(INPUT_FILE):
        sys.stderr.write(f"Input not found: {INPUT_FILE}\n")
        sys.exit(1)
    with open(INPUT_FILE) as f:
        req = json.load(f)
    manifest = req.get("manifest", {})
    user_input = req.get("user_input", "")
    input_parts = req.get("input_parts", [])
    model = req.get("model", "openai/gpt-4")
    api_key = req.get("api_key")

    system_prompt = _build_system_prompt(manifest)
    user_content = user_input
    if input_parts:
        combined = [user_input] if user_input else []
        for part in input_parts:
            if isinstance(part, dict) and "content" in part:
                combined.append(str(part["content"]))
            elif isinstance(part, str):
                combined.append(part)
        user_content = "\n\n".join(combined) if combined else user_input
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        import litellm
        mcp_tools = get_mcp_tools_from_manifest(manifest)
        kwargs = {"model": model, "messages": messages}
        if api_key:
            kwargs["api_key"] = api_key
        if mcp_tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in mcp_tools]
        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content if response.choices else ""
        usage = getattr(response, "usage", None)
        usage_dict = None
        if usage:
            usage_dict = {"prompt_tokens": getattr(usage, "prompt_tokens", 0), "completion_tokens": getattr(usage, "completion_tokens", 0)}
    except Exception as e:
        content = f"Error: {str(e)}"
        usage_dict = None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"content": content, "usage": usage_dict}, f, indent=2)


def _build_system_prompt(manifest: dict) -> str:
    parts = [
        f"Agent: {manifest.get('name', 'Agent')}",
        f"Description: {manifest.get('description', '')}",
    ]
    skills = manifest.get("skills", [])
    if skills:
        skill_names = [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in skills]
        parts.append(f"Skills: {', '.join(skill_names)}")
    domains = manifest.get("domains", [])
    if domains:
        domain_names = [d.get("name", str(d)) if isinstance(d, dict) else str(d) for d in domains]
        parts.append(f"Domains: {', '.join(domain_names)}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    main()

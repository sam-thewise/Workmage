"""Agent runner - reads request from /input, runs via LiteLLM, writes to /output.
Supports MCP tools from manifest modules (see mcp_client)."""
import json
import os
import sys

# MCP tools from manifest can be wired here when modules declare MCP servers
from mcp_client import execute_mcp_tool, get_mcp_tools_from_manifest, parse_mcp_tool_name

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
    model = req.get("model", "openai/gpt-5.2")
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
        usage_dict = {"prompt_tokens": 0, "completion_tokens": 0}
        content = ""
        max_rounds = 8

        for _ in range(max_rounds):
            kwargs = {"model": model, "messages": messages}
            if api_key:
                kwargs["api_key"] = api_key
            if mcp_tools:
                kwargs["tools"] = [{"type": "function", "function": t} for t in mcp_tools]
            response = litellm.completion(**kwargs)
            if not response.choices:
                break

            message = response.choices[0].message
            usage = getattr(response, "usage", None)
            if usage:
                usage_dict["prompt_tokens"] += int(getattr(usage, "prompt_tokens", 0) or 0)
                usage_dict["completion_tokens"] += int(getattr(usage, "completion_tokens", 0) or 0)

            assistant_content = message.content or ""
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                content = assistant_content
                break

            assistant_message = {"role": "assistant", "content": assistant_content}
            if tool_calls:
                assistant_message["tool_calls"] = [tc.model_dump() if hasattr(tc, "model_dump") else tc for tc in tool_calls]
            messages.append(assistant_message)

            for tc in tool_calls:
                fn = tc.function if hasattr(tc, "function") else (tc.get("function") if isinstance(tc, dict) else None)
                call_id = tc.id if hasattr(tc, "id") else (tc.get("id") if isinstance(tc, dict) else "")
                fn_name = fn.name if hasattr(fn, "name") else (fn.get("name") if isinstance(fn, dict) else "")
                raw_args = fn.arguments if hasattr(fn, "arguments") else (fn.get("arguments") if isinstance(fn, dict) else "{}")
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception:
                    parsed_args = {}

                parsed = parse_mcp_tool_name(fn_name)
                if parsed:
                    server_key, _ = parsed
                    gh_token = req.get("github_token") if server_key == "github" else None
                    tool_result = execute_mcp_tool(manifest, fn_name, parsed_args, github_token=gh_token)
                else:
                    tool_result = f"Tool `{fn_name}` not registered in this runtime"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": fn_name,
                        "content": tool_result,
                    }
                )
        else:
            content = "Error: tool-calling iteration limit reached"

        if usage_dict["prompt_tokens"] == 0 and usage_dict["completion_tokens"] == 0:
            usage_dict = None
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

"""GitHub MCP proxy: list_commits, get_commit, get_file_contents.

Token is read from each request header (Authorization: token <value> or X-GitHub-Token).
No server-side token storage.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, Request, Response

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 15
MAX_PATCH_LENGTH = 8000
MAX_FILE_LENGTH = 50000


def _get_token(request: Request) -> str | None:
    """Extract GitHub token from Authorization or X-GitHub-Token header."""
    auth = request.headers.get("Authorization")
    if auth and (auth.startswith("token ") or auth.startswith("Bearer ")):
        return auth.split(" ", 1)[1].strip() or None
    return request.headers.get("X-GitHub-Token") or None


def _github_request(token: str, path: str, method: str = "GET") -> dict[str, Any] | list[Any]:
    """Call GitHub REST API; path is e.g. /repos/owner/repo/commits."""
    url = GITHUB_API_BASE + path if path.startswith("/") else GITHUB_API_BASE + "/" + path
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


# --- MCP tool definitions ---

TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": "list_commits",
        "description": "List commits for a repository. Returns commit sha, message, author, date for each.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner (user or org)."},
                "repo": {"type": "string", "description": "Repository name."},
                "branch": {"type": "string", "description": "Branch name (e.g. main). Default: default branch."},
                "per_page": {"type": "integer", "description": "Number of commits to return (max 100). Default 10."},
            },
            "required": ["owner", "repo"],
        },
    },
    {
        "name": "get_commit",
        "description": "Get a single commit by ref (sha or branch). Returns message, author, date, list of changed files, and optional patch summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner."},
                "repo": {"type": "string", "description": "Repository name."},
                "ref": {"type": "string", "description": "Commit SHA or branch/tag name."},
                "include_patch": {"type": "boolean", "description": "Include truncated patch/diff. Default false."},
            },
            "required": ["owner", "repo", "ref"],
        },
    },
    {
        "name": "get_file_contents",
        "description": "Get contents of a file in a repository (e.g. README.md). Use ref for branch or commit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner."},
                "repo": {"type": "string", "description": "Repository name."},
                "path": {"type": "string", "description": "File path (e.g. README.md, src/main.py)."},
                "ref": {"type": "string", "description": "Branch, tag, or commit SHA. Default: default branch."},
                "max_length": {"type": "integer", "description": "Max characters to return. Omit for full file."},
            },
            "required": ["owner", "repo", "path"],
        },
    },
]


def _handle_list_commits(token: str, args: dict[str, Any]) -> str:
    owner = (args.get("owner") or "").strip()
    repo = (args.get("repo") or "").strip()
    branch = (args.get("branch") or "").strip()
    per_page = min(100, max(1, int(args.get("per_page") or 10)))
    if not owner or not repo:
        return "owner and repo are required"
    path = f"/repos/{owner}/{repo}/commits?per_page={per_page}"
    if branch:
        path += f"&sha={urllib.parse.quote(branch)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            return f"GitHub API error: {err.get('message', body)}"
        except Exception:
            return f"GitHub API error: {e.code} {body}"
    except Exception as e:
        return f"Request failed: {e}"
    if not isinstance(data, list):
        return json.dumps(data)
    lines = []
    for c in data:
        sha = c.get("sha", "")[:7]
        commit = c.get("commit") or {}
        msg = (commit.get("message") or "").strip().split("\n")[0]
        author = (commit.get("author") or {}).get("name") or ""
        date = (commit.get("author") or {}).get("date") or ""
        lines.append(f"- {sha} {msg} (author: {author}, date: {date})")
    return "\n".join(lines) if lines else "No commits found."


def _handle_get_commit(token: str, args: dict[str, Any]) -> str:
    owner = (args.get("owner") or "").strip()
    repo = (args.get("repo") or "").strip()
    ref = (args.get("ref") or "").strip()
    include_patch = bool(args.get("include_patch"))
    if not owner or not repo or not ref:
        return "owner, repo, and ref are required"
    path = f"/repos/{owner}/{repo}/commits/{urllib.parse.quote(ref)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            return f"GitHub API error: {err.get('message', body)}"
        except Exception:
            return f"GitHub API error: {e.code} {body}"
    except Exception as e:
        return f"Request failed: {e}"
    if not isinstance(data, dict):
        return json.dumps(data)
    commit = data.get("commit") or {}
    msg = (commit.get("message") or "").strip()
    author = (commit.get("author") or {}).get("name") or ""
    date = (commit.get("author") or {}).get("date") or ""
    sha = data.get("sha", "")[:7]
    files = data.get("files") or []
    file_list = "\n".join([f"  - {f.get('filename', '')} ({f.get('status', '')})" for f in files])
    out = f"Commit: {sha}\nAuthor: {author}\nDate: {date}\n\nMessage:\n{msg}\n\nFiles changed:\n{file_list}"
    if include_patch and files:
        patches = []
        for f in files:
            patch = (f.get("patch") or "")[:MAX_PATCH_LENGTH]
            if patch:
                patches.append(f"--- {f.get('filename', '')}\n{patch}")
        if patches:
            out += "\n\nPatch (truncated):\n" + "\n---\n".join(patches)
    return out


def _handle_get_file_contents(token: str, args: dict[str, Any]) -> str:
    owner = (args.get("owner") or "").strip()
    repo = (args.get("repo") or "").strip()
    path_arg = (args.get("path") or "").strip()
    ref = (args.get("ref") or "").strip()
    max_length = args.get("max_length")
    if max_length is not None:
        max_length = max(0, int(max_length)) or MAX_FILE_LENGTH
    else:
        max_length = MAX_FILE_LENGTH
    if not owner or not repo or not path_arg:
        return "owner, repo, and path are required"
    path = f"/repos/{owner}/{repo}/contents/{urllib.parse.quote(path_arg)}"
    if ref:
        path += f"?ref={urllib.parse.quote(ref)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            return f"GitHub API error: {err.get('message', body)}"
        except Exception:
            return f"GitHub API error: {e.code} {body}"
    except Exception as e:
        return f"Request failed: {e}"
    if not isinstance(data, dict):
        return json.dumps(data)
    if data.get("type") != "file":
        return "Path is not a file (directory or symlink)."
    content_b64 = data.get("content")
    if not content_b64:
        return "No content in response."
    try:
        content = base64.b64decode(content_b64).decode("utf-8", errors="replace")
    except Exception as e:
        return f"Decode failed: {e}"
    if len(content) > max_length:
        content = content[:max_length] + "\n\n[... truncated]"
    return content


router = APIRouter(prefix="/mcp/github", tags=["mcp-github"])


def _handle_tools_list() -> dict[str, Any]:
    return {"tools": TOOLS_LIST}


def _handle_tools_call(token: str | None, params: dict[str, Any]) -> dict[str, Any]:
    if not token:
        return {"content": [{"type": "text", "text": "GitHub token required. Set Authorization: token <token> or X-GitHub-Token header."}]}
    name = params.get("name") or ""
    args = params.get("arguments") or {}
    if name == "list_commits":
        text = _handle_list_commits(token, args)
    elif name == "get_commit":
        text = _handle_get_commit(token, args)
    elif name == "get_file_contents":
        text = _handle_get_file_contents(token, args)
    else:
        text = f"Unknown tool: {name}"
    return {"content": [{"type": "text", "text": text}]}


@router.post("")
async def mcp_github_jsonrpc(request: Request) -> Response:
    """Handle MCP JSON-RPC: tools/list and tools/call. Token from request header."""
    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}),
            status_code=200,
            media_type="application/json",
        )
    method = body.get("method") if isinstance(body, dict) else None
    req_id = body.get("id") if isinstance(body, dict) else None
    params = body.get("params") if isinstance(body, dict) else {}
    token = _get_token(request)

    if method == "tools/list":
        result = _handle_tools_list()
    elif method == "tools/call":
        result = _handle_tools_call(token, params)
    else:
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }),
            status_code=200,
            media_type="application/json",
        )

    return Response(
        content=json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}),
        status_code=200,
        media_type="application/json",
    )


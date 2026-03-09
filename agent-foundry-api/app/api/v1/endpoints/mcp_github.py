"""GitHub MCP proxy: list_commits, get_commit, get_file_contents.

Token is read from each request header (Authorization: token <value> or X-GitHub-Token).
No server-side token storage.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

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


def _token_preview(token: str) -> str:
    """First 7 chars + … for verification (e.g. ghp_abc…). Safe to log."""
    if not token or not token.strip():
        return "(empty)"
    t = token.strip()
    return t[:7] + "…" if len(t) >= 7 else t[:2] + "…"


def _request_summary_for_debug(method: str, path: str, token: str) -> str:
    """Full request line (token redacted) so it appears in tool_result / worker logs."""
    url = GITHUB_API_BASE + path if path.startswith("/") else GITHUB_API_BASE + "/" + path
    headers_safe = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {_token_preview(token)}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return f" Request: {method} {url} | Headers: {json.dumps(headers_safe)}"


def _github_request(token: str, path: str, method: str = "GET") -> dict[str, Any] | list[Any]:
    """Call GitHub REST API; path is e.g. /repos/owner/repo/commits.
    Use same headers as GitHub docs / working curl: Bearer auth, application/vnd.github+json, Api-Version.
    """
    url = GITHUB_API_BASE + path if path.startswith("/") else GITHUB_API_BASE + "/" + path
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # Log full request with token redacted (4 chars) for debugging
    headers_safe = {k: f"Bearer {_token_preview(token)}" if k == "Authorization" else v for k, v in headers.items()}
    logger.info(
        "github_request method=%s url=%s headers=%s",
        method,
        url,
        json.dumps(headers_safe, sort_keys=True),
    )
    req = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


# --- MCP tool definitions ---

def _parse_owner_repo(args: dict[str, Any], owner_key: str = "owner", repo_key: str = "repo") -> tuple[str, str]:
    """Get owner and repo from args. Accepts owner/repo in repo (e.g. username/Workmage) if owner missing."""
    owner = (args.get(owner_key) or "").strip()
    repo = (args.get(repo_key) or "").strip()
    # Allow "owner/repo" in repo when owner is missing (e.g. "username/Workmage")
    if repo and "/" in repo and not owner:
        parts = repo.split("/", 1)
        owner, repo = (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (owner, repo)
    return owner, repo


TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": "list_commits",
        "description": "List commits for a repository. Returns commit sha, message, author, date for each. Pass owner and repo separately, or repo as 'owner/repo' (e.g. username/Workmage). Supports date range via since and until (ISO 8601, e.g. 2024-01-01T00:00:00Z).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner (user or org)."},
                "repo": {"type": "string", "description": "Repository name, or 'owner/repo' (e.g. username/Workmage)."},
                "branch": {"type": "string", "description": "Branch name (e.g. main). Default: default branch."},
                "per_page": {"type": "integer", "description": "Number of commits to return (max 100). Default 10."},
                "since": {"type": "string", "description": "Only commits after this date (ISO 8601, e.g. 2024-01-01T00:00:00Z)."},
                "until": {"type": "string", "description": "Only commits before this date (ISO 8601, e.g. 2024-12-31T23:59:59Z)."},
            },
            "required": ["repo"],
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
            "required": ["repo", "ref"],
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
            "required": ["repo", "path"],
        },
    },
    {
        "name": "get_compare",
        "description": "Compare two commits (base...head) and return full diff. For a single commit, use parent SHA as base and commit SHA as head. Use three dots between base and head (e.g. base...head).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner."},
                "repo": {"type": "string", "description": "Repository name."},
                "base": {"type": "string", "description": "Base commit SHA or branch (left side of ...)."},
                "head": {"type": "string", "description": "Head commit SHA or branch (right side of ...)."},
                "max_patch_length": {"type": "integer", "description": "Max characters per file patch. Omit for default (8000)."},
            },
            "required": ["repo", "base", "head"],
        },
    },
]


def _handle_list_commits(token: str, args: dict[str, Any]) -> str:
    owner, repo = _parse_owner_repo(args)
    branch = (args.get("branch") or "").strip()
    per_page = min(100, max(1, int(args.get("per_page") or 10)))
    since = (args.get("since") or "").strip()
    until = (args.get("until") or "").strip()
    if not owner or not repo:
        return "repo is required (e.g. 'owner/repo' like username/Workmage, or owner and repo separately)"
    path = f"/repos/{owner}/{repo}/commits?per_page={per_page}"
    if branch:
        path += f"&sha={urllib.parse.quote(branch)}"
    if since:
        path += f"&since={urllib.parse.quote(since)}"
    if until:
        path += f"&until={urllib.parse.quote(until)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            msg = err.get("message", body)
        except Exception:
            msg = body
        if e.code == 404:
            return (
                f"GitHub API 404: {msg}. Token sent (preview: {_token_preview(token)}). "
                "For private repos: (1) Use a classic PAT with 'repo' scope, or (2) For fine-grained PATs, add this repository and grant Contents read. "
                "Check owner/repo spelling and case (e.g. username/Workmage)."
                + "\n"
                + _request_summary_for_debug("GET", path, token)
            )
        return f"GitHub API error: {msg}"
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
    owner, repo = _parse_owner_repo(args)
    ref = (args.get("ref") or "").strip()
    include_patch = bool(args.get("include_patch"))
    if not owner or not repo:
        return "repo is required (e.g. 'owner/repo' or owner and repo separately)"
    if not ref:
        return "ref is required (commit SHA or branch name)"
    path = f"/repos/{owner}/{repo}/commits/{urllib.parse.quote(ref)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            msg = err.get("message", body)
        except Exception:
            msg = body
        if e.code == 404:
            return (
                f"GitHub API 404: {msg}. Token sent (preview: {_token_preview(token)}). "
                "For private repos, ensure your token has repo access and owner/repo/ref are correct."
                + "\n"
                + _request_summary_for_debug("GET", path, token)
            )
        return f"GitHub API error: {msg}"
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
    owner, repo = _parse_owner_repo(args)
    path_arg = (args.get("path") or "").strip()
    ref = (args.get("ref") or "").strip()
    max_length = args.get("max_length")
    if max_length is not None:
        max_length = max(0, int(max_length)) or MAX_FILE_LENGTH
    else:
        max_length = MAX_FILE_LENGTH
    if not owner or not repo:
        return "repo is required (e.g. 'owner/repo' or owner and repo separately)"
    if not path_arg:
        return "path is required (e.g. README.md)"
    path = f"/repos/{owner}/{repo}/contents/{urllib.parse.quote(path_arg)}"
    if ref:
        path += f"?ref={urllib.parse.quote(ref)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            msg = err.get("message", body)
        except Exception:
            msg = body
        if e.code == 404:
            return (
                f"GitHub API 404: {msg}. Token sent (preview: {_token_preview(token)}). "
                "For private repos, ensure your token has repo access and owner/repo/path are correct."
                + "\n"
                + _request_summary_for_debug("GET", path, token)
            )
        return f"GitHub API error: {msg}"
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


def _handle_get_compare(token: str, args: dict[str, Any]) -> str:
    owner, repo = _parse_owner_repo(args)
    base = (args.get("base") or "").strip()
    head = (args.get("head") or "").strip()
    max_patch_length = args.get("max_patch_length")
    if max_patch_length is not None:
        max_patch_length = max(1000, min(100000, int(max_patch_length)))
    else:
        max_patch_length = MAX_PATCH_LENGTH
    if not owner or not repo:
        return "repo is required (e.g. 'owner/repo' or owner and repo separately)"
    if not base or not head:
        return "base and head are required (e.g. parent_sha...commit_sha for single-commit diff)"
    path = f"/repos/{owner}/{repo}/compare/{urllib.parse.quote(base)}...{urllib.parse.quote(head)}"
    try:
        data = _github_request(token, path)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        try:
            err = json.loads(body)
            msg = err.get("message", body)
        except Exception:
            msg = body
        if e.code == 404:
            return (
                f"GitHub API 404: {msg}. Token sent (preview: {_token_preview(token)}). "
                "Check owner/repo/base/head."
                + "\n"
                + _request_summary_for_debug("GET", path, token)
            )
        return f"GitHub API error: {msg}"
    except Exception as e:
        return f"Request failed: {e}"
    if not isinstance(data, dict):
        return json.dumps(data)
    ahead_by = data.get("ahead_by", 0)
    behind_by = data.get("behind_by", 0)
    commits = data.get("commits") or []
    files = data.get("files") or []
    out_lines = [
        f"Compare: {base[:7]}...{head[:7]}",
        f"ahead_by: {ahead_by}, behind_by: {behind_by}",
        f"commits: {len(commits)}",
        f"files changed: {len(files)}",
        "",
    ]
    for f in files:
        filename = f.get("filename", "")
        status = f.get("status", "")
        patch = (f.get("patch") or "")[:max_patch_length]
        out_lines.append(f"--- {filename} ({status}) ---")
        if patch:
            out_lines.append(patch)
            if len(f.get("patch") or "") > max_patch_length:
                out_lines.append(f"\n[... truncated, max {max_patch_length} chars per file]")
        out_lines.append("")
    return "\n".join(out_lines).strip() or "No diff (empty comparison)"


router = APIRouter(prefix="/mcp/github", tags=["mcp-github"])


def _handle_tools_list() -> dict[str, Any]:
    return {"tools": TOOLS_LIST}


def _handle_tools_call(token: str | None, params: dict[str, Any]) -> dict[str, Any]:
    if not token:
        return {"content": [{"type": "text", "text": "GitHub token required. Token preview: (none). Add your GitHub token in app settings (e.g. Users → GitHub token). Private repos need a token with repo access."}]}
    name = params.get("name") or ""
    args = params.get("arguments") or {}
    if name == "list_commits":
        text = _handle_list_commits(token, args)
    elif name == "get_commit":
        text = _handle_get_commit(token, args)
    elif name == "get_file_contents":
        text = _handle_get_file_contents(token, args)
    elif name == "get_compare":
        text = _handle_get_compare(token, args)
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


# Example Agent Manifests for Chaining

These manifests demonstrate how `input_formats` and `output_formats` enable compatible agent chains.

## Compatibility Rule

An edge **A → B** is valid when `output_formats(A) ∩ input_formats(B) ≠ ∅`.

## Example Chain: URL Suggester → Web Summarizer → Report Writer

```
[URL Suggester]  →  [Web Summarizer]  →  [Report Writer]
output: text/plain   input: text/plain   input: text/plain
        text/url     output: text/plain  output: text/plain
                                              application/json
```

### Manifests

| Manifest | Input formats | Output formats | Chains with |
|----------|---------------|----------------|-------------|
| `url-suggester-manifest.json` | text/plain | text/plain, text/url | **Web Summarizer** (accepts text/plain, text/url) |
| `demo-agent-manifest.json` (root) | text/plain, text/url | text/plain | **URL Suggester** (outputs text/plain), **Report Writer** (accepts text/plain) |
| `report-writer-manifest.json` | text/plain | text/plain, application/json | **Web Summarizer** (outputs text/plain) |
| `avalanche-action-agent.json` | text/plain | text/plain, application/json | Demonstrates MCP + capability modules + execution policy |
| `web-summarizer-mcp-manifest.json` | text/plain, text/url | text/plain | Web Summarizer using the **built-in** MCP scrape tool (token-efficient markdown at `API_BASE/api/v1/mcp`) |
| `x-trend-scout-manifest.json` | text/plain | text/plain, application/json | X Trend Scout: twstalker URLs + scrape → trend report + reply targets |
| `x-content-writer-manifest.json` | text/plain | text/plain, application/json | Drafts posts and replies from trend report + beliefs |
| `x-reply-suggester-manifest.json` | text/plain | text/plain | Suggests 2–3 reply options for a single post |
| `x-personality-builder-manifest.json` | text/plain | text/plain | Builds personality/voice profile from pasted tweets or twstalker URL (MCP scrape); use in Setup lane and save to a slug, then feed slug to Content Writer |
| `x-content-writer-github-manifest.json` | text/plain | text/plain, application/json | X Content Writer **with GitHub**: uses your repo commits + messages (and optional file content) plus trend report + beliefs to draft posts about the tech you're working on. **Requires a GitHub token** (see below). |

### X Content Writer with GitHub

The **X Content Writer (with GitHub)** agent (`x-content-writer-github-manifest.json`) combines:

- **GitHub MCP tools**: `list_commits`, `get_commit`, `get_file_contents` so the agent can read your recent commits, messages, and repo files.
- **Web scrape**: same `scrape_as_markdown` tool for trend report URLs.
- **Content writer behaviour**: trend report + your beliefs → draft posts and replies (JSON or plain text).

**Input examples:** "Repo: owner/repo, branch main, last 5 commits" or "Use my last 3 commits from repo X" along with a trend report and your voice/beliefs. The agent uses commit messages and file/diff context to infer "tech I'm working on" and "about the tech," then drafts social posts.

**GitHub token requirement:** Users must add a GitHub token before running this agent (or any chain that includes it). The token is stored **encrypted at rest** (same pattern as LLM BYOK keys) and is **only sent at runtime** when starting a run or chain—never stored in manifests or logs. Add a token via `POST /api/v1/users/me/github-token` with body `{ "token": "ghp_..." }` (personal access token or fine-grained token with `repo` read scope). If a run or chain uses an agent with GitHub and the user has no token saved, the API returns 400 with a message to add a GitHub token in settings.

### X Authority workflow (Trend Scout → Content Writer)

Chain **X Trend Scout** → **X Content Writer** for founder authority-building: input expert handles, get trend report, then draft posts and replies. Create content drafts via `POST /api/v1/content-drafts/bulk` from the chain output; use the Drafts UI to edit and approve before copying to X.

### Web scraping tool (token-efficient markdown)

The API provides an MCP endpoint at `/api/v1/mcp` with one tool: `scrape_as_markdown`. It fetches a URL and returns main content as markdown (using trafilatura), so agents use fewer tokens. In your manifest, add a module with `type: "mcp"`, `transport: "http"`, and `url` set to your API base + `/api/v1/mcp` (e.g. `http://api:8000/api/v1/mcp` when the sandbox and API share a Docker network, or `https://your-api-host/api/v1/mcp` in production).

### Usage

1. Create agents in the Expert Dashboard using these manifests.
2. Publish and list them in the marketplace.
3. As a buyer, purchase the agents.
4. In **Chains**, add URL Suggester → Web Summarizer → Report Writer.
5. Run with input like: "Find URLs about Python async programming"

The chain will: suggest URLs → summarize each → write a structured report.

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
| `x-github-activity-manifest.json` | text/plain | text/plain | **GitHub scraper**: fetches repo commits, messages, optional file content; outputs a report for content creation. **Requires a GitHub token.** Chain into X Content Writer to support the import. |
| `x-content-writer-github-manifest.json` | text/plain | text/plain, application/json | X Content Writer that **accepts** a repo activity report (from X GitHub Activity or pasted) plus trend report + beliefs; has scrape tool for URLs. Use after GitHub Activity in a chain. |

### GitHub Activity (scraper) and Content Writer import

The GitHub-related flow is split into two agents so the scraper is separate and the Content Writer supports importing its output:

1. **X GitHub Activity** (`x-github-activity-manifest.json`) – **GitHub-only** scraper. Uses GitHub MCP tools (`list_commits`, `get_commit`, `get_file_contents`) to fetch your recent commits, messages, and optional file content. Outputs a **text/plain report** (e.g. recent commits, messages, tech/topics) designed to be chained into the Content Writer or pasted into your workflow. **Requires a GitHub token** (see below).

2. **X Content Writer (accepts GitHub report)** (`x-content-writer-github-manifest.json`) – Content writer with **no** GitHub module. It accepts trend report + beliefs + **optional repo activity report**. When it receives a repo activity report (from the previous node in a chain or pasted), it uses it to infer "tech I'm working on" and drafts posts. It has the scrape tool for URLs only. **Supports the import** of the GitHub Activity agent output when used in a chain.

**Chain for repo → posts:** **X GitHub Activity** → **X Content Writer (accepts GitHub report)**. Run the chain with input like "owner/repo, branch main, last 5 commits". The first agent produces the activity report; the second receives it as input and drafts posts and replies. You can also run X GitHub Activity alone and paste its output into X Content Writer (or the base X Content Writer) as needed.

**GitHub token requirement:** Users must add a GitHub token before running the **X GitHub Activity** agent (or any chain that includes it). The token is stored **encrypted at rest** (same pattern as LLM BYOK keys) and is **only sent at runtime** when starting a run or chain—never stored in manifests or logs. Add a token via `POST /api/v1/users/me/github-token` with body `{ "token": "ghp_..." }` (personal access token or fine-grained token with `repo` read scope). If a run or chain uses an agent with a GitHub module and the user has no token saved, the API returns 400 with a message to add a GitHub token in settings.

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

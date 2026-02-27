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

### Web scraping tool (token-efficient markdown)

The API provides an MCP endpoint at `/api/v1/mcp` with one tool: `scrape_as_markdown`. It fetches a URL and returns main content as markdown (using trafilatura), so agents use fewer tokens. In your manifest, add a module with `type: "mcp"`, `transport: "http"`, and `url` set to your API base + `/api/v1/mcp` (e.g. `http://api:8000/api/v1/mcp` when the sandbox and API share a Docker network, or `https://your-api-host/api/v1/mcp` in production).

### Usage

1. Create agents in the Expert Dashboard using these manifests.
2. Publish and list them in the marketplace.
3. As a buyer, purchase the agents.
4. In **Chains**, add URL Suggester → Web Summarizer → Report Writer.
5. Run with input like: "Find URLs about Python async programming"

The chain will: suggest URLs → summarize each → write a structured report.

# Workmage

AI agent marketplace and runner. Experts list OASF agents; Buyers discover, purchase, and run them with BYOK or platform LLM.

## Quick Start

```bash
cp .env.example .env   # edit if needed
make init              # build, start db, run migrations, start all services
make build-sandbox      # build agent sandbox image (required for runs)
```

Or manually:

```bash
docker compose up -d postgres redis
# wait for healthy
docker compose run --rm api alembic upgrade head
docker build -t agent-sandbox:latest ./agent-sandbox
docker compose up -d
```

- **Frontend**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Features

- **Expert Dashboard**: Create agents with OASF manifest, validate, publish
- **Marketplace**: Browse listed agents, filter by category
- **Chain Marketplace**: Experts can publish chain listings and buyers can purchase full chains
- **Purchase**: One-time payment (Stripe for paid agents/chains; free items instant)
- **Run Agent**: Execute in Docker sandbox; BYOK or platform LLM; subscription rate limits
- **API Keys**: Save OpenAI/Anthropic keys for BYOK runs
- **Cost estimates**: Per-token estimates for platform-hosted runs
- **MCP (Model Context Protocol)**: Agents can declare MCP servers in their manifest; the sandbox discovers tools and runs an iterative tool-call loop (e.g. Avalanche docs at `https://build.avax.network/api/mcp`)
- **Web scraping tool (token-efficient markdown)**: The API exposes an MCP endpoint that provides a `scrape_as_markdown` tool. It fetches a URL and returns main content as markdown using [trafilatura](https://github.com/adbar/trafilatura) (main-content extraction), so agents use fewer tokens than raw HTML. To use it, add an MCP module to your agent manifest with `type: "mcp"`, `transport: "http"`, and `url` set to your API base + `/api/v1/mcp` (e.g. `https://your-api-host/api/v1/mcp`, or `http://api:8000/api/v1/mcp` when the sandbox and API share a Docker network). Optional: set `MCP_PUBLIC_URL` in `.env` if the MCP endpoint is served from a different URL.
- **Action infrastructure**: Policy-controlled execution, agent wallets (ERC-6551–style), trust metadata (ERC-8004–aligned), simulation-first tx execution, and optional live broadcast after approval

## Makefile Commands

- `make up` - Start all services
- `make down` - Stop services
- `make logs` - Follow logs
- `make build` - Rebuild images
- `make build-sandbox` - Build agent sandbox image
- `make db-upgrade` - Run migrations
- `make db-migrate msg="..."` - Create new migration

## OAuth (Google, Facebook, X)

Optional: add social login by configuring OAuth credentials in `.env`:

1. **Google**: [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Create OAuth 2.0 Client ID (Web application). Add redirect URI: `http://localhost:8000/api/v1/auth/google/callback` (or your `API_PUBLIC_URL` + `/api/v1/auth/google/callback`).
2. **Facebook**: [Meta Developers](https://developers.facebook.com/) → Create App → Add Facebook Login product. Set redirect URI: `http://localhost:8000/api/v1/auth/facebook/callback`.
3. **X (Twitter)**: [X Developer Portal](https://developer.x.com/) → Create App → OAuth 2.0 → Set callback URL: `http://localhost:8000/api/v1/auth/x/callback`.

Set in `.env`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
X_CLIENT_ID=...
X_CLIENT_SECRET=...
API_PUBLIC_URL=http://localhost:8000  # Must be reachable from user's browser
```

## Commission & Stripe Connect

Sales use a **20% platform / 80% creator** split.

- **Agents**: 80% goes to the agent creator.
- **Chains**: 80% is split across included agent owners (deterministic equal split with cent rounding).

Experts must link Stripe (Dashboard -> Settings) before publishing paid listings.

## Stripe Webhooks (local testing)

Use the **Stripe CLI** to forward webhooks to your local API:

1. [Install Stripe CLI](https://stripe.com/docs/stripe-cli)
2. Run: `stripe login`
3. Run: `stripe listen --forward-to localhost:8000/webhooks/stripe`
4. Copy the webhook signing secret (`whsec_...`) and set `STRIPE_WEBHOOK_SECRET` in `.env`
5. Restart the API

**Webhook URL:** `http://localhost:8000/webhooks/stripe`

The endpoint handles `checkout.session.completed` and records purchases (including when the user never lands on the success page).

## Admin & Moderation

Experts submit agents and chains for approval; they appear in the marketplace only after an admin or moderator approves them.

### Setup admin account

Add your email(s) to `.env`:

```env
ADMIN_EMAILS=admin@example.com,superuser@example.com
```

On API startup, these users are promoted to `admin` role (they must already be registered).

### Moderator invites

Admins can invite users to become moderators (Admin Panel → Moderator Invites). The invite link can be shared; the user logs in with the invited email and accepts the invite.

### Moderation flow

1. Expert publishes -> listing status `pending_review`, awaits moderation
2. Admin/Mod reviews pending agents/chains at `/admin`, approves or rejects
3. Approved -> listing appears in marketplace
4. Rejected → expert sees reason, can edit and resubmit

Moderators can approve/reject/remove both agents and chains. Only admins can create moderator invites.

## Agent Chaining

Create chains of agents so output from one feeds into the next. Use **My Chains** (authenticated) to build and publish visual pipelines. Compatibility is enforced via `input_formats` and `output_formats` in manifests.

Example chainable manifests are in `example-manifests/`:

- `demo-agent-manifest.json` – Web Summarizer (input: text/plain, text/url; output: text/plain)
- `url-suggester-manifest.json` – Suggests URLs; chains into Web Summarizer
- `report-writer-manifest.json` – Structured report; receives from Web Summarizer

See `example-manifests/README.md` for the full chain diagram.

## Workflow Verification

Manual smoke tests:

1. Register expert account and create/publish an agent.
2. Create a chain from listed agents, set price/category/tags, and publish.
3. Verify chain appears in admin pending queue and not in public chain marketplace yet.
4. Approve chain as admin/moderator, verify it appears in `/marketplace/chains`.
5. Purchase chain as buyer and confirm Stripe redirect flow records purchase.
6. Run the purchased chain as buyer without purchasing every individual agent.

## Action infrastructure & MCP (env & config)

The platform supports agent-driven blockchain actions (e.g. Avalanche) behind policy and approval gates. Configure the following in `.env` as needed.

### Rollout and policy

| Variable | Default | Description |
|----------|---------|-------------|
| `ACTIONS_ENABLE_LIVE_TX` | `false` | Set to `true` to allow live transaction broadcast (keep `false` until signer and RPC are configured). |
| `ACTIONS_REQUIRE_APPROVAL_FOR_LIVE` | `true` | When `true`, live executions stay `pending_approval` until an admin/moderator approves; then use `POST /api/v1/action-infra/executions/{id}/broadcast`. |
| `ACTIONS_ENABLE_REFERENCE_CAPABILITIES` | `true` | Enables the reference liquidity-scan and contract-audit capability endpoints. |
| `ACTIONS_HTTP_TIMEOUT_SEC` | `15` | Timeout for outbound HTTP (RPC, Snowtrace, MCP). |
| `ACTIONS_DEFAULT_MAX_SPEND_WEI` | `100000000000000000` | Default max spend (wei) per execution when not overridden by manifest policy. |
| `ACTIONS_DEFAULT_MAX_GAS_WEI` | `3000000000000000` | Default max gas (wei) per execution. |
| `ACTIONS_MIN_TRUST_SCORE` | `20` | Minimum agent trust score for execution (ERC-8004–aligned). |
| `ACTIONS_FACTORY_ADDRESSES` | *(empty)* | Comma-separated DEX factory addresses for the reference liquidity watcher (e.g. Trader Joe / UniswapV2 factories). |

### Avalanche RPC and Snowtrace

| Variable | Default | Description |
|----------|---------|-------------|
| `AVALANCHE_RPC_URL` | *(empty)* | Avalanche C-Chain RPC URL (mainnet). Required for simulation/broadcast and reference liquidity scan. |
| `AVALANCHE_FUJI_RPC_URL` | *(empty)* | Fuji testnet RPC URL. |
| `SNOWTRACE_API_URL` | Routescan mainnet API | Etherscan-compatible API for contract source (e.g. `getsourcecode`) and verification. |
| `SNOWTRACE_FUJI_API_URL` | Routescan testnet API | Fuji testnet API for contract verification. |
| `SNOWTRACE_API_KEY` | *(empty)* | Optional API key for Snowtrace/Routescan (rate limits). |

### Signer (agent wallet broadcast)

**Never commit real private keys.** Use env only (or a secrets manager in production).

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_SIGNER_PRIVATE_KEY` | *(empty)* | Single hex private key used for all agent wallets (testing only). |
| `AGENT_SIGNER_KEYS` | *(empty)* | JSON object mapping wallet address to hex key, e.g. `{"0x1234...":"0xabc..."}`. Use for per-wallet keys. |
| `SIGNER_ENCRYPTION_KEY` | *(empty)* | Optional base64 Fernet key for encrypting platform-managed signer keys. If unset, keys are derived from `SECRET_KEY` + salt. Use to rotate signer encryption without changing `SECRET_KEY`. |

If both `AGENT_SIGNER_PRIVATE_KEY` and `AGENT_SIGNER_KEYS` are unset, you can still create agent wallets by using **managed wallets**: create a wallet with `managed: true` (or omit `wallet_address`) in `POST /api/v1/action-infra/wallets`. The platform will generate a keypair, store the encrypted private key in the database, and return the wallet address. Resolution order at broadcast: (1) env keys, (2) lookup by wallet address in the managed-keys table. If both env vars are set, `AGENT_SIGNER_KEYS` is used for lookup by wallet address; otherwise the single key is used for any wallet.

### ERC-6551 / ERC-8004 on Avalanche

ERC-6551 (token-bound accounts) and ERC-8004 (trustless agent identity/reputation/validation) are deployed on both **Fuji testnet** and **Avalanche mainnet**. No contract deployment is required; use the existing registry addresses (e.g. canonical ERC-6551 registry at `0x000000006551c19487814612e58FE06813775758`).

### MCP (manifest)

Agents declare MCP servers in the manifest `modules` array, e.g.:

```json
{
  "modules": [
    {
      "type": "mcp",
      "name": "avalanche_docs",
      "transport": "http",
      "url": "https://build.avax.network/api/mcp",
      "timeout_sec": 15,
      "retries": 2
    }
  ]
}
```

Optional: `key`, `headers` (for auth). The sandbox discovers tools via `tools/list` and executes via `tools/call` (HTTP JSON-RPC).

### API surface

- **Agents**: `GET /api/v1/agents/{id}` — agent details. `GET /api/v1/agents/{id}/agent-uri` — ERC-8004 AgentURI metadata (name, description, image, services) for on-chain identity.
- **Action infra**: `GET/POST /api/v1/action-infra/...` — health, executions, wallets, fund/withdraw intents, trust profiles, execute (simulation or live), request-approval, approve, broadcast. See API docs at `/docs`.
- **Reference capability**: `POST /api/v1/action-infra/reference/liquidity-scan` — requires `ACTIONS_ENABLE_REFERENCE_CAPABILITIES`, RPC URL, and `ACTIONS_FACTORY_ADDRESSES`.
- **Admin**: `GET/POST /api/v1/admin/agent-nft-contracts` — list or register deployed shared agent NFT contract per network. `POST .../agent-nft-contracts/{network}/verify` and `.../verify-status` — submit verification to Snowtrace and poll status.

### Agent metadata (ERC-8004 AgentURI)

`GET /api/v1/agents/{id}/agent-uri` returns JSON with `name`, `description`, `image` (from manifest if present), and `services` (API URL, agent-uri URL, MCP URL). Use this URL as the `agentURI` when registering with an ERC-8004 Identity Registry or as the `tokenURI` base for agent identity NFTs. Set `API_PUBLIC_URL` in `.env` so service URLs are absolute.

### Shared agent NFT contract (deploy and verify)

The platform can use a **shared agent identity NFT** contract (one per network) for minting agent NFTs and binding ERC-6551 TBAs. Deploy and verify it via the `contracts/agent-nft` project:

1. **Deploy**: In `contracts/agent-nft`, set `DEPLOYER_PRIVATE_KEY` and run `npm run deploy:fuji` or `npm run deploy:avalanche`. Save the contract address and deploy tx hash.
2. **Register**: `POST /api/v1/admin/agent-nft-contracts` with `network`, `chain_id`, `contract_address`, `deploy_tx_hash` (admin only).
3. **Verify on Snowtrace**: Run `npx hardhat verify --network fuji <address> "Workmage Agent Identity" "WMAI" "<base_uri>"` (or use admin `POST .../agent-nft-contracts/fuji/verify` with flattened source). Then `POST .../agent-nft-contracts/fuji/verify-status` to mark verified in the DB.

See `contracts/agent-nft/README.md` for full steps and env vars.

## Project Structure

- `agent-foundry-api/` - FastAPI backend (auth, agents, purchases, runs, chains, LLM, action-infra, admin agent-nft-contracts)
- `agent-foundry-frontend/` - Vue 3 + Vite frontend
- `agent-sandbox/` - Docker base image for agent execution (LiteLLM + MCP client)
- `contracts/agent-nft/` - Shared agent identity NFT (ERC-721): deploy and verify on Snowtrace (Fuji/mainnet)
- `example-manifests/` - Chainable OASF manifest examples and Avalanche action-infra demo

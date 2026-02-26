# Agent Foundry AI

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
- **Purchase**: One-time payment (Stripe for paid agents; free agents instant)
- **Run Agent**: Execute in Docker sandbox; BYOK or platform LLM; subscription rate limits
- **API Keys**: Save OpenAI/Anthropic keys for BYOK runs
- **Cost estimates**: Per-token estimates for platform-hosted runs

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

Agent sales use a **20% platform / 80% creator** split. Experts must link their Stripe account (Dashboard → Settings) before publishing paid agents. The agent setup page shows the commission breakdown when setting a price.

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

Experts submit agents for approval; they appear in the marketplace only after an admin or moderator approves them.

### Setup admin account

Add your email(s) to `.env`:

```env
ADMIN_EMAILS=admin@example.com,superuser@example.com
```

On API startup, these users are promoted to `admin` role (they must already be registered).

### Moderator invites

Admins can invite users to become moderators (Admin Panel → Moderator Invites). The invite link can be shared; the user logs in with the invited email and accepts the invite.

### Moderation flow

1. Expert publishes → agent status `pending_review`, awaits moderation
2. Admin/Mod views pending agents at `/admin`, approves or rejects
3. Approved → agent appears in marketplace
4. Rejected → expert sees reason, can edit and resubmit

Moderators can approve/reject agents and remove listed agents. Only admins can create moderator invites.

## Agent Chaining

Create chains of agents so output from one feeds into the next. Use **Chains** (authenticated) to build a visual pipeline. Compatibility is enforced via `input_formats` and `output_formats` in manifests.

Example chainable manifests are in `example-manifests/`:

- `demo-agent-manifest.json` – Web Summarizer (input: text/plain, text/url; output: text/plain)
- `url-suggester-manifest.json` – Suggests URLs; chains into Web Summarizer
- `report-writer-manifest.json` – Structured report; receives from Web Summarizer

See `example-manifests/README.md` for the full chain diagram.

## Project Structure

- `agent-foundry-api/` - FastAPI backend (auth, agents, purchases, runs, chains, LLM)
- `agent-foundry-frontend/` - Vue 3 + Vite frontend
- `agent-sandbox/` - Docker base image for agent execution
- `example-manifests/` - Chainable OASF manifest examples

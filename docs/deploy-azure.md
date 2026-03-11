# Deploy Agent Foundry to Azure (AKS)

One-page guide to deploy the stack to Azure Kubernetes Service with the master-branch GitHub Action.

## Prerequisites

**Set up Azure and GitHub first.** For a full, step-by-step setup of the Azure resources (resource group, ACR, AKS, optional Postgres/Redis) and the service principal via Azure CLI, see **[deploy-azure-infrastructure.md](deploy-azure-infrastructure.md)**.

In short you need:

- **Azure**: Subscription, AKS cluster, ACR (Azure Container Registry). AKS must be able to pull from ACR (use `az aks create --attach-acr` or see the infrastructure doc).
- **Database & Redis**: Use **Azure Database for PostgreSQL** and **Azure Cache for Redis** for production (set `USE_AZURE_SERVICES=true` in repo variables or secrets and create `workmage-secrets` with your connection strings), or use the in-cluster Postgres/Redis from the demo overlay (default).
- **GitHub repo secrets** (Settings → Secrets and variables → Actions):
  - `AZURE_CREDENTIALS`: JSON for a service principal (from `az ad sp create-for-rbac ... --sdk-auth` in the infrastructure doc).
  - `ACR_NAME`: ACR registry name (e.g. `myacr`).
  - `AKS_NAME`: AKS cluster name.
  - `AKS_RESOURCE_GROUP`: Resource group containing the AKS cluster.

You can use **OIDC** instead of a client secret: create an app registration, add a federated credential for the repo, and set `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`; then change the workflow to use `azure/login@v2` with `client-id`, `tenant-id`, `subscription-id` (and `id-token: write`).

## What gets deployed

- **API** (FastAPI): Service name must be `api` so in-cluster MCP URLs like `http://api:8000/api/v1/mcp` resolve from sandbox containers.
- **Worker** (Celery): Same image as API; runs with a Docker-in-Docker (DinD) sidecar so it can start agent-sandbox containers. Uses env `AGENT_SANDBOX_IMAGE` (set by the workflow to your ACR agent-sandbox image). The **base** kustomization does not include the worker (no privileged DinD there); the **demo** overlay adds a hardened worker with TLS, resource limits, and a NetworkPolicy. For production, use a separate overlay or a Kubernetes Job–based executor.
- **Beat** (Celery Beat): One replica; schedules periodic tasks (mint payments, X authority).
- **Twitter-automation**: MCP proxy; API uses `TWITTER_MCP_URL` pointing to `http://twitter-automation:8010/mcp/twitter`.
- **Frontend**: Vue app; build with the correct `VITE_API_URL` for the public API URL if needed.
- **Postgres & Redis**: In-cluster (base manifests) for demo, or use Azure managed services and override `DATABASE_URL` / `REDIS_URL` in the secret.

## Env vars and secrets

- **ConfigMap** (`workmage-config`): Non-secret env (e.g. `ENVIRONMENT`, `FRONTEND_URL`, `API_PUBLIC_URL`, `TWITTER_MCP_URL`). Override in the demo overlay or patch for your hostnames.
- **Secret** (`workmage-secrets`): Copy `k8s/base/secret.example.yaml` to `secret.yaml` (or create via `kubectl create secret generic`). Provide at least:
  - `DATABASE_URL`, `DATABASE_SYNC_URL`, `REDIS_URL`, `SECRET_KEY`
  - `POSTGRES_PASSWORD` if using in-cluster Postgres
  - Optional: Stripe keys, `TWITTER_BEARER_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.

Do not commit real secrets. For CI, create the secret once in the cluster (or use Azure Key Vault provider).

## AGENT_SANDBOX_IMAGE and Beat vs worker

- **AGENT_SANDBOX_IMAGE**: The worker must use the full ACR image so DinD can pull it (e.g. `myacr.azurecr.io/agent-sandbox:demo`). The GitHub Action sets this on the worker deployment after apply.
- **Beat vs worker**: Run one Beat deployment (scheduler) and one or more worker deployments (task execution). Same image; Beat command: `celery -A app.worker.celery_app beat ...`; worker command: `celery -A app.worker.celery_app worker ...`.

## Deploy flow (master branch)

1. Push to the **master** branch (or run the workflow manually via **Actions → Deploy to AKS (master branch) → Run workflow**).
2. The workflow: logs in to Azure, builds and pushes the four images to ACR (tag `:demo` and `:<sha>`), runs `kubectl apply -k k8s/demo` or `k8s/azure`, then sets the worker’s `AGENT_SANDBOX_IMAGE` to the ACR sandbox image.
3. Ensure the `agent-foundry` namespace and the `workmage-secrets` secret exist. For the **demo overlay** (`k8s/demo`), the example `workmage-secrets` secret is created by the manifests; when using the **base manifests** (`k8s/base`), you must create the `workmage-secrets` secret yourself (for example by copying `k8s/base/secret.example.yaml` to `secret.yaml` or via `kubectl create secret generic`).

## Post-deploy

- **Ingress & HTTPS**: The workflow installs NGINX Ingress and cert-manager. Point **demo.workmage.app** and **api-demo.workmage.app** DNS A records to the LoadBalancer IP (see job summary). cert-manager provisions a free Let's Encrypt TLS certificate automatically; use **https://demo.workmage.app**. To use a different domain, update `k8s/base/ingress.yaml`, and `k8s/base/configmap.yaml`, and set the issuer email in `k8s/base/letsencrypt-issuer.yaml`.
- **Migrations**: The workflow runs a one-off Job `db-migrate` on every deploy (Alembic `upgrade head`) before restarting the API, so the DB schema is created/updated automatically. To run migrations manually (e.g. after changing manifests without redeploying): delete the job and re-apply the overlay, or run locally with `DATABASE_SYNC_URL` set: `alembic -c agent-foundry-api/alembic.ini upgrade head`.

### Troubleshooting "Your connection is not private" (ERR_CERT_AUTHORITY_INVALID)

The browser shows this when the TLS certificate is missing, self-signed, or for the wrong domain. Check that Let's Encrypt issued the cert:

```powershell
kubectl get certificate -n workmage
kubectl describe certificate workmage-tls -n workmage
kubectl get challenges -n workmage
kubectl describe challenge -n workmage   # use the challenge name from the previous command
```

- **Certificate not Ready**: If `READY` is `False`, look at the Challenge events. Common causes:
  - **DNS not pointing to the cluster**: `demo.workmage.app` and `api-demo.workmage.app` must resolve to your ingress LoadBalancer IP. Check with `nslookup demo.workmage.app` from outside the cluster.
  - **Port 80 blocked**: Let's Encrypt validates via HTTP on port 80. Ensure your AKS LoadBalancer allows inbound 80 (NGINX Ingress does by default).
  - **404 on challenge**: If the challenge fails with 404, the HTTP-01 solver ingress may not be getting traffic; ensure no other proxy (e.g. Cloudflare) is in front with "Flexible SSL" or blocking `/.well-known/acme-challenge/`.
- **Force re-issue**: To retry issuance after fixing DNS or network: `kubectl delete certificate workmage-tls -n workmage` then re-run the workflow or `kubectl apply -k k8s/demo` (cert-manager will create a new Certificate from `k8s/base/certificate.yaml`).
- **Clear HSTS**: If you previously visited the site and the browser cached HSTS, clear it for the domain: Chrome → `chrome://net-internals/#hsts` → Delete domain `workmage.app`, then reload.
- **Storage**: The worker’s PVC `agent-runs` uses `ReadWriteMany`; on AKS you may need a storage class (e.g. Azure Files). Set `storageClassName` in `k8s/demo/worker-deployment.yaml` if required (demo overlay).

### Connection refused to Azure PostgreSQL

If the API logs show `ConnectionRefusedError` to the database, the Postgres firewall is likely blocking AKS. In Azure Portal go to your PostgreSQL Flexible Server → **Networking** → enable **Allow public access from any Azure service within Azure to this server** and save. Or add a firewall rule for your AKS outbound IP (get it with `kubectl run curl-debug --rm -it --restart=Never -n workmage --image=curlimages/curl -- curl -s ifconfig.me`).

## Local apply (without the Action)

```bash
az acr login --name <ACR_NAME>
az aks get-credentials --resource-group <AKS_RESOURCE_GROUP> --name <AKS_NAME>
cd k8s/demo
kustomize edit set image agent-foundry-api:latest=<ACR_LOGIN_SERVER>/agent-foundry-api:demo
kustomize edit set image agent-foundry-frontend:latest=<ACR_LOGIN_SERVER>/agent-foundry-frontend:demo
kustomize edit set image agent-sandbox:latest=<ACR_LOGIN_SERVER>/agent-sandbox:demo
kustomize edit set image twitter-automation-service:latest=<ACR_LOGIN_SERVER>/twitter-automation-service:demo
kubectl apply -k .
kubectl set env deployment/worker -n agent-foundry AGENT_SANDBOX_IMAGE=<ACR_LOGIN_SERVER>/agent-sandbox:demo
```

Replace `<ACR_LOGIN_SERVER>` with your ACR login server (e.g. `myacr.azurecr.io`).

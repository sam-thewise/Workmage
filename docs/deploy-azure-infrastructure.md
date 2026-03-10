# Azure infrastructure setup for Agent Foundry (AKS)

Step-by-step setup of Azure resources via Azure CLI so the **demo** branch GitHub Action can build, push, and deploy. Do this once before relying on the workflow.

## What you need on your machine

- **Azure CLI** ([install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)): `az --version`
- **kubectl** (optional for verification): [install](https://kubernetes.io/docs/tasks/tools/)
- **Azure subscription** with permissions to create resource groups, ACR, AKS, and (optional) managed Postgres/Redis

---

## 1. Sign in and pick a subscription

```bash
az login
az account set --subscription "<subscription-id-or-name>"
az account show --output table
```

Use the **Id** or **Name** from the table as your subscription. Note the **Tenant ID** (you’ll need it for GitHub secrets).

---

## 2. Set variables (use your own names/region)

```bash
# Change these to your values
export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
export TENANT_ID=$(az account show --query tenantId -o tsv)
export RESOURCE_GROUP=agent-foundry-demo
export LOCATION=eastus
export ACR_NAME=agentfoundrydemo    # 5–50 alphanumeric, globally unique
export AKS_NAME=agent-foundry-aks
export AKS_NODE_COUNT=2
export AKS_NODE_SIZE=Standard_B2s     # or Standard_D2s_v3 for production
```

**ACR name**: Must be globally unique (e.g. `myorg-agentfoundry-demo`). Only lowercase letters and numbers.

---

## 3. Create resource group

```bash
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output table
```

---

## 4. Create Azure Container Registry (ACR)

```bash
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled false \
  --output table
```

Get the login server (used later for image names and GitHub):

```bash
export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
echo "ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER"
```

**Optional (local Docker push)**: If you want to push from your machine without the workflow:

```bash
az acr update --name "$ACR_NAME" --admin-enabled true
az acr credential show --name "$ACR_NAME" --query "username" -o tsv
az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv
# docker login $ACR_LOGIN_SERVER  (use the username and password above)
```

Turn admin off again when you rely only on the workflow: `az acr update --name "$ACR_NAME" --admin-enabled false`.

---

## 5. Create AKS and attach ACR

This creates a cluster and gives its managed identity permission to pull from your ACR (no image pull secret needed).

```bash
az aks create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AKS_NAME" \
  --location "$LOCATION" \
  --node-count "$AKS_NODE_COUNT" \
  --node-vm-size "$AKS_NODE_SIZE" \
  --attach-acr "$ACR_NAME" \
  --generate-ssh-keys \
  --output table
```

**Attach ACR to an existing AKS** (if you created AKS without `--attach-acr`):

```bash
az aks update \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AKS_NAME" \
  --attach-acr "$ACR_NAME"
```

Verify:

```bash
az aks get-credentials --resource-group "$RESOURCE_GROUP" --name "$AKS_NAME" --overwrite-existing
kubectl get nodes
```

---

## 6. (Optional) Azure Database for PostgreSQL

Use this for production instead of in-cluster Postgres. You’ll put the connection string into the Kubernetes secret.

```bash
export PG_SERVER_NAME=agent-foundry-pg
export PG_ADMIN_USER=pgadmin
export PG_ADMIN_PASSWORD='<pick-a-strong-password>'
export PG_DB_NAME=agentfoundry
```

Create the server (Flexible Server, same region as AKS):

```bash
az postgres flexible-server create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$PG_SERVER_NAME" \
  --location "$LOCATION" \
  --admin-user "$PG_ADMIN_USER" \
  --admin-password "$PG_ADMIN_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16 \
  --storage-size 32 \
  --output table
```

Create the database and allow AKS to connect (replace with your AKS subnet if you use private networking):

```bash
az postgres flexible-server db create \
  --resource-group "$RESOURCE_GROUP" \
  --server-name "$PG_SERVER_NAME" \
  --database-name "$PG_DB_NAME"

# Allow Azure services (and optionally restrict to your AKS outbound IP later)
az postgres flexible-server firewall-rule create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$PG_SERVER_NAME" \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

Build the connection strings (replace with your server name if different):

```bash
export PG_HOST="${PG_SERVER_NAME}.postgres.database.azure.com"
export DATABASE_URL="postgresql+asyncpg://${PG_ADMIN_USER}:${PG_ADMIN_PASSWORD}@${PG_HOST}:5432/${PG_DB_NAME}?sslmode=require"
export DATABASE_SYNC_URL="postgresql://${PG_ADMIN_USER}:${PG_ADMIN_PASSWORD}@${PG_HOST}:5432/${PG_DB_NAME}?sslmode=require"
echo "DATABASE_URL is set (do not print it in logs)"
```

You’ll put `DATABASE_URL` and `DATABASE_SYNC_URL` into the Kubernetes secret and can remove in-cluster Postgres from the manifests.

---

## 7. (Optional) Azure Cache for Redis

Use this for production instead of in-cluster Redis.

```bash
export REDIS_NAME=agent-foundry-redis
```

```bash
az redis create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$REDIS_NAME" \
  --location "$LOCATION" \
  --sku Basic \
  --vm-size c0 \
  --output table
```

Get host and key:

```bash
export REDIS_HOST=$(az redis show --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query hostName -o tsv)
export REDIS_KEY=$(az redis list-keys --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query primaryKey -o tsv)
export REDIS_URL="redis://:${REDIS_KEY}@${REDIS_HOST}:6380"
echo "REDIS_URL is set (do not print it in logs)"
```

Use `REDIS_URL` in the Kubernetes secret. Default port for Azure Redis SSL is 6380; use 6379 if you disable SSL.

---

## 8. Service principal for GitHub Actions

The workflow needs a service principal that can: log in to Azure, push to ACR, and run `az aks get-credentials` and `kubectl apply`.

Create a principal and scope it to your resource group:

```bash
export SP_NAME=sp-agent-foundry-github

az ad sp create-for-rbac \
  --name "$SP_NAME" \
  --role contributor \
  --scopes "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  --sdk-auth
```

The output is a **single JSON object**. Copy it entirely; you will use it as `AZURE_CREDENTIALS` in GitHub.

Example shape (do not use this literally):

```json
{
  "clientId": "...",
  "clientSecret": "...",
  "subscriptionId": "...",
  "tenantId": "..."
}
```

**Narrower permissions (optional)**  
Instead of Contributor on the resource group, you can create custom roles or assign:

- **ACR**: `AcrPush` on the ACR resource
- **AKS**: `Azure Kubernetes Service Cluster User Role` on the AKS cluster (so the SP can get kubeconfig)

Then the workflow can only push images and deploy, not delete the resource group. For a quick demo, Contributor on the resource group is fine.

---

## 9. GitHub repository secrets and variables

In your repo: **Settings → Secrets and variables → Actions**.

### Secrets (required for the workflow)

| Secret name           | Value | Notes |
|-----------------------|-------|--------|
| `AZURE_CREDENTIALS`   | The **entire** JSON from step 8 (one line is fine) | Service principal for Azure login |
| `ACR_NAME`            | e.g. `agentfoundrydemo` | Your ACR name (step 2) |
| `AKS_NAME`            | e.g. `agent-foundry-aks` | Your AKS cluster name |
| `AKS_RESOURCE_GROUP`  | e.g. `agent-foundry-demo` | Resource group containing AKS |

**Adding each secret**

1. **Secrets and variables → Actions → New repository secret**.
2. Name: `AZURE_CREDENTIALS`, Value: paste the full JSON (no extra newlines).
3. Repeat for `ACR_NAME`, `AKS_NAME`, `AKS_RESOURCE_GROUP` with the values you used in step 2.

You can use **Variables** instead of secrets for `ACR_NAME`, `AKS_NAME`, and `AKS_RESOURCE_GROUP` if you prefer (they’re not sensitive). The workflow supports both (`vars.X || secrets.X`).

---

## 10. One-time Kubernetes secret (app config)

The workflow applies manifests from `k8s/demo`; the base includes an example secret. For a real deploy you should replace it with a secret that has your DB and Redis URLs.

**If you use in-cluster Postgres/Redis** (default in base): the example secret is enough for a first run. Ensure `k8s/base/kustomization.yaml` includes `secret.example.yaml` (or a copy you renamed).

**If you use Azure PostgreSQL and/or Azure Redis**: create the Kubernetes secret manually once (replace placeholders with the values from steps 6 and 7):

```bash
kubectl create namespace agent-foundry --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic agent-foundry-secrets -n agent-foundry \
  --from-literal=DATABASE_URL='<your-database-url>' \
  --from-literal=DATABASE_SYNC_URL='<your-database-sync-url>' \
  --from-literal=REDIS_URL='<your-redis-url>' \
  --from-literal=SECRET_KEY='<openssl-rand-hex-32>' \
  --from-literal=POSTGRES_PASSWORD='<postgres-password-if-using-in-cluster-pg>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

If you use the example secret from the manifests, the first `kubectl apply -k k8s/demo` will create/overwrite it. To avoid that, remove `secret.example.yaml` from `k8s/base/kustomization.yaml` and rely on the secret you created above.

---

## 11. Quick verification

- **Azure**
  - ACR: `az acr repository list --name "$ACR_NAME" --output table` (empty until first push).
  - AKS: `az aks show --resource-group "$RESOURCE_GROUP" --name "$AKS_NAME" --query provisioningState -o tsv` → `Succeeded`.
- **kubectl** (after `az aks get-credentials ...`): `kubectl get nodes` and `kubectl get ns agent-foundry`.

After the first run of the **Deploy to AKS (demo branch)** workflow you should see images in ACR and workloads in the `agent-foundry` namespace.

---

## Summary checklist

- [ ] Azure CLI installed and logged in; subscription and variables set (steps 1–2).
- [ ] Resource group created (step 3).
- [ ] ACR created; `ACR_NAME` and `ACR_LOGIN_SERVER` noted (step 4).
- [ ] AKS created with `--attach-acr`; `kubectl get nodes` works (step 5).
- [ ] (Optional) PostgreSQL Flexible Server and DB created; connection strings ready (step 6).
- [ ] (Optional) Azure Cache for Redis created; `REDIS_URL` ready (step 7).
- [ ] Service principal created; full JSON copied (step 8).
- [ ] GitHub repo secrets (and/or variables) set: `AZURE_CREDENTIALS`, `ACR_NAME`, `AKS_NAME`, `AKS_RESOURCE_GROUP` (step 9).
- [ ] Kubernetes secret `agent-foundry-secrets` created or left to the example from manifests (step 10).

Then push to the **demo** branch or run the workflow manually; see [deploy-azure.md](deploy-azure.md) for deploy flow and app-level config.

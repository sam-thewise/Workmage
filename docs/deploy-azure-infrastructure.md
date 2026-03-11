# Azure infrastructure setup for Agent Foundry (AKS)

Step-by-step setup of Azure resources via Azure CLI so the **demo** branch GitHub Action can build, push, and deploy. Do this once before relying on the workflow.

All commands are for **PowerShell** (Windows). Variables use `$env:VAR` so they work correctly in the same session.

## What you need on your machine

- **Azure CLI** ([install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)): `az --version`
- **kubectl** (optional for verification): [install](https://kubernetes.io/docs/tasks/tools/)
- **Azure subscription** with permissions to create resource groups, ACR, AKS, and (optional) managed Postgres/Redis

---

## 1. Sign in and pick a subscription

```powershell
az login
az account set --subscription "<subscription-id-or-name>"
az account show --output table
```

Use the **Id** or **Name** from the table as your subscription. Note the **Tenant ID** (you’ll need it for GitHub secrets).

---

## 2. Set variables (use your own names/region)

Run these in **PowerShell** and use the same session for steps 2–5 so the variables are available when you create the resource group, ACR, and AKS.

```powershell
# Change these to your values
$env:SUBSCRIPTION_ID = (az account show --query id -o tsv)
$env:TENANT_ID = (az account show --query tenantId -o tsv)
$env:RESOURCE_GROUP = "agent-foundry-demo"
$env:LOCATION = "eastus"
$env:ACR_NAME = "agentfoundrydemo"   # 5–50 alphanumeric, globally unique
$env:AKS_NAME = "agent-foundry-aks"
$env:AKS_NODE_COUNT = "2"
$env:AKS_NODE_SIZE = "Standard_DC2s_v3"  # 2 vCPU, 16 GiB; use Standard_M8-2ms if you prefer general-purpose over confidential computing
```

**ACR name**: Must be globally unique (e.g. `myorg-agentfoundry-demo`). Only lowercase letters and numbers.

---

## 3. Create resource group

```powershell
az group create `
  --name $env:RESOURCE_GROUP `
  --location $env:LOCATION `
  --output table
```

---

## 4. Create Azure Container Registry (ACR)

```powershell
az acr create `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:ACR_NAME `
  --sku Basic `
  --admin-enabled false `
  --output table
```

Get the login server (used later for image names and GitHub):

```powershell
$env:ACR_LOGIN_SERVER = (az acr show --name $env:ACR_NAME --resource-group $env:RESOURCE_GROUP --query loginServer -o tsv)
Write-Host "ACR_LOGIN_SERVER=$env:ACR_LOGIN_SERVER"
```

**Optional (local Docker push)**: If you want to push from your machine without the workflow:

```powershell
az acr update --name $env:ACR_NAME --admin-enabled true
az acr credential show --name $env:ACR_NAME --query "username" -o tsv
az acr credential show --name $env:ACR_NAME --query "passwords[0].value" -o tsv
# docker login $env:ACR_LOGIN_SERVER  (use the username and password above)
```

Turn admin off again when you rely only on the workflow: `az acr update --name $env:ACR_NAME --admin-enabled false`.

---

## 5. Create AKS and attach ACR

This creates a cluster and gives its managed identity permission to pull from your ACR (no image pull secret needed).

```powershell
az aks create `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:AKS_NAME `
  --location $env:LOCATION `
  --node-count $env:AKS_NODE_COUNT `
  --node-vm-size $env:AKS_NODE_SIZE `
  --attach-acr $env:ACR_NAME `
  --generate-ssh-keys `
  --output table
```

**Attach ACR to an existing AKS** (if you created AKS without `--attach-acr`):

```powershell
az aks update `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:AKS_NAME `
  --attach-acr $env:ACR_NAME
```

Verify:

```powershell
az aks get-credentials --resource-group $env:RESOURCE_GROUP --name $env:AKS_NAME --overwrite-existing
kubectl get nodes
```

---

## 6. (Optional) Azure Database for PostgreSQL

Use this for production instead of in-cluster Postgres. You’ll put the connection string into the Kubernetes secret.

```powershell
$env:PG_SERVER_NAME = "agent-foundry-pg"
$env:PG_ADMIN_USER = "pgadmin"
$env:PG_ADMIN_PASSWORD = "<pick-a-strong-password>"
$env:PG_DB_NAME = "agentfoundry"
```

Create the server (Flexible Server, same region as AKS). Use **General Purpose** with `Standard_D2s_v3` (2 vCore); Burstable (B1ms) is often not available in subscriptions. If this SKU is restricted, list options with `az postgres flexible-server list-skus --location $env:LOCATION -o table` and pick an available General Purpose SKU.

```powershell
az postgres flexible-server create `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:PG_SERVER_NAME `
  --location $env:LOCATION `
  --admin-user $env:PG_ADMIN_USER `
  --admin-password $env:PG_ADMIN_PASSWORD `
  --sku-name Standard_D2s_v3 `
  --tier GeneralPurpose `
  --version 16 `
  --storage-size 32 `
  --output table
```

Create the database and allow AKS to connect (replace with your AKS subnet if you use private networking):

```powershell
az postgres flexible-server db create `
  --resource-group $env:RESOURCE_GROUP `
  --server-name $env:PG_SERVER_NAME `
  --database-name $env:PG_DB_NAME

# Allow Azure services (and optionally restrict to your AKS outbound IP later)
az postgres flexible-server firewall-rule create `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:PG_SERVER_NAME `
  --rule-name AllowAzureServices `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0
```

Build the connection strings (replace with your server name if different):

```powershell
$env:PG_HOST = "$($env:PG_SERVER_NAME).postgres.database.azure.com"
$env:DATABASE_URL = "postgresql+asyncpg://$($env:PG_ADMIN_USER):$($env:PG_ADMIN_PASSWORD)@$($env:PG_HOST):5432/$($env:PG_DB_NAME)?sslmode=require"
$env:DATABASE_SYNC_URL = "postgresql://$($env:PG_ADMIN_USER):$($env:PG_ADMIN_PASSWORD)@$($env:PG_HOST):5432/$($env:PG_DB_NAME)?sslmode=require"
Write-Host "DATABASE_URL is set (do not print it in logs)"
```

You’ll put `DATABASE_URL` and `DATABASE_SYNC_URL` into the Kubernetes secret and can remove in-cluster Postgres from the manifests.

---

## 7. (Optional) Azure Cache for Redis

Use this for production instead of in-cluster Redis.

```powershell
$env:REDIS_NAME = "agent-foundry-redis"
```

```powershell
az redis create `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:REDIS_NAME `
  --location $env:LOCATION `
  --sku Basic `
  --vm-size c0 `
  --output table
```

Get host and key:

```powershell
$env:REDIS_HOST = (az redis show --resource-group $env:RESOURCE_GROUP --name $env:REDIS_NAME --query hostName -o tsv)
$env:REDIS_KEY = (az redis list-keys --resource-group $env:RESOURCE_GROUP --name $env:REDIS_NAME --query primaryKey -o tsv)
$env:REDIS_URL = "redis://:$($env:REDIS_KEY)@$($env:REDIS_HOST):6380"
Write-Host "REDIS_URL is set (do not print it in logs)"
```

Use `REDIS_URL` in the Kubernetes secret. Default port for Azure Redis SSL is 6380; use 6379 if you disable SSL.

---

## 8. Service principal for GitHub Actions

The workflow needs a service principal that can: log in to Azure, push to ACR, and run `az aks get-credentials` and `kubectl apply`.

Create a principal and scope it to your resource group:

```powershell
$env:SP_NAME = "sp-agent-foundry-github"

az ad sp create-for-rbac `
  --name $env:SP_NAME `
  --role contributor `
  --scopes "/subscriptions/$($env:SUBSCRIPTION_ID)/resourceGroups/$($env:RESOURCE_GROUP)" `
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

Run the commands below from **any directory** (e.g. repo root). They use `kubectl` against whichever cluster is current in your kubeconfig—ensure you’ve run step 5 (`az aks get-credentials ...`) so the context points at your AKS cluster.

**If you use in-cluster Postgres/Redis** (default): Leave `USE_AZURE_SERVICES` unset. The workflow uses `k8s/demo`, which provides a secretGenerator and in-cluster Postgres/Redis. No manual secret needed.

**If you use Azure PostgreSQL and/or Azure Redis**: Set the GitHub variable `USE_AZURE_SERVICES` to `true`. The workflow will use `k8s/azure`, which excludes in-cluster Postgres and Redis and uses your Azure services. Create the Kubernetes secret manually once (replace placeholders with the values from steps 6 and 7).

- **DATABASE_URL / DATABASE_SYNC_URL**: From step 6; they already contain your Azure PostgreSQL admin user and password (the one you set as `$env:PG_ADMIN_PASSWORD`). The app uses these to talk to Azure Postgres—no separate “Postgres password” field for the app.
- **REDIS_URL**: From step 7 (Azure Redis).
- **SECRET_KEY**: Generate a random value (see below).

Generate a random value for `SECRET_KEY` (used for session/signing). In PowerShell: `[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }) -as [byte[]])` or use OpenSSL if installed: `openssl rand -hex 32`. Use that string as the `SECRET_KEY` value below.

```powershell
kubectl create namespace workmage --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic workmage-secrets -n workmage `
  --from-literal=DATABASE_URL='<from-step-6>' `
  --from-literal=DATABASE_SYNC_URL='<from-step-6>' `
  --from-literal=REDIS_URL='<from-step-7>' `
  --from-literal=SECRET_KEY='<paste-generated-key-here>' `
  --dry-run=client -o yaml | kubectl apply -f -
```

Create this secret **before** the first deploy when using `USE_AZURE_SERVICES=true`; the workflow checks for it and fails with a helpful message if it's missing.

---

## 11. Quick verification

- **Azure**
  - ACR: `az acr repository list --name $env:ACR_NAME --output table` (empty until first push).
  - AKS: `az aks show --resource-group $env:RESOURCE_GROUP --name $env:AKS_NAME --query provisioningState -o tsv` → `Succeeded`.
- **kubectl** (after `az aks get-credentials ...`): `kubectl get nodes` and `kubectl get ns workmage`.

After the first run of the workflow you should see images in ACR and workloads in the `workmage` namespace.

---

## Summary checklist

- [ ] Azure CLI installed and logged in; subscription and variables set (steps 1–2).
- [ ] Resource group created (step 3).
- [ ] ACR created; `ACR_NAME` and `ACR_LOGIN_SERVER` noted (step 4).
- [ ] AKS created with `--attach-acr`; `kubectl get nodes` works (step 5).
- [ ] (Optional) PostgreSQL Flexible Server and DB created; connection strings ready (step 6).
- [ ] (Optional) Azure Cache for Redis created; `REDIS_URL` ready (step 7).
- [ ] (If using Azure) `USE_AZURE_SERVICES=true` variable set; `workmage-secrets` created with Azure URLs (step 10).
- [ ] Service principal created; full JSON copied (step 8).
- [ ] GitHub repo secrets (and/or variables) set: `AZURE_CREDENTIALS`, `ACR_NAME`, `AKS_NAME`, `AKS_RESOURCE_GROUP` (step 9).
- [ ] Kubernetes secret `workmage-secrets` created or left to the example from manifests (step 10).

Then push to the **demo** branch or run the workflow manually; see [deploy-azure.md](deploy-azure.md) for deploy flow and app-level config.

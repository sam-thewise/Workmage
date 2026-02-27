# Workmage Agent NFT (Shared Agent Identity Contract)

This project deploys and verifies the **shared agent identity NFT** contract used by Workmage for ERC-8004 / ERC-6551 flows. One contract per network (Fuji, Avalanche mainnet); the API stores the deployed address in the database and uses it when minting agent identity NFTs.

## Prerequisites

- Node.js 18+
- AVAX on Fuji (faucet) or mainnet for deploy gas
- [Snowtrace API key](https://snowtrace.io/apis) (optional but recommended for verification)

## Setup

```bash
cd contracts/agent-nft
npm install
cp .env.example .env
# Edit .env: DEPLOYER_PRIVATE_KEY, optional SNOWTRACE_API_KEY, AGENT_NFT_BASE_URI
```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `DEPLOYER_PRIVATE_KEY` | Yes (for deploy) | Hex private key of deployer (no 0x prefix ok). |
| `AVALANCHE_FUJI_RPC_URL` | No | Fuji RPC (default: public). |
| `AVALANCHE_RPC_URL` | No | Mainnet RPC (default: public). |
| `SNOWTRACE_API_KEY` | No | API key for verification (reduces rate limits). |
| `SNOWTRACE_FUJI_API_URL` | No | Fuji Snowtrace/Routescan API (default: Routescan testnet). |
| `SNOWTRACE_API_URL` | No | Mainnet Snowtrace/Routescan API. |
| `AGENT_NFT_BASE_URI` | No | Base URI for token metadata (e.g. your API base + `/api/v1/agent-nft/metadata/`). |

## Deploy

**Fuji (testnet):**

```bash
npm run deploy:fuji
```

**Avalanche mainnet:**

```bash
npm run deploy:avalanche
```

Save the printed **contract address** and the **transaction hash** from the deploy (from Hardhat log or block explorer).

## Register in API

After deploy, register the contract in the Workmage API so the platform can use it for minting:

```bash
# Replace <API>, <ADMIN_TOKEN>, <CONTRACT_ADDRESS>, <DEPLOY_TX_HASH>
curl -X POST "https://<API>/api/v1/admin/agent-nft-contracts" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "network": "fuji",
    "chain_id": 43113,
    "contract_address": "<CONTRACT_ADDRESS>",
    "deploy_tx_hash": "<DEPLOY_TX_HASH>"
  }'
```

For mainnet use `"network": "avalanche"` and `"chain_id": 43114`.

## Verify on Snowtrace

Verification makes the contract source visible on [Snowtrace](https://snowtrace.io) (Fuji: testnet.snowtrace.io).

**Option A – Hardhat verify (recommended)**

```bash
# Fuji
npx hardhat verify --network fuji <CONTRACT_ADDRESS> "Workmage Agent Identity" "WMAI" "https://your-api/api/v1/agent-nft/metadata/"

# Mainnet
npx hardhat verify --network avalanche <CONTRACT_ADDRESS> "Workmage Agent Identity" "WMAI" "https://your-api/api/v1/agent-nft/metadata/"
```

Use the **exact** constructor args (name, symbol, baseURI) you used in deploy.

**Option B – API verify**

If you have the flattened source, you can submit via the admin API:

```bash
# 1. Flatten (from contracts/agent-nft)
npx hardhat flatten contracts/WorkmageAgentNFT.sol > WorkmageAgentNFT_flat.sol
# Remove duplicate SPDX and fix multi-license if needed

# 2. Submit (replace <SOURCE_CODE> with contents of WorkmageAgentNFT_flat.sol)
curl -X POST "https://<API>/api/v1/admin/agent-nft-contracts/fuji/verify" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "<SOURCE_CODE>",
    "contract_name": "WorkmageAgentNFT",
    "compiler_version": "v0.8.20+commit.a1b79de6"
  }'

# 3. Poll status until verified
curl -X POST "https://<API>/api/v1/admin/agent-nft-contracts/fuji/verify-status" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

After verification, the API sets `verified_at` on the contract record when you call `verify-status` and the explorer reports success.

## Contract

- **WorkmageAgentNFT**: ERC-721, `mint(to)` by owner, `_baseURI()` set by owner. Use as shared “agent identity” NFT; tokenURI can point at your API (e.g. agent-uri or a dedicated metadata route per token).

## Summary

1. **Deploy** with `npm run deploy:fuji` or `deploy:avalanche`.
2. **Register** the contract in the API via `POST /api/v1/admin/agent-nft-contracts`.
3. **Verify** on Snowtrace via `npx hardhat verify` (or admin verify + verify-status).
4. Use the registered contract address from the API when minting agent NFTs and binding ERC-6551 TBAs.

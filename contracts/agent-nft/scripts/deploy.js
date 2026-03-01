const hre = require("hardhat");

const CONTRACT_NAME = "WorkmageAgentNFT";
const NAME = "Workmage Agent Identity";
const SYMBOL = "WMAI";
const BASE_URI = process.env.AGENT_NFT_BASE_URI || "https://api.workmage.example/api/v1/agent-nft/metadata/";

async function main() {
  const network = hre.network.name;
  const chainId = (await hre.ethers.provider.getNetwork()).chainId.toString();
  const signers = await hre.ethers.getSigners();
  const deployer = signers[0];

  if (!deployer) {
    throw new Error(
      "No deployer account. Add DEPLOYER_PRIVATE_KEY to contracts/agent-nft/.env (64 hex chars, with or without 0x prefix). " +
      "The .env file must be in the same folder as hardhat.config.js. Run from contracts/agent-nft: npm run deploy:fuji"
    );
  }

  const balance = await hre.ethers.provider.getBalance(deployer.address);

  console.log("Network:", network, "ChainId:", chainId);
  console.log("Deploying with account:", deployer.address);
  console.log("Balance:", hre.ethers.formatEther(balance), "AVAX");

  const minBalance = hre.ethers.parseEther("0.01");
  if (balance < minBalance) {
    throw new Error(
      "Insufficient balance. Send at least 0.01 AVAX to " + deployer.address + " on " + network + " (Fuji faucet: https://faucet.avax.network or https://core.app/tools/faucet/). " +
      "Ensure DEPLOYER_PRIVATE_KEY in .env is the key for the wallet you funded."
    );
  }

  const Contract = await hre.ethers.getContractFactory(CONTRACT_NAME);
  const contract = await Contract.deploy(NAME, SYMBOL, BASE_URI);
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  const deployTx = contract.deploymentTransaction();
  const txHash = deployTx ? deployTx.hash : null;
  console.log(CONTRACT_NAME, "deployed to:", address);
  if (txHash) console.log("Deploy tx hash:", txHash);

  const minterAddr = process.env.AGENT_NFT_MINTER_ADDRESS;
  if (minterAddr) {
    const MINTER_ROLE = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("MINTER_ROLE"));
    const tx = await contract.grantRole(MINTER_ROLE, minterAddr);
    await tx.wait();
    console.log("Granted MINTER_ROLE to", minterAddr);
  }

  console.log("\nNext steps:");
  console.log("1. If not set: AGENT_NFT_MINTER_ADDRESS - redeploy with it or call grantRole(MINTER_ROLE, api_minter_address)");
  console.log("2. Register in API: POST /api/v1/admin/agent-nft-contracts");
  console.log("   Body: { \"network\": \"" + network + "\", \"chain_id\": " + chainId + ", \"contract_address\": \"" + address + "\", \"deploy_tx_hash\": \"<tx_hash>\" }");
  console.log("3. Verify on Snowtrace:");
  console.log("   npx hardhat verify --network " + network + " " + address + " \"" + NAME + "\" \"" + SYMBOL + "\" \"" + BASE_URI + "\"");
  console.log("\nContract address:", address);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

const hre = require("hardhat");

const CONTRACT_NAME = "MintPaymentContract";

async function main() {
  const network = hre.network.name;
  const chainId = (await hre.ethers.provider.getNetwork()).chainId.toString();
  const signers = await hre.ethers.getSigners();
  const deployer = signers[0];

  const treasury = process.env.MINT_PAYMENT_TREASURY || deployer.address;
  const minMintFee = process.env.MINT_PAYMENT_MIN_FEE_WEI || hre.ethers.parseEther("0.0002");

  if (!deployer) {
    throw new Error("Add DEPLOYER_PRIVATE_KEY to .env and run: npm run deploy:mint-payment:fuji");
  }

  console.log("Network:", network);
  console.log("Deployer:", deployer.address);
  console.log("Treasury:", treasury);
  console.log("Min mint fee (wei):", minMintFee.toString());

  const Contract = await hre.ethers.getContractFactory(CONTRACT_NAME);
  const contract = await Contract.deploy(deployer.address, treasury, minMintFee);
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  console.log(CONTRACT_NAME, "deployed to:", address);
  console.log("\nSet MINT_PAYMENT_CONTRACT_" + (network === "fuji" ? "FUJI" : "AVALANCHE") + "=" + address);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

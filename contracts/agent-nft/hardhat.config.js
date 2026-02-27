require("@nomicfoundation/hardhat-toolbox");
try { require("dotenv").config({ path: require("path").join(__dirname, ".env") }); } catch (_) {}

const AVALANCHE_RPC = process.env.AVALANCHE_RPC_URL || "https://api.avax.network/ext/bc/C/rpc";
const FUJI_RPC = process.env.AVALANCHE_FUJI_RPC_URL || "https://api.avax-test.network/ext/bc/C/rpc";
const raw = (process.env.DEPLOYER_PRIVATE_KEY || "").trim();
const PRIVATE_KEY = raw ? (raw.startsWith("0x") ? raw : "0x" + raw) : "";
// Valid key: 64 hex chars, or 0x + 64 hex = 66 chars
const HAS_VALID_KEY = PRIVATE_KEY.length === 66 || (PRIVATE_KEY.length === 64 && !PRIVATE_KEY.startsWith("0x"));

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: false, runs: 200 },
    },
  },
  networks: {
    fuji: {
      url: FUJI_RPC,
      chainId: 43113,
      accounts: HAS_VALID_KEY ? [PRIVATE_KEY] : [],
    },
    avalanche: {
      url: AVALANCHE_RPC,
      chainId: 43114,
      accounts: HAS_VALID_KEY ? [PRIVATE_KEY] : [],
    },
  },
  etherscan: {
    apiKey: {
      avalanche: process.env.SNOWTRACE_API_KEY || "dummy",
      fuji: process.env.SNOWTRACE_API_KEY || "dummy",
    },
    customChains: [
      {
        network: "fuji",
        chainId: 43113,
        urls: {
          apiURL: process.env.SNOWTRACE_FUJI_API_URL || "https://api.routescan.io/v2/network/testnet/evm/43113/etherscan/api",
          browserURL: "https://testnet.snowtrace.io",
        },
      },
      {
        network: "avalanche",
        chainId: 43114,
        urls: {
          apiURL: process.env.SNOWTRACE_API_URL || "https://api.routescan.io/v2/network/mainnet/evm/etherscan/api",
          browserURL: "https://snowtrace.io",
        },
      },
    ],
  },
};

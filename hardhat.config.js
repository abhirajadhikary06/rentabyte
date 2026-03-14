import "@nomicfoundation/hardhat-toolbox";
import "dotenv/config";

/**
 * Hardhat configuration for RentAByte smart contract.
 * Targets the Polygon Amoy Testnet.
 *
 * Setup:
 *   1. Copy .env.example to .env and fill in your values.
 *   2. npm install
 *   3. npx hardhat compile
 *   4. npx hardhat run scripts/deploy.js --network amoy
 */

const PRIVATE_KEY = process.env.DEPLOYER_PRIVATE_KEY || "0x" + "0".repeat(64);

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    // Local development
    hardhat: {},
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    // Polygon Amoy Testnet
    amoy: {
      url: process.env.POLYGON_RPC_URL || "https://rpc-amoy.polygon.technology",
      chainId: 80002,
      accounts: [PRIVATE_KEY],
      gasPrice: "auto",
    },
  },
  etherscan: {
    apiKey: {
      polygonAmoy: process.env.POLYGONSCAN_API_KEY || "",
    },
    customChains: [
      {
        network: "polygonAmoy",
        chainId: 80002,
        urls: {
          apiURL: "https://api-amoy.polygonscan.com/api",
          browserURL: "https://amoy.polygonscan.com",
        },
      },
    ],
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};

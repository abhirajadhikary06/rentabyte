/**
 * RentAByte - Hardhat Deploy Script
 *
 * Usage:
 *   npx hardhat run hardhat-scripts/deploy.js --network amoy
 *
 * After deployment, copy the printed contract address into your:
 *   - backend/.env  →  CONTRACT_ADDRESS=0x...
 *   - frontend/app.js  →  CONTRACT_ADDRESS constant
 */

const { ethers } = require("hardhat");

async function main() {
  const signers = await ethers.getSigners();
  if (signers.length === 0) {
    throw new Error(
      "No deployer account configured. Set DEPLOYER_PRIVATE_KEY=0x... in root .env"
    );
  }
  const [deployer] = signers;
  console.log("Deploying RentAByte with account:", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", ethers.formatEther(balance), "POL");

  // 0.001 POL = 1_000_000_000_000_000 wei per 100 MB
  const pricePerHundredMBWei = ethers.parseEther("0.001");

  const RentAByte = await ethers.getContractFactory("RentAByte");
  const contract = await RentAByte.deploy(pricePerHundredMBWei);

  await contract.waitForDeployment();
  const address = await contract.getAddress();

  console.log("─────────────────────────────────────────────");
  console.log("RentAByte deployed to:", address);
  console.log("Price per 100 MB:", ethers.formatEther(pricePerHundredMBWei), "POL");
  console.log("─────────────────────────────────────────────");
  console.log("Add to backend/.env:");
  console.log(`  CONTRACT_ADDRESS=${address}`);
  console.log("Add to frontend/app.js:");
  console.log(`  const CONTRACT_ADDRESS = "${address}";`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });

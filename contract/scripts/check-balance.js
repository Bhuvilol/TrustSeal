const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  
  console.log("Checking balance for account:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  const balanceInEther = hre.ethers.formatEther(balance);
  
  console.log("Balance:", balanceInEther, "MATIC");
  
  // Estimate deployment cost
  const estimatedGas = 2000000n; // Approximate gas for contract deployment
  const gasPrice = (await hre.ethers.provider.getFeeData()).gasPrice;
  const estimatedCost = estimatedGas * gasPrice;
  const estimatedCostInEther = hre.ethers.formatEther(estimatedCost);
  
  console.log("Estimated deployment cost:", estimatedCostInEther, "MATIC");
  
  if (balance < estimatedCost) {
    console.log("\n⚠️  WARNING: Insufficient funds!");
    console.log("You need approximately", estimatedCostInEther, "MATIC to deploy.");
    console.log("Please get testnet tokens from:");
    console.log("- https://faucet.polygon.technology/");
    console.log("- https://www.alchemy.com/faucets/polygon-amoy");
    console.log("- https://faucets.chain.link/polygon-amoy");
  } else {
    console.log("\n✅ Sufficient funds for deployment!");
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

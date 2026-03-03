const fs = require("fs");
const path = require("path");
require("dotenv").config({ path: "../backend/.env" });

async function main() {
  const factory = await ethers.getContractFactory("SupplyChainRelay");
  const contract = await factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const artifactPath = path.join(__dirname, "..", "artifacts", "contracts", "SupplyChainRelay.sol", "SupplyChainRelay.json");
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  const abiJson = JSON.stringify(artifact.abi);

  const output = {
    network: "amoy",
    address,
    abi: artifact.abi,
    abi_json_single_line: abiJson,
    deployed_at: new Date().toISOString(),
  };

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "amoy.json"), JSON.stringify(output, null, 2));

  console.log("CONTRACT_ADDRESS=" + address);
  console.log("CHAIN_CONTRACT_ABI_JSON=" + abiJson);
  console.log("WROTE_DEPLOYMENT=" + path.join("deployments", "amoy.json"));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
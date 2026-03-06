const fs = require("fs");
const path = require("path");
const hre = require("hardhat");
require("dotenv").config({ path: "../backend/.env" });

function toEnvKeySuffix(networkName) {
  return String(networkName || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "_");
}

async function main() {
  const networkName = hre.network.name || "amoy";
  const networkChainId = Number(hre.network.config.chainId || process.env.CHAIN_CHAIN_ID || 0) || undefined;
  const artifactPath = path.join(__dirname, "..", "artifacts", "contracts", "SupplyChainRelay.sol", "SupplyChainRelay.json");
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  const abiJson = JSON.stringify(artifact.abi);
  const outDir = path.join(__dirname, "..", "deployments");
  const deploymentPath = path.join(outDir, `${networkName}.json`);

  const reuseDeployment = String(process.env.REUSE_DEPLOYMENT_ADDRESS || "").toLowerCase() === "true";
  const keySuffix = toEnvKeySuffix(networkName);
  let address =
    (process.env[`CHAIN_CONTRACT_ADDRESS_${keySuffix}`] || "").trim() ||
    (process.env.CHAIN_CONTRACT_ADDRESS || "").trim();

  if (!reuseDeployment) {
    const factory = await hre.ethers.getContractFactory("SupplyChainRelay");
    const contract = await factory.deploy();
    await contract.waitForDeployment();
    address = await contract.getAddress();
  }

  if (!address && fs.existsSync(deploymentPath)) {
    const existing = JSON.parse(fs.readFileSync(deploymentPath, "utf8"));
    address = String(existing.address || "").trim();
  }

  if (!address) {
    throw new Error("Contract address is required. Set CHAIN_CONTRACT_ADDRESS or deploy a new contract.");
  }

  const output = {
    network: networkName,
    chain_id: networkChainId,
    address,
    abi: artifact.abi,
    abi_json_single_line: abiJson,
    deployed_at: new Date().toISOString(),
    deployment_mode: reuseDeployment ? "abi_refresh" : "fresh_deploy",
  };

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(deploymentPath, JSON.stringify(output, null, 2));

  const backendEnvSnippet = [
    `CHAIN_CHAIN_ID=${networkChainId || ""}`,
    `CHAIN_CONTRACT_ADDRESS=${address}`,
    `CHAIN_CONTRACT_ABI_JSON=${abiJson}`,
  ].join("\n");
  const backendEnvOutPath = path.join(__dirname, "..", "..", "backend", `.env.contract.${networkName}`);
  fs.writeFileSync(backendEnvOutPath, `${backendEnvSnippet}\n`);

  console.log("CONTRACT_ADDRESS=" + address);
  console.log("CHAIN_CHAIN_ID=" + (networkChainId || ""));
  console.log("CHAIN_CONTRACT_ABI_JSON=" + abiJson);
  console.log("WROTE_DEPLOYMENT=" + path.join("deployments", `${networkName}.json`));
  console.log("WROTE_BACKEND_ENV_SNIPPET=" + path.join("..", "backend", `.env.contract.${networkName}`));
  console.log("DEPLOYMENT_MODE=" + output.deployment_mode);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

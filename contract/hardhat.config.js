require("dotenv").config({ path: "../backend/.env" });
require("@nomicfoundation/hardhat-ethers");

const chainRpcUrl = process.env.CHAIN_RPC_URL || "";
const amoyRpcUrl = process.env.CHAIN_RPC_URL_AMOY || chainRpcUrl;
const polygonRpcUrl = process.env.CHAIN_RPC_URL_POLYGON || "";
const localhostRpcUrl = process.env.CHAIN_RPC_URL_LOCALHOST || "http://127.0.0.1:8545";
const privateKey = process.env.CHAIN_PRIVATE_KEY || "";
const normalizedPrivateKey = privateKey.trim();
const hasValidPrivateKey = /^0x[a-fA-F0-9]{64}$/.test(normalizedPrivateKey);

module.exports = {
  solidity: "0.8.20",
  networks: {
    amoy: {
      url: amoyRpcUrl,
      accounts: hasValidPrivateKey ? [normalizedPrivateKey] : [],
      chainId: 80002,
    },
    polygon: {
      url: polygonRpcUrl,
      accounts: hasValidPrivateKey ? [normalizedPrivateKey] : [],
      chainId: 137,
    },
    localhost: {
      url: localhostRpcUrl,
      chainId: 31337,
      accounts: hasValidPrivateKey ? [normalizedPrivateKey] : [],
    },
  },
};

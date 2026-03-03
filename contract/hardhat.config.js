require("dotenv").config({ path: "../backend/.env" });
require("@nomicfoundation/hardhat-ethers");

const chainRpcUrl = process.env.CHAIN_RPC_URL || "";
const privateKey = process.env.CHAIN_PRIVATE_KEY || "";
const normalizedPrivateKey = privateKey.trim();
const hasValidPrivateKey = /^0x[a-fA-F0-9]{64}$/.test(normalizedPrivateKey);

module.exports = {
  solidity: "0.8.20",
  networks: {
    amoy: {
      url: chainRpcUrl,
      accounts: hasValidPrivateKey ? [normalizedPrivateKey] : [],
      chainId: 80002,
    },
  },
};

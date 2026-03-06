# Contract Deploy and ABI Sync

## Compile

```powershell
cd contract
npm run compile
```

## Test

```powershell
npm test
```

## Fresh deploy (amoy)

Requires `CHAIN_RPC_URL` and `CHAIN_PRIVATE_KEY` in `backend/.env`.

```powershell
cd contract
npm run deploy:amoy
```

Writes:
- `contract/deployments/amoy.json`
- `backend/.env.contract.amoy` (snippet for backend chain vars)

## Fresh deploy (polygon mainnet)

Requires `CHAIN_RPC_URL_POLYGON` and `CHAIN_PRIVATE_KEY` in `backend/.env`.

```powershell
cd contract
npm run deploy:polygon
```

Writes:
- `contract/deployments/polygon.json`
- `backend/.env.contract.polygon`

## Fresh deploy (localhost)

```powershell
cd contract
npm run deploy:localhost
```

Writes:
- `contract/deployments/localhost.json`
- `backend/.env.contract.localhost`

## ABI refresh without redeploy

Use this after ABI/interface changes when contract address is already deployed.

```powershell
cd contract
$env:REUSE_DEPLOYMENT_ADDRESS='true'
npx hardhat run scripts/deploy.js --network amoy
```

You can also provide env-specific contract address keys:
- `CHAIN_CONTRACT_ADDRESS_AMOY`
- `CHAIN_CONTRACT_ADDRESS_POLYGON`
- `CHAIN_CONTRACT_ADDRESS_LOCALHOST`

This updates `contract/deployments/<network>.json` with latest ABI while preserving address.

## Backend env alignment

After deploy/ABI refresh, copy values from `backend/.env.contract.<network>` into your active `backend/.env`:

```env
CHAIN_CHAIN_ID=...
CHAIN_CONTRACT_ADDRESS=...
CHAIN_CONTRACT_ABI_JSON=[...]
```

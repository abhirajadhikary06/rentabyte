# RentAByte

Decentralised storage marketplace powered by Polygon Amoy.

Sellers contribute unused Dropbox space. Buyers rent it with POL through MetaMask. Files are encrypted, split into chunks, and distributed across seller nodes.

Live app: https://rentabyte.onrender.com

## What It Does

- Lets buyers purchase storage on Polygon Amoy using POL.
- Lets sellers register unused Dropbox space and earn POL rewards.
- Encrypts files with Fernet before storage.
- Splits encrypted files into 5 MB chunks.
- Distributes chunks across multiple seller Dropbox accounts.
- Reconstructs and verifies chunks on download.

## Current Architecture

```text
Browser
  |- landing.html
  |- index.html
  |- upload.html
  |- app.js
  |- MetaMask + ethers.js
  v
FastAPI backend
  |- wallet registration
  |- Dropbox connection
  |- storage allocation
  |- file upload / download
  |- static frontend hosting
  v
Services
  |- Polygon Amoy RPC
  |- Neon Postgres
  |- Dropbox seller accounts
```

## Key Flow

### Buyer flow

1. Connect MetaMask on Polygon Amoy.
2. Choose a storage amount.
3. Pay `0.001 POL` per `100 MB`.
4. Backend verifies the payment transaction on-chain.
5. Storage is allocated against that transaction hash.
6. Buyer uploads files tied to that allocation.

### Seller flow

1. Connect MetaMask.
2. Connect a Dropbox account with an access token.
3. Register available storage in MB.
4. Backend verifies free Dropbox capacity.
5. Seller node is added to the storage pool.
6. Seller receives a POL reward transaction.

### File flow

1. File is read by the backend.
2. File is encrypted with Fernet.
3. Encrypted payload is split into 5 MB chunks.
4. Chunks are uploaded to seller Dropbox accounts.
5. Chunk metadata is stored in Neon Postgres.
6. On download, chunks are fetched, verified, merged, and decrypted.

## Project Structure

```text
rentabyte/
|- backend/
|  |- .env.example
|  |- blockchain_service.py
|  |- database.py
|  |- dropbox_service.py
|  |- main.py
|  |- models.py
|  |- storage_service.py
|- contracts/
|  |- RentAByte.sol
|- frontend/
|  |- app.js
|  |- index.html
|  |- landing.html
|  |- upload.html
|- hardhat-scripts/
|  |- deploy.js
|- scripts/
|  |- test_dropbox.py
|  |- test_neondb.py
|  |- verify_transaction.py
|- Dockerfile
|- hardhat.config.js
|- package.json
|- requirements.txt
|- README.md
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Wallet | MetaMask |
| Blockchain | Polygon Amoy, ethers.js v6, web3.py |
| Smart Contract | Solidity, Hardhat |
| Backend | FastAPI, Uvicorn |
| Database | Neon Postgres, psycopg2 |
| Storage | Dropbox API |
| Encryption | cryptography / Fernet |
| Deployment | Render, Docker |

## Live Deployment

- Production URL: https://rentabyte.onrender.com
- Frontend and backend are served from the same Render deployment.
- The frontend uses `window.RENTABYTE_API_BASE = ""`, so API requests are same-origin.
- The app listens on port `8000` locally and uses Render's injected `PORT` variable in production.

## Environment Variables

Create `backend/.env` locally from `backend/.env.example`.

Required variables:

```env
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology
CONTRACT_ADDRESS=0xe21092e562933E14F2F8D624D04E5a000e356835
PLATFORM_WALLET=0xC913d8B68ACCFE2b1AEB8805D48D802547C827A1
PLATFORM_PRIVATE_KEY=your_private_key
POL_PER_100MB=0.001
FERNET_KEY=your_fernet_key
CHUNK_SIZE_MB=5
NEONDB_DATABASE_URL=your_neon_connection_string
```

Notes:

- `POL_PER_100MB` is currently `0.001`.
- `NEONDB_DATABASE_URL` is required because the project now uses Postgres, not SQLite.
- In hosted environments, set these variables in the Render dashboard instead of relying on `.env`.

## Local Development

### 1. Install dependencies

```bash
git clone https://github.com/abhirajadhikary06/rentabyte.git
cd rentabyte

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

npm install
```

### 2. Configure backend

```bash
copy backend\.env.example backend\.env
```

Fill in the environment variables listed above.

### 3. Run the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Local URLs:

- App: http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

The backend serves the frontend directly, so you do not need a separate frontend dev server for normal local testing.

## Docker

Build and run locally:

```bash
docker build -t rentabyte .
docker run -p 8000:8000 --env-file backend/.env rentabyte
```

The Docker image:

- installs Python dependencies from `requirements.txt`
- copies `backend/` and `frontend/`
- starts Uvicorn from `backend/`
- exposes port `8000`

## Smart Contract

Compile and deploy:

```bash
npx hardhat compile
npx hardhat run hardhat-scripts/deploy.js --network amoy
```

Available scripts from `package.json`:

```bash
npm run compile
npm run deploy:amoy
npm run deploy:local
npm run node
npm run test
```

## Main Endpoints

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health and Polygon RPC status |
| `POST` | `/connect-wallet` | Register buyer or seller wallet |
| `POST` | `/connect-dropbox` | Save and verify seller Dropbox token |
| `POST` | `/register-storage` | Add seller storage to pool |
| `GET` | `/storage-pool` | Return pool stats |
| `POST` | `/request-storage` | Verify payment and allocate storage |
| `POST` | `/upload-file` | Upload and distribute a file |
| `GET` | `/files` | List files for a wallet |
| `GET` | `/download-file/{file_id}` | Download and reconstruct a file |

## End-to-End Demo Flow

### Seller demo

1. Open https://rentabyte.onrender.com
2. Connect MetaMask.
3. Open the seller tab.
4. Paste a Dropbox access token.
5. Register storage in MB.
6. Confirm the seller reward transaction is returned.

### Buyer demo

1. Open https://rentabyte.onrender.com
2. Connect MetaMask.
3. Purchase storage from the buyer panel.
4. Copy the resulting payment transaction hash.
5. Open the My Files page.
6. Paste the transaction hash into the allocation field.
7. Upload a file.
8. Refresh the file list and download the file back.

## Render Deployment

This project is deployed as a single Render web service using the root `Dockerfile`.

Recommended Render setup:

1. Create a Web Service from the GitHub repo.
2. Let Render build from the repository root.
3. Set all backend environment variables in Render.
4. Ensure the service port is `8000` if Render asks for an internal port.
5. Redeploy after updating environment variables.

Because the frontend is served by FastAPI, you do not need a separate static-site deployment for the current production setup.

## Current Notes

- The UI has been redesigned with the current orange multi-color theme.
- Toast notifications and transaction feedback are implemented in the frontend.
- The file list on the upload page is scrollable after roughly three visible rows.
- MetaMask buttons in the navbar use the current black styling.

## Troubleshooting

### 502 on Render

- Check service logs first.
- Most startup failures are caused by missing or invalid environment variables.
- Verify `NEONDB_DATABASE_URL` is reachable from Render.

### Wallet transaction errors

- Make sure MetaMask is on Polygon Amoy.
- Ensure the wallet has enough POL for both payment and gas.
- If MetaMask shows gas-related errors, retry after a short delay.

### No storage nodes available

- A seller must register Dropbox-backed storage first.
- Uploads fail if no seller node has enough free capacity for the next chunk.

### Download or decryption failure

- `FERNET_KEY` must remain stable between upload and download.
- Dropbox tokens used by seller nodes must still be valid.

## License

MIT

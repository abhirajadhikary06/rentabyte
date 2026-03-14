# 🔷 RentAByte

> **Decentralised Storage Marketplace powered by Polygon**
>
> Sellers contribute unused Dropbox space. Buyers rent it using POL tokens via MetaMask.
> Files are encrypted, split into chunks, and distributed across seller nodes — all on the Polygon Amoy Testnet.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Quick Start (Local)](#quick-start-local)
   - [Backend Setup](#1-backend-setup)
   - [Smart Contract Deploy](#2-smart-contract-deploy)
   - [Frontend Setup](#3-frontend-setup)
5. [MetaMask Setup](#metamask-setup)
6. [Getting Test POL Tokens](#getting-test-pol-tokens)
7. [End-to-End Demo Flow](#end-to-end-demo-flow)
8. [API Reference](#api-reference)
9. [Deploying to Render](#deploying-to-render)
10. [Environment Variables](#environment-variables)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│   index.html (Dashboard)         upload.html (File Manager)    │
│   app.js ─ ethers.js ─ MetaMask ─ Polygon Amoy Testnet         │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API (FastAPI)
┌─────────────────────────▼───────────────────────────────────────┐
│                         BACKEND (Python / FastAPI)              │
│                                                                 │
│  main.py          ── API endpoints                              │
│  blockchain_service.py ── Verify Polygon tx via RPC            │
│  storage_service.py    ── Encrypt → Chunk → Distribute         │
│  dropbox_service.py    ── Upload/Download chunks               │
│  database.py           ── SQLite metadata store                │
└───────────┬─────────────────────────────────┬───────────────────┘
            │                                 │
  ┌─────────▼──────────┐           ┌──────────▼──────────┐
  │   Polygon Amoy     │           │   Dropbox Accounts  │
  │   Testnet (RPC)    │           │   (Seller nodes)    │
  │   Smart Contract   │           │   Encrypted chunks  │
  └────────────────────┘           └─────────────────────┘
            │
  ┌─────────▼──────────┐
  │   SQLite Database  │
  │   (Metadata only)  │
  │   users / files /  │
  │   chunks / nodes   │
  └────────────────────┘
```

### Payment Flow

```
Buyer                    MetaMask              Smart Contract        Backend
  │                          │                      │                   │
  │── Choose 500 MB ────────>│                      │                   │
  │                          │── Send 0.05 POL ────>│                   │
  │                          │                      │── emit event ─────│
  │<── tx_hash ──────────────│                      │                   │
  │                          │                      │                   │
  │── POST /request-storage (tx_hash) ─────────────────────────────────>│
  │                          │                      │                   │── verify tx on RPC
  │                          │                      │                   │── allocate 500 MB
  │<── 200 OK (allocated) ──────────────────────────────────────────────│
```

### File Storage Flow

```
Buyer uploads file.pdf (12 MB)
          │
          ▼
    [encrypt with Fernet AES]
          │
          ▼
    [split into 3 chunks: 5MB + 5MB + 2MB]
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
 Node1  Node2  Node3   ← each is a seller's Dropbox
    │     │     │
    └─────┴─────┘
          │
    [store paths in SQLite]
```

---

## Project Structure

```
rentabyte/
├── backend/
│   ├── main.py              ← FastAPI app + all endpoints
│   ├── database.py          ← SQLite init & connection
│   ├── models.py            ← Pydantic request/response schemas
│   ├── storage_service.py   ← Encrypt, chunk, distribute files
│   ├── dropbox_service.py   ← Dropbox SDK wrapper
│   ├── blockchain_service.py← Polygon RPC tx verification
│   └── .env.example         ← Environment variable template
│
├── contracts/
│   └── RentAByte.sol        ← Solidity smart contract
│
├── hardhat-scripts/
│   └── deploy.js            ← Hardhat deployment script
│
├── frontend/
│   ├── index.html           ← Dashboard (connect wallet, buy/sell storage)
│   ├── upload.html          ← File upload & download manager
│   ├── app.js               ← ethers.js, MetaMask, API calls
│   └── style.css            ← Dark UI stylesheet
│
├── scripts/
│   └── verify_transaction.py← Standalone tx verifier CLI
│
├── hardhat.config.js        ← Hardhat + Polygon Amoy config
├── package.json             ← Node deps for Hardhat
├── requirements.txt         ← Python deps
├── render.yaml              ← Render deployment config
└── README.md
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| MetaMask | Latest | [metamask.io](https://metamask.io/) |
| Git | Any | [git-scm.com](https://git-scm.com/) |

---

## Quick Start (Local)

### 1. Backend Setup

```bash
# Clone the repo
git clone https://github.com/yourname/rentabyte.git
cd rentabyte

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in at minimum:

```env
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology
POL_PER_100MB=0.01
CHUNK_SIZE_MB=5

# Generate a Fernet key:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=your_generated_key_here

# After deploying the smart contract (Step 2):
CONTRACT_ADDRESS=0xYourContractAddress

# OR if skipping contract, use a wallet address for direct transfers:
PLATFORM_WALLET=0xYourWalletAddress
```

```bash
# Start the backend
cd backend
uvicorn main:app --reload --port 8000
```

You should see:
```
[DB] Database initialized successfully.
[RentAByte] Backend started.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Visit **http://localhost:8000/docs** to see the auto-generated Swagger UI.

---

### 2. Smart Contract Deploy

> **Skip this step for a quick demo** — you can use a direct wallet transfer instead.
> Set `PLATFORM_WALLET` in `.env` and `RENTABYTE_PLATFORM_WALLET` in the HTML files.

```bash
# From project root
npm install

# Compile the contract
npx hardhat compile

# Add your deployer private key to .env (root level)
echo "DEPLOYER_PRIVATE_KEY=0xYourPrivateKeyHere" >> .env

# Deploy to Polygon Amoy Testnet
npx hardhat run hardhat-scripts/deploy.js --network amoy
```

Output:
```
Deploying RentAByte with account: 0xYourAddress
Account balance: 0.5 POL
─────────────────────────────────────────────
RentAByte deployed to: 0xAbCd1234...
Price per 100 MB: 0.01 POL
─────────────────────────────────────────────
Add to backend/.env:
  CONTRACT_ADDRESS=0xAbCd1234...
Add to frontend/app.js:
  const CONTRACT_ADDRESS = "0xAbCd1234...";
```

Update both files with the printed contract address.

---

### 3. Frontend Setup

The frontend is pure HTML/CSS/JS — no build step needed.

**Option A: Open directly in browser**
```bash
open frontend/index.html
# or on Linux:
xdg-open frontend/index.html
```

**Option B: Serve with Python (recommended to avoid CORS issues)**
```bash
cd frontend
python -m http.server 3000
# Open: http://localhost:3000
```

**Option C: Use VS Code Live Server extension**
Right-click `index.html` → Open with Live Server

---

## MetaMask Setup

### 1. Install MetaMask
Download from [metamask.io](https://metamask.io/). Create or import a wallet.

### 2. Add Polygon Amoy Testnet

RentAByte will add this network **automatically** when you click Connect. To add it manually:

| Field | Value |
|-------|-------|
| Network Name | Polygon Amoy Testnet |
| RPC URL | `https://rpc-amoy.polygon.technology` |
| Chain ID | `80002` |
| Currency Symbol | `POL` |
| Block Explorer | `https://amoy.polygonscan.com` |

In MetaMask:
1. Click the network dropdown (top left)
2. Click **Add a custom network**
3. Fill in the table above
4. Click **Save**

### 3. Switch to Amoy
Select **Polygon Amoy Testnet** from the network dropdown before using RentAByte.

---

## Getting Test POL Tokens

You need POL tokens to pay for storage (they're free on testnet).

1. Go to **https://faucet.polygon.technology**
2. Select **Polygon Amoy** network
3. Paste your MetaMask wallet address
4. Click **Submit**
5. Wait ~30 seconds — you'll receive **0.2 POL** (enough for 2000 MB of storage at demo pricing)

> **Alternative faucets** if the official one is slow:
> - https://www.alchemy.com/faucets/polygon-amoy
> - https://polygon-faucet.io

---

## End-to-End Demo Flow

### As a Seller (contributing storage)

1. **Open** `http://localhost:3000/index.html`
2. **Click** "🦊 Connect MetaMask" → approve in MetaMask
3. **Click** "I'm a Seller" tab
4. **Get a Dropbox access token:**
   - Go to https://www.dropbox.com/developers/apps
   - Create a new app → **Scoped access** → **Full Dropbox**
   - Go to **Settings** → **OAuth 2** → click **Generate** under "Generated access token"
   - Copy the token (starts with `sl.`)
5. **Paste** the token into "Dropbox Access Token" → click **Connect Dropbox**
6. **Enter** how many MB to share (e.g. `2000`) → click **Register Storage Node**
7. Watch the Pool Stats update ✅

### As a Buyer (purchasing storage)

1. **Open** `http://localhost:3000/index.html`
2. **Click** "🦊 Connect MetaMask"
3. **Stay on** "I'm a Buyer" tab
4. **Enter** storage amount (e.g. `500` MB)
   - Cost shown: `0.05 POL`
5. **Click** "💳 Pay & Allocate Storage"
6. MetaMask pops up → **Confirm** the transaction
7. Wait for confirmation (~5-30 seconds on Amoy)
8. Backend verifies the tx and allocates storage ✅
9. **Copy the tx hash** shown in the success message

### Uploading a File

1. **Click** "📁 Go to My Files" or navigate to `upload.html`
2. **Paste** your payment tx hash into "Payment Transaction Hash" → click **Use This Tx**
3. **Drag & drop** a file onto the upload zone (or click to browse)
4. Watch the progress bar — the backend is:
   - Encrypting your file (Fernet AES)
   - Splitting it into 5 MB chunks
   - Uploading chunks to seller Dropboxes
5. File appears in "Uploaded Files" table ✅

### Downloading a File

1. In the "Uploaded Files" table, click **⬇️ Download** next to any file
2. Backend fetches all chunks from Dropboxes
3. Verifies SHA-256 hash of each chunk
4. Merges and decrypts the file
5. File downloads to your browser ✅

### Verifying a Transaction (CLI)

```bash
cd scripts
python verify_transaction.py 0xYourTxHash 0xYourWalletAddress 500
```

Output:
```
════════════════════════════════════════════════════
RentAByte - Transaction Verifier
════════════════════════════════════════════════════
Verifying transaction: 0xabc...
Buyer wallet:          0x1234...
Storage requested:     500 MB
────────────────────────────────────────────────────
Status:    ✅ VALID
Reason:    Transaction verified successfully
Value:     50000000000000000 wei
Balance:   0.45 POL
════════════════════════════════════════════════════
```

---

## API Reference

All endpoints are available at `http://localhost:8000`. Full interactive docs at `/docs`.

### `GET /health`
Check backend and Polygon RPC status.
```json
{ "status": "ok", "polygon_rpc": true }
```

### `POST /connect-wallet`
Register a wallet address.
```json
// Request
{ "wallet_address": "0x1234...abcd" }

// Response
{ "success": true, "message": "Wallet registered successfully.", "wallet_address": "0x1234...abcd" }
```

### `POST /connect-dropbox`
Save seller's Dropbox token (verifies it works).
```json
// Request
{ "wallet_address": "0x1234...", "dropbox_token": "sl.XXXXX" }

// Response
{ "success": true, "message": "Dropbox connected. Available space: 8432 MB." }
```

### `POST /register-storage`
Seller registers storage capacity.
```json
// Request
{ "wallet_address": "0x1234...", "storage_mb": 2000 }

// Response
{ "success": true, "node_id": 1, "registered_mb": 2000 }
```

### `GET /storage-pool`
Pool statistics (public).
```json
{
  "total_storage_mb": 5000,
  "available_storage_mb": 3200,
  "node_count": 3,
  "price_per_100mb_pol": 0.01
}
```

### `POST /request-storage`
Buyer allocates storage after paying on-chain.
```json
// Request
{ "wallet_address": "0x1234...", "storage_mb": 500, "tx_hash": "0xabc..." }

// Response
{ "success": true, "message": "Storage allocated: 500 MB", "allocated_mb": 500 }
```

### `POST /upload-file`
Upload a file (multipart form).
```
POST /upload-file?wallet_address=0x1234...&tx_hash=0xabc...
Content-Type: multipart/form-data
Body: file=@yourfile.pdf
```
```json
{
  "success": true,
  "file_id": "uuid-string",
  "file_name": "yourfile.pdf",
  "file_size": 1048576,
  "message": "File uploaded and distributed successfully."
}
```

### `GET /files?wallet_address=0x1234...`
List all files for a wallet.
```json
{
  "files": [
    { "file_id": "uuid", "original_name": "doc.pdf", "file_size": 1048576, "created_at": "2024-..." }
  ]
}
```

### `GET /download-file/{file_id}`
Download a file by ID. Returns binary stream with `Content-Disposition` header.

---

## Deploying to Render

### Step 1 — Push to GitHub
```bash
git add .
git commit -m "initial commit"
git push origin main
```

### Step 2 — Create a Render Web Service

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo
3. Render detects `render.yaml` automatically
4. Set the following environment variables in the Render dashboard:

| Variable | Value |
|----------|-------|
| `CONTRACT_ADDRESS` | Your deployed contract address |
| `PLATFORM_WALLET` | Your wallet (fallback if no contract) |
| `FERNET_KEY` | Your generated Fernet key |
| `POLYGON_RPC_URL` | `https://rpc-amoy.polygon.technology` |
| `POL_PER_100MB` | `0.01` |

5. Click **Deploy**
6. Copy the Render URL (e.g. `https://rentabyte-api.onrender.com`)

### Step 3 — Update Frontend Config

In `frontend/index.html` and `frontend/upload.html`, update:
```javascript
window.RENTABYTE_API_BASE = "https://rentabyte-api.onrender.com";
window.RENTABYTE_CONTRACT = "0xYourContractAddress";
```

Then deploy the frontend (GitHub Pages, Netlify, or Vercel — it's static HTML):

**Netlify (easiest):**
1. Go to [netlify.com](https://netlify.com) → **Add new site** → **Deploy manually**
2. Drag the `frontend/` folder into the deploy box
3. Your site is live in seconds

**GitHub Pages:**
```bash
# From project root
cp -r frontend docs      # GitHub Pages serves from /docs
git add docs/
git commit -m "frontend deploy"
git push
# Enable Pages in repo Settings → Pages → Source: /docs
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POLYGON_RPC_URL` | Polygon Amoy RPC endpoint | `https://rpc-amoy.polygon.technology` |
| `CONTRACT_ADDRESS` | Deployed RentAByte contract | *(empty)* |
| `PLATFORM_WALLET` | Fallback payment receiver wallet | *(empty)* |
| `POL_PER_100MB` | Price in POL per 100 MB | `0.01` |
| `FERNET_KEY` | AES encryption key (base64) | *(auto-generated)* |
| `CHUNK_SIZE_MB` | File chunk size in MB | `5` |
| `DB_PATH` | SQLite database file path | `rentabyte.db` |

---

## Troubleshooting

### MetaMask doesn't pop up
- Make sure MetaMask is **installed and unlocked**
- Check you're on **Polygon Amoy Testnet** (Chain ID 80002)
- Open browser console for error details

### "Transaction not found on-chain"
- Polygon Amoy can be slow — wait 30-60 seconds after MetaMask confirms
- The tx needs at least **1 block confirmation**
- Check the tx on https://amoy.polygonscan.com

### "No storage nodes available"
- A seller must first register storage before a buyer can upload files
- For testing, register as a seller first with a Dropbox token

### Dropbox token invalid
- Tokens from the Dropbox console expire — regenerate a fresh one
- Make sure the app has **Full Dropbox** scope (not App folder)
- The token must start with `sl.`

### Backend CORS errors
- The backend allows all origins (`*`) by default
- If deploying to Render, your frontend URL must be able to reach the Render URL
- Check the Render service logs for startup errors

### Fernet key mismatch / decryption fails
- The same `FERNET_KEY` must be used for both upload and download
- On Render free tier, the service restarts periodically — always set `FERNET_KEY` in env vars (never auto-generate in production)

### Python dependency conflicts
```bash
# Use a clean virtual environment
python -m venv .venv --clear
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Blockchain | ethers.js v6, MetaMask, Polygon Amoy |
| Smart Contract | Solidity 0.8.20, Hardhat |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Encryption | Fernet (AES-128-CBC via `cryptography`) |
| Storage | Dropbox API v2 (Python SDK) |
| Database | SQLite (via `sqlite3` stdlib) |
| Deployment | Render (backend), Netlify (frontend) |

---

## Pricing Model

| Storage | POL Cost |
|---------|----------|
| 100 MB | 0.01 POL |
| 500 MB | 0.05 POL |
| 1 GB   | 0.10 POL |
| 5 GB   | 0.50 POL |

*Configurable via `POL_PER_100MB` env variable and smart contract `updatePrice()` function.*

---

## License

MIT — built for hackathon demonstration purposes.

---

*RentAByte — Making every byte count on the blockchain* 🔷

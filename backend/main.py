"""
RentAByte - Main FastAPI Application
Entry point for the backend. Defines all REST API endpoints.

Run locally:
    uvicorn main:app --reload --port 8000
"""

from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db, get_connection
from models import (
    ConnectWalletRequest, ConnectWalletResponse,
    ConnectDropboxRequest, ConnectDropboxResponse,
    RegisterStorageRequest, RegisterStorageResponse,
    StoragePoolResponse,
    RequestStorageRequest, RequestStorageResponse,
)
import dropbox_service
import blockchain_service
import storage_service

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ── App Setup ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="RentAByte API",
    description="Decentralised storage marketplace powered by Polygon",
    version="1.0.0",
)

# Allow all origins for hackathon demo; restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise DB on startup
@app.on_event("startup")
def on_startup():
    init_db()
    print("[RentAByte] Backend started.")


# ── Health Check ───────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Simple health-check used by Render."""
    rpc_ok = blockchain_service.is_connected()
    return {"status": "ok", "polygon_rpc": rpc_ok}


# ── Wallet Endpoints ───────────────────────────────────────────────────────

@app.post("/connect-wallet", response_model=ConnectWalletResponse)
def connect_wallet(req: ConnectWalletRequest):
    """
    Register or look up a user by their MetaMask wallet address.
    Called every time the user connects MetaMask on the frontend.
    """
    wallet = req.wallet_address.lower().strip()
    if not wallet.startswith("0x") or len(wallet) != 42:
        raise HTTPException(status_code=400, detail="Invalid wallet address format.")

    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE wallet_address = %s", (wallet,)
    ).fetchone()

    if existing is None:
        conn.execute(
            "INSERT INTO users (wallet_address) VALUES (%s)", (wallet,)
        )
        conn.commit()
        message = "Wallet registered successfully."
    else:
        message = "Wallet already registered."

    conn.close()
    return ConnectWalletResponse(
        success=True,
        message=message,
        wallet_address=wallet,
    )


# ── Dropbox Endpoints ──────────────────────────────────────────────────────

@app.post("/connect-dropbox", response_model=ConnectDropboxResponse)
def connect_dropbox(req: ConnectDropboxRequest):
    """
    Save a seller's Dropbox access token.
    The frontend collects the token via Dropbox OAuth or manual entry.
    """
    wallet = req.wallet_address.lower().strip()
    conn = get_connection()

    user = conn.execute(
        "SELECT id FROM users WHERE wallet_address = %s", (wallet,)
    ).fetchone()
    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found. Connect wallet first.")

    # Verify the token works
    available = dropbox_service.get_available_storage_bytes(req.dropbox_token)
    if available == 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Dropbox token invalid or account has no free space."
        )

    conn.execute(
        "UPDATE users SET dropbox_token = %s WHERE wallet_address = %s",
        (req.dropbox_token, wallet)
    )
    conn.commit()
    conn.close()

    available_mb = available // (1024 * 1024)
    return ConnectDropboxResponse(
        success=True,
        message=f"Dropbox connected. Available space: {available_mb} MB."
    )


# ── Seller Storage Registration ────────────────────────────────────────────

@app.post("/register-storage", response_model=RegisterStorageResponse)
def register_storage(req: RegisterStorageRequest):
    """
    A seller registers how many MB they want to contribute to the pool.
    The backend verifies they have that much free space on Dropbox.
    """
    wallet = req.wallet_address.lower().strip()
    conn = get_connection()

    user = conn.execute(
        "SELECT id, dropbox_token FROM users WHERE wallet_address = %s", (wallet,)
    ).fetchone()
    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Wallet not found.")

    if not user["dropbox_token"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Connect Dropbox first.")

    # Check Dropbox really has this much space
    available_bytes = dropbox_service.get_available_storage_bytes(user["dropbox_token"])
    requested_bytes = req.storage_mb * 1024 * 1024

    if available_bytes < requested_bytes:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dropbox only has {available_bytes // (1024*1024)} MB free; "
                f"you requested {req.storage_mb} MB."
            )
        )

    # Insert storage node
    cursor = conn.execute("""
        INSERT INTO storage_nodes (user_id, provider, total_storage, available_storage)
        VALUES (%s, 'dropbox', %s, %s)
        RETURNING node_id
    """, (user["id"], requested_bytes, requested_bytes))
    node_id = cursor.fetchone()["node_id"]

    try:
        reward = blockchain_service.send_seller_reward(wallet, req.storage_mb)
    except Exception as exc:
        conn.rollback()
        conn.close()
        raise HTTPException(
            status_code=502,
            detail=f"Storage reward payment failed: {exc}"
        )

    conn.commit()
    conn.close()

    return RegisterStorageResponse(
        success=True,
        node_id=node_id,
        registered_mb=req.storage_mb,
        reward_tx_hash=reward["tx_hash"],
        reward_pol=reward["reward_pol"],
    )


# ── Storage Pool Info ──────────────────────────────────────────────────────

@app.get("/storage-pool", response_model=StoragePoolResponse)
def storage_pool():
    """Return aggregated pool statistics visible to all users."""
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COUNT(*)           AS node_count,
            SUM(total_storage)      AS total_bytes,
            SUM(available_storage)  AS available_bytes
        FROM storage_nodes
    """).fetchone()
    conn.close()

    total_mb = int((row["total_bytes"] or 0) // (1024 * 1024))
    avail_mb = int((row["available_bytes"] or 0) // (1024 * 1024))

    return StoragePoolResponse(
        total_storage_mb=total_mb,
        available_storage_mb=avail_mb,
        node_count=int(row["node_count"] or 0),
        price_per_100mb_pol=blockchain_service.POL_PER_100MB,
    )


# ── Storage Purchase (Buyer) ───────────────────────────────────────────────

@app.post("/request-storage", response_model=RequestStorageResponse)
def request_storage(req: RequestStorageRequest):
    """
    Buyer requests storage after sending a Polygon transaction.
    Backend verifies the tx_hash on-chain before allocating storage.
    """
    wallet = req.wallet_address.lower().strip()

    # Prevent double-spend: check tx_hash not already used
    conn = get_connection()
    existing_tx = conn.execute(
        "SELECT id FROM storage_allocations WHERE tx_hash = %s", (req.tx_hash,)
    ).fetchone()
    if existing_tx:
        conn.close()
        raise HTTPException(
            status_code=400, detail="Transaction hash already used."
        )

    # Verify on Polygon
    result = blockchain_service.verify_transaction(
        req.tx_hash, wallet, req.storage_mb
    )
    if not result["valid"]:
        conn.close()
        raise HTTPException(status_code=402, detail=result["reason"])

    # Ensure user exists
    user = conn.execute(
        "SELECT id FROM users WHERE wallet_address = %s", (wallet,)
    ).fetchone()
    if user is None:
        conn.execute("INSERT INTO users (wallet_address) VALUES (%s)", (wallet,))
        conn.commit()

    allocated_bytes = req.storage_mb * 1024 * 1024
    conn.execute("""
        INSERT INTO storage_allocations (wallet_address, allocated_bytes, tx_hash)
        VALUES (%s, %s, %s)
    """, (wallet, allocated_bytes, req.tx_hash))
    conn.commit()
    conn.close()

    return RequestStorageResponse(
        success=True,
        message=f"Storage allocated: {req.storage_mb} MB",
        allocated_mb=req.storage_mb,
    )


# ── File Upload ────────────────────────────────────────────────────────────

@app.post("/upload-file")
async def upload_file(
    wallet_address: str = Query(..., description="Buyer wallet address"),
    tx_hash: str = Query(..., description="Payment tx hash (or allocation reference)"),
    file: UploadFile = File(...),
):
    """
    Buyer uploads a file. Backend:
      1. Reads the file bytes.
      2. Verifies the buyer has an active storage allocation.
      3. Encrypts, chunks, distributes across seller Dropboxes.
      4. Records metadata in SQLite.
    """
    wallet = wallet_address.lower().strip()

    # Verify allocation exists
    conn = get_connection()
    alloc = conn.execute("""
        SELECT id, allocated_bytes, used_bytes
        FROM storage_allocations
        WHERE wallet_address = %s AND tx_hash = %s
    """, (wallet, tx_hash)).fetchone()

    if alloc is None:
        conn.close()
        raise HTTPException(status_code=403, detail="No active storage allocation for this tx_hash.")

    file_data = await file.read()
    file_size = len(file_data)

    remaining = alloc["allocated_bytes"] - alloc["used_bytes"]
    if file_size > remaining:
        conn.close()
        raise HTTPException(
            status_code=413,
            detail=(
                f"File size ({file_size // 1024} KB) exceeds remaining "
                f"allocation ({remaining // 1024} KB)."
            )
        )

    try:
        file_id = storage_service.store_file(
            file_data, file.filename, wallet, tx_hash
        )
    except (ValueError, IOError) as exc:
        conn.close()
        raise HTTPException(status_code=507, detail=str(exc))

    # Update used_bytes
    conn.execute("""
        UPDATE storage_allocations
        SET used_bytes = used_bytes + %s
        WHERE id = %s
    """, (file_size, alloc["id"]))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "file_id": file_id,
        "file_name": file.filename,
        "file_size": file_size,
        "message": "File uploaded and distributed successfully.",
    }


# ── File List ──────────────────────────────────────────────────────────────

@app.get("/files")
def list_files(wallet_address: str = Query(...)):
    """Return all files uploaded by a wallet address."""
    wallet = wallet_address.lower().strip()
    files = storage_service.list_files_for_wallet(wallet)
    return {"files": files}


# ── File Download ──────────────────────────────────────────────────────────

@app.get("/download-file/{file_id}")
def download_file(
    file_id: str,
    wallet_address: str = Query("", description="Requester wallet (optional ownership check)"),
):
    """
    Reconstruct the original file from distributed chunks and return it
    as a binary response.
    """
    try:
        file_bytes, original_name = storage_service.retrieve_file(
            file_id, wallet_address
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except IOError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return Response(
        content=file_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{original_name}"'
        },
    )


# ── Frontend Static App (Python + HTML same-origin deployment) ────────────

@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(str(FRONTEND_DIR / "landing.html"))

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

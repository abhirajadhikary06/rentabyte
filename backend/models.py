"""
RentAByte - Pydantic Models
Request and response schemas used by FastAPI endpoints.
"""

from pydantic import BaseModel
from typing import Optional


# ── Wallet ──────────────────────────────────────────────────────────────────

class ConnectWalletRequest(BaseModel):
    wallet_address: str


class ConnectWalletResponse(BaseModel):
    success: bool
    message: str
    wallet_address: str


# ── Dropbox ──────────────────────────────────────────────────────────────────

class ConnectDropboxRequest(BaseModel):
    wallet_address: str
    dropbox_token: str   # long-lived or short-lived access token


class ConnectDropboxResponse(BaseModel):
    success: bool
    message: str


# ── Storage Registration (Seller) ─────────────────────────────────────────────

class RegisterStorageRequest(BaseModel):
    wallet_address: str
    storage_mb: int          # how many MB the seller wants to share


class RegisterStorageResponse(BaseModel):
    success: bool
    node_id: int
    registered_mb: int
    reward_tx_hash: str
    reward_pol: float


# ── Storage Pool ─────────────────────────────────────────────────────────────

class StoragePoolResponse(BaseModel):
    total_storage_mb: int
    available_storage_mb: int
    node_count: int
    price_per_100mb_pol: float


# ── Storage Request (Buyer pays) ──────────────────────────────────────────────

class RequestStorageRequest(BaseModel):
    wallet_address: str
    storage_mb: int
    tx_hash: str             # Polygon transaction hash from MetaMask


class RequestStorageResponse(BaseModel):
    success: bool
    message: str
    allocated_mb: int


# ── File Upload / Download ────────────────────────────────────────────────────

class FileMetaResponse(BaseModel):
    file_id: str
    original_name: str
    file_size: int
    created_at: str


class DownloadResponse(BaseModel):
    file_id: str
    original_name: str

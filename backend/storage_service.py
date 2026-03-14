"""
RentAByte - Storage Service
Core logic for:
  - Encrypting / decrypting files with Fernet (AES-128-CBC under the hood)
  - Splitting files into fixed-size chunks (5 MB default)
  - Distributing chunks across seller nodes
  - Reassembling chunks back into the original file
"""

import os
import hashlib
import uuid
from io import BytesIO
from typing import List, Tuple

from cryptography.fernet import Fernet

from database import get_connection
import dropbox_service
from dotenv import load_dotenv
load_dotenv()  # Load .env file for local development
# ── Constants ──────────────────────────────────────────────────────────────

CHUNK_SIZE_BYTES = int(os.getenv("CHUNK_SIZE_MB", "5")) * 1024 * 1024   # 5 MB

# Master encryption key – store this safely; in production use a KMS.
# For the demo we generate one at startup or read from env.
_RAW_KEY = os.getenv("FERNET_KEY", "")
if _RAW_KEY:
    FERNET_KEY = _RAW_KEY.encode()
else:
    # Generate a key and print it so the operator can persist it.
    FERNET_KEY = Fernet.generate_key()
    print(f"[Storage] Generated Fernet key (add to .env): {FERNET_KEY.decode()}")

fernet = Fernet(FERNET_KEY)


# ── Encryption helpers ──────────────────────────────────────────────────────

def encrypt_data(data: bytes) -> bytes:
    """Encrypt raw bytes using Fernet symmetric encryption."""
    return fernet.encrypt(data)


def decrypt_data(data: bytes) -> bytes:
    """Decrypt Fernet-encrypted bytes."""
    return fernet.decrypt(data)


def sha256_hash(data: bytes) -> str:
    """Return hex SHA-256 of data (used to verify chunk integrity)."""
    return hashlib.sha256(data).hexdigest()


# ── Chunk helpers ───────────────────────────────────────────────────────────

def split_into_chunks(data: bytes) -> List[bytes]:
    """Split bytes into CHUNK_SIZE_BYTES chunks."""
    chunks = []
    for offset in range(0, len(data), CHUNK_SIZE_BYTES):
        chunks.append(data[offset : offset + CHUNK_SIZE_BYTES])
    return chunks


def merge_chunks(chunks: List[bytes]) -> bytes:
    """Reassemble ordered list of chunks into original bytes."""
    return b"".join(chunks)


# ── Node selection ──────────────────────────────────────────────────────────

def get_available_nodes(required_bytes: int) -> List[dict]:
    """
    Return a list of storage nodes that together have at least
    required_bytes of free space.  Each node is a dict with keys:
    node_id, user_id, available_storage, dropbox_token.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT sn.node_id, sn.user_id, sn.available_storage,
               u.dropbox_token
        FROM storage_nodes sn
        JOIN users u ON u.id = sn.user_id
        WHERE sn.available_storage >= %s
        ORDER BY sn.available_storage DESC
    """, (CHUNK_SIZE_BYTES,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def pick_node_for_chunk(nodes: List[dict], chunk_size: int) -> dict | None:
    """Return the node with the most free space that can fit this chunk."""
    for node in nodes:
        if node["available_storage"] >= chunk_size:
            return node
    return None


def deduct_node_storage(node_id: int, bytes_used: int, conn=None):
    """Reduce available_storage on a node after a chunk is stored."""
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    conn.execute(
        "UPDATE storage_nodes SET available_storage = available_storage - %s WHERE node_id = %s",
        (bytes_used, node_id)
    )

    if owns_connection:
        conn.commit()
        conn.close()


def restore_node_storage(node_id: int, bytes_freed: int):
    """Restore available_storage when a file is deleted."""
    conn = get_connection()
    conn.execute(
        "UPDATE storage_nodes SET available_storage = available_storage + %s WHERE node_id = %s",
        (bytes_freed, node_id)
    )
    conn.commit()
    conn.close()


# ── Main upload pipeline ────────────────────────────────────────────────────

def store_file(
    file_data: bytes,
    original_name: str,
    owner_wallet: str,
    tx_hash: str,
) -> str:
    """
    Full pipeline:
      1. Encrypt the file.
      2. Split into chunks.
      3. Assign each chunk to an available seller node.
      4. Upload chunk to that seller's Dropbox.
      5. Record metadata in SQLite.

    Returns the file_id (UUID string).
    Raises ValueError if there is not enough distributed storage.
    """
    file_id = str(uuid.uuid4())
    encrypted = encrypt_data(file_data)
    chunks = split_into_chunks(encrypted)

    nodes = get_available_nodes(CHUNK_SIZE_BYTES)
    if not nodes:
        raise ValueError("No storage nodes available with enough free space.")

    conn = get_connection()

    # ── Insert file record ──────────────────────────────────────────────────
    conn.execute("""
        INSERT INTO files (file_id, owner_wallet, original_name, file_size, tx_hash)
        VALUES (%s, %s, %s, %s, %s)
    """, (file_id, owner_wallet, original_name, len(file_data), tx_hash))

    # ── Distribute chunks ───────────────────────────────────────────────────
    node_pool = list(nodes)  # mutable copy
    for idx, chunk in enumerate(chunks):
        node = pick_node_for_chunk(node_pool, len(chunk))
        if node is None:
            conn.rollback()
            conn.close()
            raise ValueError(
                f"Not enough storage across nodes for chunk {idx}. "
                "Ask more sellers to register storage."
            )

        chunk_hash = sha256_hash(chunk)
        dropbox_path = f"/rentabyte_chunks/{file_id}_chunk_{idx:04d}.bin"

        # Upload to seller's Dropbox
        ok = dropbox_service.upload_chunk(
            node["dropbox_token"], chunk, dropbox_path
        )
        if not ok:
            conn.rollback()
            conn.close()
            raise IOError(
                f"Failed to upload chunk {idx} to node {node['node_id']}."
            )

        # Record chunk metadata
        conn.execute("""
            INSERT INTO chunks
              (file_id, node_id, chunk_index, chunk_hash, dropbox_path, chunk_size)
                        VALUES (%s, %s, %s, %s, %s, %s)
        """, (file_id, node["node_id"], idx, chunk_hash, dropbox_path, len(chunk)))

        # Deduct from node's in-memory pool so the next chunk picks correctly
        for n in node_pool:
            if n["node_id"] == node["node_id"]:
                n["available_storage"] -= len(chunk)
                break

        # Deduct from DB using the same transaction/connection to avoid lock contention
        deduct_node_storage(node["node_id"], len(chunk), conn=conn)

    conn.commit()
    conn.close()
    return file_id


# ── Main download pipeline ──────────────────────────────────────────────────

def retrieve_file(file_id: str, requester_wallet: str) -> Tuple[bytes, str]:
    """
    Full pipeline:
      1. Load chunk metadata from SQLite.
      2. Fetch each chunk from its seller's Dropbox.
      3. Verify SHA-256 hash of each chunk.
      4. Merge chunks.
      5. Decrypt.

    Returns (file_bytes, original_filename).
    Raises ValueError / IOError on failure.
    """
    conn = get_connection()

    file_row = conn.execute(
        "SELECT * FROM files WHERE file_id = %s", (file_id,)
    ).fetchone()

    if file_row is None:
        conn.close()
        raise ValueError(f"File {file_id} not found.")

    # Ownership check (commented out to allow demo downloads without auth)
    # if file_row["owner_wallet"].lower() != requester_wallet.lower():
    #     conn.close()
    #     raise PermissionError("You do not own this file.")

    chunk_rows = conn.execute("""
        SELECT c.chunk_index, c.chunk_hash, c.dropbox_path, c.node_id,
               u.dropbox_token
        FROM chunks c
        JOIN storage_nodes sn ON sn.node_id = c.node_id
        JOIN users u ON u.id = sn.user_id
        WHERE c.file_id = %s
        ORDER BY c.chunk_index ASC
    """, (file_id,)).fetchall()
    conn.close()

    if not chunk_rows:
        raise ValueError("No chunks found for this file.")

    raw_chunks: List[bytes] = []
    for row in chunk_rows:
        chunk_data = dropbox_service.download_chunk(
            row["dropbox_token"], row["dropbox_path"]
        )
        if chunk_data is None:
            raise IOError(
                f"Failed to download chunk {row['chunk_index']} "
                f"from node {row['node_id']}."
            )

        # Verify integrity
        if sha256_hash(chunk_data) != row["chunk_hash"]:
            raise IOError(
                f"Chunk {row['chunk_index']} hash mismatch – possible corruption."
            )

        raw_chunks.append(chunk_data)

    encrypted_file = merge_chunks(raw_chunks)
    original_data = decrypt_data(encrypted_file)
    return original_data, file_row["original_name"]


# ── List files for a wallet ─────────────────────────────────────────────────

def list_files_for_wallet(owner_wallet: str) -> List[dict]:
    """Return all files owned by a wallet address."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT file_id, original_name, file_size, created_at
        FROM files
        WHERE owner_wallet = %s
        ORDER BY created_at DESC
    """, (owner_wallet,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

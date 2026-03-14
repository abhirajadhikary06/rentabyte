"""
RentAByte - Database Module
Handles SQLite initialization and connection management.
"""

import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "rentabyte.db")


def get_connection():
    """Return a new SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrency
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # Users table – one row per wallet address
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address   TEXT UNIQUE NOT NULL,
            dropbox_token    TEXT,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # StorageNodes – storage contributed by sellers
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_nodes (
            node_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL REFERENCES users(id),
            provider          TEXT NOT NULL DEFAULT 'dropbox',
            total_storage     INTEGER NOT NULL,   -- bytes
            available_storage INTEGER NOT NULL,   -- bytes
            created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # Files – metadata for each file uploaded by a buyer
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id         TEXT PRIMARY KEY,          -- UUID
            owner_wallet    TEXT NOT NULL,
            original_name   TEXT NOT NULL,
            file_size       INTEGER NOT NULL,          -- bytes
            tx_hash         TEXT,                      -- payment tx
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # Chunks – one row per 5 MB chunk of a file
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id       TEXT NOT NULL REFERENCES files(file_id),
            node_id       INTEGER NOT NULL REFERENCES storage_nodes(node_id),
            chunk_index   INTEGER NOT NULL,
            chunk_hash    TEXT NOT NULL,
            dropbox_path  TEXT NOT NULL,
            chunk_size    INTEGER NOT NULL   -- bytes
        )
    """)

    # ------------------------------------------------------------------
    # StorageAllocations – tracks storage rented by buyers
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_allocations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_address  TEXT NOT NULL,
            allocated_bytes INTEGER NOT NULL,
            used_bytes      INTEGER NOT NULL DEFAULT 0,
            tx_hash         TEXT NOT NULL UNIQUE,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")

"""
RentAByte - Database Module
Handles PostgreSQL (Neon) initialization and connection management.
"""

import os

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
load_dotenv()  # Load .env file for local development
DATABASE_URL = os.getenv("NEONDB_DATABASE_URL", "").strip()


class PostgresConnection:
    """Compatibility wrapper to support conn.execute(...) style calls."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        cursor = self._conn.cursor()
        cursor.execute(query, params or ())
        return cursor

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, item):
        return getattr(self._conn, item)


def get_connection():
    """Return a new PostgreSQL connection with dict-like row access."""
    if not DATABASE_URL:
        raise RuntimeError(
            "NEONDB_DATABASE_URL is not set. Please configure backend/.env."
        )

    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=RealDictCursor,
    )
    conn.autocommit = False
    return PostgresConnection(conn)


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # Users table – one row per wallet address
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               BIGSERIAL PRIMARY KEY,
            wallet_address   TEXT UNIQUE NOT NULL,
            dropbox_token    TEXT,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # StorageNodes – storage contributed by sellers
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_nodes (
            node_id           BIGSERIAL PRIMARY KEY,
            user_id           BIGINT NOT NULL REFERENCES users(id),
            provider          TEXT NOT NULL DEFAULT 'dropbox',
            total_storage     BIGINT NOT NULL,   -- bytes
            available_storage BIGINT NOT NULL,   -- bytes
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            file_size       BIGINT NOT NULL,           -- bytes
            tx_hash         TEXT,                      -- payment tx
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ------------------------------------------------------------------
    # Chunks – one row per 5 MB chunk of a file
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id      BIGSERIAL PRIMARY KEY,
            file_id       TEXT NOT NULL REFERENCES files(file_id),
            node_id       BIGINT NOT NULL REFERENCES storage_nodes(node_id),
            chunk_index   INTEGER NOT NULL,
            chunk_hash    TEXT NOT NULL,
            dropbox_path  TEXT NOT NULL,
            chunk_size    BIGINT NOT NULL   -- bytes
        )
    """)

    # ------------------------------------------------------------------
    # StorageAllocations – tracks storage rented by buyers
    # ------------------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_allocations (
            id              BIGSERIAL PRIMARY KEY,
            wallet_address  TEXT NOT NULL,
            allocated_bytes BIGINT NOT NULL,
            used_bytes      BIGINT NOT NULL DEFAULT 0,
            tx_hash         TEXT NOT NULL UNIQUE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")

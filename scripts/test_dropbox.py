"""
RentAByte - Dropbox Connection Test
Run this locally to verify your Dropbox access token works before using the app.

Usage:
    cd C:\\Abhiraj\\OpenSource\\rentabyte
    python scripts/test_dropbox.py

The script will:
  1. Authenticate with your token
  2. Check available storage space
  3. Upload a small test chunk
  4. Download it back and verify integrity
  5. Delete the test chunk
"""

import sys
import os
import hashlib

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dropbox_service import (
    get_client,
    get_available_storage_bytes,
    upload_chunk,
    download_chunk,
    delete_chunk,
)

# ── Config ────────────────────────────────────────────────────────────────────

# Paste your Dropbox access token here, or set env var DROPBOX_TOKEN
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN", "")

TEST_PATH = "/rentabyte_chunks/_test_connection.bin"
TEST_DATA = b"RentAByte dropbox test chunk - " + os.urandom(64)

# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(title=""):
    width = 52
    if title:
        pad = (width - len(title) - 2) // 2
        print("─" * pad + f" {title} " + "─" * pad)
    else:
        print("─" * width)

def ok(msg):  print(f"  ✅  {msg}")
def fail(msg): print(f"  ❌  {msg}"); sys.exit(1)
def info(msg): print(f"  ℹ️   {msg}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    sep("RentAByte Dropbox Test")

    if not DROPBOX_TOKEN:
        fail(
            "No token found.\n"
            "  Set env var:  $env:DROPBOX_TOKEN='sl.your_token_here'\n"
            "  or edit DROPBOX_TOKEN in this script."
        )

    # 1. Authenticate
    info("Authenticating …")
    try:
        dbx = get_client(DROPBOX_TOKEN)
        account = dbx.users_get_current_account()
        ok(f"Authenticated as: {account.name.display_name} ({account.email})")
    except Exception as exc:
        fail(f"Auth failed: {exc}")

    sep()

    # 2. Check storage space
    info("Checking available storage …")
    available_bytes = get_available_storage_bytes(DROPBOX_TOKEN)
    available_mb = available_bytes / (1024 * 1024)
    available_gb = available_bytes / (1024 ** 3)
    if available_bytes == 0:
        fail("Could not retrieve storage info (token may lack permissions).")
    ok(f"Available space: {available_mb:,.1f} MB  ({available_gb:.2f} GB)")

    sep()

    # 3. Upload test chunk
    info(f"Uploading test chunk to {TEST_PATH} …")
    original_hash = hashlib.sha256(TEST_DATA).hexdigest()
    success = upload_chunk(DROPBOX_TOKEN, TEST_DATA, TEST_PATH)
    if not success:
        fail("Upload failed.")
    ok(f"Uploaded {len(TEST_DATA)} bytes  (SHA-256: {original_hash[:16]}…)")

    sep()

    # 4. Download and verify
    info("Downloading chunk and verifying integrity …")
    downloaded = download_chunk(DROPBOX_TOKEN, TEST_PATH)
    if downloaded is None:
        fail("Download returned None.")
    downloaded_hash = hashlib.sha256(downloaded).hexdigest()
    if downloaded_hash != original_hash:
        fail(f"Hash mismatch!\n  expected: {original_hash}\n  got:      {downloaded_hash}")
    ok(f"Downloaded {len(downloaded)} bytes — hash matches ✔")

    sep()

    # 5. Delete test chunk
    info(f"Deleting test chunk …")
    deleted = delete_chunk(DROPBOX_TOKEN, TEST_PATH)
    if not deleted:
        fail("Delete failed.")
    ok("Test chunk removed from Dropbox")

    sep()
    print()
    print("  🎉  All tests passed — Dropbox is ready for RentAByte!")
    print()


if __name__ == "__main__":
    main()

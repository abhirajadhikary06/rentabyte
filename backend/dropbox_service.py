"""
RentAByte - Dropbox Service
Handles all interactions with the Dropbox API:
  - Checking available space
  - Uploading encrypted file chunks
  - Downloading file chunks
"""

import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
import io


CHUNK_FOLDER = "/rentabyte_chunks"   # folder created in the seller's Dropbox


def get_client(access_token: str) -> dropbox.Dropbox:
    """Return an authenticated Dropbox client."""
    return dropbox.Dropbox(access_token)


def get_available_storage_bytes(access_token: str) -> int:
    """
    Query the seller's Dropbox account and return available bytes.
    Returns 0 on any error (invalid token, revoked, etc.).
    """
    try:
        dbx = get_client(access_token)
        usage = dbx.users_get_space_usage()
        allocated = usage.allocation.get_individual().allocated
        used = usage.used
        available = max(0, allocated - used)
        return available
    except (ApiError, AuthError) as exc:
        print(f"[Dropbox] get_available_storage_bytes error: {exc}")
        return 0


def upload_chunk(access_token: str, chunk_data: bytes, dropbox_path: str) -> bool:
    """
    Upload a single encrypted chunk to the seller's Dropbox.
    dropbox_path example: /rentabyte_chunks/file_abc_chunk_0.bin
    Returns True on success.
    """
    try:
        dbx = get_client(access_token)
        dbx.files_upload(
            chunk_data,
            dropbox_path,
            mode=WriteMode("overwrite"),
            mute=True
        )
        return True
    except (ApiError, AuthError) as exc:
        print(f"[Dropbox] upload_chunk error at {dropbox_path}: {exc}")
        return False


def download_chunk(access_token: str, dropbox_path: str) -> bytes | None:
    """
    Download a single chunk from a seller's Dropbox.
    Returns raw bytes or None on failure.
    """
    try:
        dbx = get_client(access_token)
        _, response = dbx.files_download(dropbox_path)
        return response.content
    except (ApiError, AuthError) as exc:
        print(f"[Dropbox] download_chunk error at {dropbox_path}: {exc}")
        return None


def delete_chunk(access_token: str, dropbox_path: str) -> bool:
    """Delete a chunk from a seller's Dropbox (used when file is deleted)."""
    try:
        dbx = get_client(access_token)
        dbx.files_delete_v2(dropbox_path)
        return True
    except (ApiError, AuthError) as exc:
        print(f"[Dropbox] delete_chunk error at {dropbox_path}: {exc}")
        return False

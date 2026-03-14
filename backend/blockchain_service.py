"""
RentAByte - Blockchain Service
Verifies Polygon Amoy Testnet transactions using Web3.py.

Payment rule: 1 POL = 100 MB of storage.
Contract address is optional – for a simple hackathon demo we verify
native MATIC/POL transfers directly on-chain rather than requiring a
deployed ERC-20 contract.
"""

import os
from web3 import Web3
from web3.exceptions import TransactionNotFound
from dotenv import load_dotenv
load_dotenv()  # Load .env file for local development
# ── RPC Configuration ──────────────────────────────────────────────────────

POLYGON_AMOY_RPC = os.getenv(
    "POLYGON_RPC_URL",
    "https://rpc-amoy.polygon.technology"   # public Amoy testnet RPC
)

# Contract address for the RentAByte smart contract (deploy with Hardhat)
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")

# Minimum POL per 100 MB (in wei).  0.001 POL = 100 MB for demo purposes.
POL_PER_100MB = float(os.getenv("POL_PER_100MB", "0.001"))

# Platform wallet that receives payments
PLATFORM_WALLET = os.getenv("PLATFORM_WALLET", "").lower()

w3 = Web3(Web3.HTTPProvider(POLYGON_AMOY_RPC))


def is_connected() -> bool:
    """Check RPC connectivity."""
    return w3.is_connected()


def get_expected_wei(storage_mb: int) -> int:
    """
    Calculate expected payment in wei for storage_mb megabytes.
    100 MB costs POL_PER_100MB POL.
    """
    pol_amount = (storage_mb / 100) * POL_PER_100MB
    return w3.to_wei(pol_amount, "ether")


def verify_transaction(tx_hash: str, buyer_wallet: str, storage_mb: int) -> dict:
    """
    Verify a Polygon transaction on-chain.

    Checks:
      1. Transaction exists and has been mined.
      2. Sender matches the buyer wallet.
      3. Receiver is the platform wallet (or contract).
      4. Value >= expected payment for storage_mb.

    Returns a dict with keys:
      valid (bool), reason (str), value_wei (int)
    """
    if not w3.is_connected():
        return {"valid": False, "reason": "Cannot connect to Polygon RPC", "value_wei": 0}

    try:
        tx = w3.eth.get_transaction(tx_hash)
    except TransactionNotFound:
        return {"valid": False, "reason": "Transaction not found on-chain", "value_wei": 0}

    if tx is None:
        return {"valid": False, "reason": "Transaction is None", "value_wei": 0}

    # Check the transaction is mined (has a block number)
    if tx.get("blockNumber") is None:
        return {"valid": False, "reason": "Transaction is still pending", "value_wei": 0}

    # Verify sender
    if tx["from"].lower() != buyer_wallet.lower():
        return {
            "valid": False,
            "reason": f"Sender mismatch: expected {buyer_wallet}, got {tx['from']}",
            "value_wei": int(tx["value"])
        }

    # Verify receiver (accept contract and/or platform wallet)
    receiver = tx.get("to", "").lower() if tx.get("to") else ""
    valid_receivers = {
        addr.lower()
        for addr in (CONTRACT_ADDRESS, PLATFORM_WALLET)
        if addr
    }
    if valid_receivers and receiver not in valid_receivers:
        return {
            "valid": False,
            "reason": (
                "Receiver mismatch: expected one of "
                f"{', '.join(sorted(valid_receivers))}, got {receiver}"
            ),
            "value_wei": int(tx["value"])
        }

    # Verify value
    expected_wei = get_expected_wei(storage_mb)
    paid_wei = int(tx["value"])
    if paid_wei < expected_wei:
        return {
            "valid": False,
            "reason": (
                f"Underpayment: expected {expected_wei} wei "
                f"({storage_mb} MB), got {paid_wei} wei"
            ),
            "value_wei": paid_wei
        }

    return {
        "valid": True,
        "reason": "Transaction verified successfully",
        "value_wei": paid_wei
    }


def get_balance_pol(wallet_address: str) -> float:
    """Return the POL/MATIC balance of a wallet (for display purposes)."""
    try:
        balance_wei = w3.eth.get_balance(
            Web3.to_checksum_address(wallet_address)
        )
        return float(w3.from_wei(balance_wei, "ether"))
    except Exception as exc:
        print(f"[Blockchain] get_balance error: {exc}")
        return 0.0

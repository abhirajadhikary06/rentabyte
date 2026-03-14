"""
RentAByte - verify_transaction.py
Standalone script to verify a Polygon transaction from the command line.

Usage:
    python verify_transaction.py <tx_hash> <buyer_wallet> <storage_mb>

Example:
    python verify_transaction.py 0xabc...def 0x1234...abcd 500
"""

import sys
import os
import re
from dotenv import load_dotenv
load_dotenv()  # Load .env file for local development
# Allow running from project root or scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blockchain_service import verify_transaction, is_connected, get_balance_pol


def _is_hex(value: str, n_bytes: int) -> bool:
    """Return True when value is 0x-prefixed hex with exact byte length."""
    pattern = rf"^0x[a-fA-F0-9]{{{n_bytes * 2}}}$"
    return bool(re.match(pattern, value or ""))

def main():
    if len(sys.argv) != 4:
        print("Usage: python verify_transaction.py <tx_hash> <buyer_wallet> <storage_mb>")
        sys.exit(1)

    tx_hash    = sys.argv[1]
    buyer      = sys.argv[2]
    try:
        storage_mb = int(sys.argv[3])
    except ValueError:
        print("[ERROR] storage_mb must be an integer, e.g. 500")
        sys.exit(1)

    if not _is_hex(tx_hash, 32):
        print("[ERROR] Invalid tx hash format. Expected 0x + 64 hex chars.")
        print("        Example: 0x9f... (66 total chars)")
        sys.exit(1)

    if not _is_hex(buyer, 20):
        print("[ERROR] Invalid buyer wallet format. Expected 0x + 40 hex chars.")
        print("        Example: 0xC913d8B68ACCFE2b1AEB8805D48D802547C827A1")
        sys.exit(1)

    if storage_mb <= 0:
        print("[ERROR] storage_mb must be greater than 0")
        sys.exit(1)

    print("=" * 60)
    print("RentAByte - Transaction Verifier")
    print("=" * 60)

    if not is_connected():
        print("[ERROR] Cannot connect to Polygon RPC endpoint.")
        print("        Check your POLYGON_RPC_URL environment variable.")
        sys.exit(1)

    print(f"Verifying transaction: {tx_hash}")
    print(f"Buyer wallet:          {buyer}")
    print(f"Storage requested:     {storage_mb} MB")
    print("-" * 60)

    result = verify_transaction(tx_hash, buyer, storage_mb)

    status = "✅ VALID" if result["valid"] else "❌ INVALID"
    print(f"Status:    {status}")
    print(f"Reason:    {result['reason']}")
    print(f"Value:     {result['value_wei']} wei")

    # Also show buyer balance
    balance = get_balance_pol(buyer)
    print(f"Balance:   {balance:.6f} POL")
    print("=" * 60)

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()

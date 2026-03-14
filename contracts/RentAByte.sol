// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title RentAByte
 * @notice Simple storage marketplace payment contract on Polygon Amoy Testnet.
 *
 * Flow:
 *   1. Buyer calls payForStorage() with the required POL amount.
 *   2. Contract emits StoragePurchased event.
 *   3. Backend listens for the event (or verifies the tx) and allocates storage.
 *   4. Platform owner can withdraw accumulated funds.
 *
 * Pricing: POL_PER_100MB POL (in wei) per 100 MB of storage.
 */
contract RentAByte {

    // ── State ──────────────────────────────────────────────────────────────

    address public owner;

    /// Price in wei for 100 MB of storage (adjustable by owner).
    uint256 public pricePerHundredMBWei;

    /// Tracks storage purchased per buyer (in MB).
    mapping(address => uint256) public storagePurchasedMB;

    // ── Events ─────────────────────────────────────────────────────────────

    event StoragePurchased(
        address indexed buyer,
        uint256 storageMB,
        uint256 amountPaid
    );

    event PriceUpdated(uint256 newPriceWei);

    event Withdrawn(address indexed to, uint256 amount);

    // ── Constructor ────────────────────────────────────────────────────────

    /**
     * @param _pricePerHundredMBWei Initial price in wei for 100 MB.
     *        Example: 0.01 POL = 10_000_000_000_000_000 wei
     */
    constructor(uint256 _pricePerHundredMBWei) {
        owner = msg.sender;
        pricePerHundredMBWei = _pricePerHundredMBWei;
    }

    // ── Modifiers ──────────────────────────────────────────────────────────

    modifier onlyOwner() {
        require(msg.sender == owner, "RentAByte: caller is not the owner");
        _;
    }

    // ── Core Functions ─────────────────────────────────────────────────────

    /**
     * @notice Buyer pays for storage. Must send exactly the required amount.
     * @param storageMB Amount of storage requested in megabytes.
     */
    function payForStorage(uint256 storageMB) external payable {
        require(storageMB > 0, "RentAByte: storageMB must be > 0");

        uint256 required = requiredPayment(storageMB);
        require(msg.value >= required, "RentAByte: insufficient payment");

        storagePurchasedMB[msg.sender] += storageMB;

        // Refund overpayment
        if (msg.value > required) {
            payable(msg.sender).transfer(msg.value - required);
        }

        emit StoragePurchased(msg.sender, storageMB, required);
    }

    /**
     * @notice Calculate the required payment for a given storage amount.
     * @param storageMB Amount of storage in MB.
     * @return Required payment in wei.
     */
    function requiredPayment(uint256 storageMB) public view returns (uint256) {
        // ceil division: (storageMB + 99) / 100 * pricePerHundredMBWei
        uint256 units = (storageMB + 99) / 100;
        return units * pricePerHundredMBWei;
    }

    /**
     * @notice Owner updates the storage price.
     * @param newPriceWei New price in wei per 100 MB.
     */
    function updatePrice(uint256 newPriceWei) external onlyOwner {
        require(newPriceWei > 0, "RentAByte: price must be > 0");
        pricePerHundredMBWei = newPriceWei;
        emit PriceUpdated(newPriceWei);
    }

    /**
     * @notice Owner withdraws all accumulated funds.
     */
    function withdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "RentAByte: nothing to withdraw");
        payable(owner).transfer(balance);
        emit Withdrawn(owner, balance);
    }

    /**
     * @notice Transfer contract ownership.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "RentAByte: zero address");
        owner = newOwner;
    }

    /// @notice Allow contract to receive plain POL transfers.
    receive() external payable {}
}

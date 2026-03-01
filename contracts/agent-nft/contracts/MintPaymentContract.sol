// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * Payment contract for Workmage Agent NFT mints.
 * User calls payForMint(recipient) with AVAX >= minMintFee.
 * Emits MintPaymentReceived; forwards AVAX to treasury.
 * Watcher service uses recipient to map payment -> mint intent -> mint.
 */
contract MintPaymentContract is Ownable, ReentrancyGuard {
    address payable public treasury;
    uint256 public minMintFee;

    event MintPaymentReceived(address indexed payer, address indexed recipient, uint256 amount);
    event MinMintFeeUpdated(uint256 oldFee, uint256 newFee);
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);

    constructor(address initialOwner, address payable treasury_, uint256 minMintFee_) Ownable(initialOwner) {
        treasury = treasury_;
        minMintFee = minMintFee_;
    }

    function payForMint(address recipient) external payable nonReentrant {
        require(recipient != address(0), "recipient zero");
        require(msg.value >= minMintFee, "value below min mint fee");
        emit MintPaymentReceived(msg.sender, recipient, msg.value);
        (bool sent,) = treasury.call{value: msg.value}("");
        require(sent, "transfer failed");
    }

    function getMintFee() external view returns (uint256) {
        return minMintFee;
    }

    function setMinMintFee(uint256 newFee) external onlyOwner {
        uint256 old = minMintFee;
        minMintFee = newFee;
        emit MinMintFeeUpdated(old, newFee);
    }

    function setTreasury(address payable newTreasury) external onlyOwner {
        require(newTreasury != address(0), "treasury zero");
        address old = treasury;
        treasury = newTreasury;
        emit TreasuryUpdated(old, newTreasury);
    }
}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

bytes32 constant MINTER_ROLE = keccak256("MINTER_ROLE");

/**
 * Shared agent identity NFT for Workmage.
 * Minter can mint tokens; owner manages URI and roles.
 * Used with ERC-6551 TBA and ERC-8004 identity flows.
 */
contract WorkmageAgentNFT is ERC721, Ownable, AccessControl {
    string private _baseTokenURI;
    uint256 private _nextTokenId;

    constructor(
        string memory name_,
        string memory symbol_,
        string memory baseTokenURI_
    ) ERC721(name_, symbol_) Ownable(msg.sender) {
        _baseTokenURI = baseTokenURI_;
        _nextTokenId = 1;
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    function mint(address to) external onlyRole(MINTER_ROLE) returns (uint256) {
        uint256 tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        return tokenId;
    }

    function setBaseURI(string calldata baseTokenURI_) external onlyOwner {
        _baseTokenURI = baseTokenURI_;
    }

    function _baseURI() internal view override returns (string memory) {
        return _baseTokenURI;
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, AccessControl) returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}

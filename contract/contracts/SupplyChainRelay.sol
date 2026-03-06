// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SupplyChainRelay {
    address public owner;

    struct CustodyRecord {
        string shipmentId;
        string bundleId;
        string bundleHash;
        address previousCustodian;
        address newCustodian;
        string ipfsCid;
        uint256 timestamp;
    }

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event AuthorizedCallerUpdated(address indexed caller, bool allowed);
    event CustodyTransferred(
        string shipmentId,
        string bundleId,
        string bundleHash,
        address indexed previousCustodian,
        address indexed newCustodian,
        string ipfsCid,
        uint256 timestamp
    );

    mapping(string => address) public currentCustodian;
    mapping(address => bool) public authorizedCallers;
    mapping(bytes32 => bool) public anchoredBundleKeys;
    mapping(string => uint256) public shipmentTransferCount;
    CustodyRecord[] public records;

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedCallers[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit AuthorizedCallerUpdated(msg.sender, true);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "INVALID_OWNER");
        address previousOwner = owner;
        owner = newOwner;
        emit OwnershipTransferred(previousOwner, newOwner);
    }

    function setAuthorizedCaller(address caller, bool allowed) external onlyOwner {
        require(caller != address(0), "INVALID_CALLER");
        authorizedCallers[caller] = allowed;
        emit AuthorizedCallerUpdated(caller, allowed);
    }

    function recordsCount() external view returns (uint256) {
        return records.length;
    }

    function transferCustody(
        string calldata shipmentId,
        string calldata bundleId,
        string calldata bundleHash,
        address previousCustodian,
        string calldata ipfsCid
    ) external {
        require(authorizedCallers[msg.sender], "CALLER_NOT_AUTHORIZED");
        require(bytes(shipmentId).length > 0, "EMPTY_SHIPMENT_ID");
        require(bytes(bundleId).length > 0, "EMPTY_BUNDLE_ID");
        require(bytes(bundleHash).length > 0, "EMPTY_BUNDLE_HASH");
        require(bytes(ipfsCid).length > 0, "EMPTY_IPFS_CID");

        bytes32 bundleKey = keccak256(abi.encodePacked(shipmentId, "|", bundleId));
        require(!anchoredBundleKeys[bundleKey], "BUNDLE_ALREADY_ANCHORED");

        address expectedPrevious = currentCustodian[shipmentId];
        if (expectedPrevious == address(0)) {
            require(previousCustodian == address(0), "INVALID_INITIAL_PREVIOUS_CUSTODIAN");
        } else {
            require(previousCustodian == expectedPrevious, "CUSTODY_SEQUENCE_MISMATCH");
        }

        anchoredBundleKeys[bundleKey] = true;
        currentCustodian[shipmentId] = msg.sender;
        shipmentTransferCount[shipmentId] += 1;
        records.push(
            CustodyRecord({
                shipmentId: shipmentId,
                bundleId: bundleId,
                bundleHash: bundleHash,
                previousCustodian: previousCustodian,
                newCustodian: msg.sender,
                ipfsCid: ipfsCid,
                timestamp: block.timestamp
            })
        );

        emit CustodyTransferred(
            shipmentId,
            bundleId,
            bundleHash,
            previousCustodian,
            msg.sender,
            ipfsCid,
            block.timestamp
        );
    }
}

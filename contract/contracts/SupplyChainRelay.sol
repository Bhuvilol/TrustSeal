// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SupplyChainRelay {
    struct CustodyRecord {
        string shipmentId;
        address previousCustodian;
        address newCustodian;
        string ipfsCid;
        uint256 timestamp;
    }

    event CustodyTransferred(
        string shipmentId,
        address indexed previousCustodian,
        address indexed newCustodian,
        string ipfsCid,
        uint256 timestamp
    );

    mapping(string => address) public currentCustodian;
    CustodyRecord[] public records;

    function transferCustody(
        string calldata shipmentId,
        address previousCustodian,
        string calldata ipfsCid
    ) external {
        currentCustodian[shipmentId] = msg.sender;
        records.push(
            CustodyRecord({
                shipmentId: shipmentId,
                previousCustodian: previousCustodian,
                newCustodian: msg.sender,
                ipfsCid: ipfsCid,
                timestamp: block.timestamp
            })
        );

        emit CustodyTransferred(shipmentId, previousCustodian, msg.sender, ipfsCid, block.timestamp);
    }
}
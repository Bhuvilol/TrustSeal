const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SupplyChainRelay Phase 5", function () {
  async function expectRevertWithReason(promise, reason) {
    try {
      await promise;
      expect.fail("Expected transaction to revert");
    } catch (error) {
      expect(String(error.message || error)).to.include(reason);
    }
  }

  async function deployFixture() {
    const [owner, other] = await ethers.getSigners();
    const factory = await ethers.getContractFactory("SupplyChainRelay");
    const relay = await factory.deploy();
    await relay.waitForDeployment();
    return { relay, owner, other };
  }

  it("emits CustodyTransferred with shipment, bundle, hash and cid", async function () {
    const { relay, owner } = await deployFixture();
    const shipmentId = "shipment-001";
    const bundleId = "bundle-001";
    const bundleHash = "0xabc123";
    const previousCustodian = ethers.ZeroAddress;
    const ipfsCid = "bafybeigdyrzt";

    const tx = await relay.transferCustody(shipmentId, bundleId, bundleHash, previousCustodian, ipfsCid);
    const receipt = await tx.wait();
    const event = receipt.logs
      .map((log) => {
        try {
          return relay.interface.parseLog(log);
        } catch {
          return null;
        }
      })
      .find((parsed) => parsed && parsed.name === "CustodyTransferred");

    expect(event).to.not.equal(undefined);
    expect(event.args.shipmentId).to.equal(shipmentId);
    expect(event.args.bundleId).to.equal(bundleId);
    expect(event.args.bundleHash).to.equal(bundleHash);
    expect(event.args.previousCustodian).to.equal(previousCustodian);
    expect(event.args.newCustodian).to.equal(owner.address);
    expect(event.args.ipfsCid).to.equal(ipfsCid);
    expect(event.args.timestamp).to.be.gt(0n);
  });

  it("stores full custody record fields including bundle data", async function () {
    const { relay } = await deployFixture();
    const shipmentId = "shipment-002";
    const bundleId = "bundle-002";
    const bundleHash = "hash-002";
    const previousCustodian = ethers.ZeroAddress;
    const ipfsCid = "bafybeibundle2";

    await relay.transferCustody(shipmentId, bundleId, bundleHash, previousCustodian, ipfsCid);
    const record = await relay.records(0);

    expect(record.shipmentId).to.equal(shipmentId);
    expect(record.bundleId).to.equal(bundleId);
    expect(record.bundleHash).to.equal(bundleHash);
    expect(record.previousCustodian).to.equal(previousCustodian);
    expect(record.newCustodian).to.not.equal(ethers.ZeroAddress);
    expect(record.ipfsCid).to.equal(ipfsCid);
    expect(record.timestamp).to.be.gt(0n);
  });

  it("updates currentCustodian per shipment key", async function () {
    const { relay, owner, other } = await deployFixture();
    const shipmentId = "shipment-003";

    await relay.connect(owner).transferCustody(shipmentId, "bundle-a", "hash-a", ethers.ZeroAddress, "cid-a");
    expect(await relay.currentCustodian(shipmentId)).to.equal(owner.address);

    await relay.connect(owner).setAuthorizedCaller(other.address, true);
    await relay.connect(other).transferCustody(shipmentId, "bundle-b", "hash-b", owner.address, "cid-b");
    expect(await relay.currentCustodian(shipmentId)).to.equal(other.address);
  });

  it("rejects unauthorized caller", async function () {
    const { relay, other } = await deployFixture();
    await expectRevertWithReason(
      relay.connect(other).transferCustody("shipment-x", "bundle-x", "hash-x", ethers.ZeroAddress, "cid-x"),
      "CALLER_NOT_AUTHORIZED"
    );
  });

  it("rejects custody sequence mismatch", async function () {
    const { relay, owner, other } = await deployFixture();
    const shipmentId = "shipment-004";
    await relay.connect(owner).transferCustody(shipmentId, "bundle-a", "hash-a", ethers.ZeroAddress, "cid-a");
    await relay.connect(owner).setAuthorizedCaller(other.address, true);

    await expectRevertWithReason(
      relay.connect(other).transferCustody(shipmentId, "bundle-b", "hash-b", ethers.ZeroAddress, "cid-b"),
      "CUSTODY_SEQUENCE_MISMATCH"
    );
  });

  it("rejects duplicate bundle id for same shipment", async function () {
    const { relay, owner, other } = await deployFixture();
    const shipmentId = "shipment-005";
    await relay.connect(owner).transferCustody(shipmentId, "bundle-a", "hash-a", ethers.ZeroAddress, "cid-a");
    await relay.connect(owner).setAuthorizedCaller(other.address, true);

    await expectRevertWithReason(
      relay.connect(other).transferCustody(shipmentId, "bundle-a", "hash-b", owner.address, "cid-b"),
      "BUNDLE_ALREADY_ANCHORED"
    );
  });
});

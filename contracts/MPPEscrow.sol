// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MPPEscrow - Machine Payment Protocol Autonomous A2A Escrow
 * @notice Holds USDC on Base (Chain ID 8453) conditioned on DharmaGate sealed evidence.
 * @dev Deployment target: Base Mainnet (USDC: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913).
 */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract MPPEscrow {
    IERC20 public immutable usdc;
    address public immutable owner;

    enum EscrowStatus { None, Locked, Released, Refunded }

    struct Invoice {
        address delegator;
        address worker;
        uint256 amountUsdc;
        bytes32 taskHash;
        uint256 expirationTimestamp;
        EscrowStatus status;
    }

    mapping(bytes32 => Invoice) public invoices;

    event EscrowCreated(bytes32 indexed invoiceId, address indexed delegator, address indexed worker, uint256 amount);
    event EscrowReleased(bytes32 indexed invoiceId, address indexed worker, bytes32 manifestSha256);
    event EscrowRefunded(bytes32 indexed invoiceId, address indexed delegator, string reason);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor(address _usdc) {
        usdc = IERC20(_usdc);
        owner = msg.sender;
    }

    /**
     * @notice Locks USDC in escrow for an autonomous subagent task.
     */
    function lockEscrow(
        bytes32 invoiceId,
        address worker,
        uint256 amountUsdc,
        bytes32 taskHash,
        uint256 durationSeconds
    ) external {
        require(invoices[invoiceId].status == EscrowStatus.None, "Invoice already exists");
        require(worker != address(0), "Invalid worker");
        require(amountUsdc > 0, "Amount must be > 0");

        require(usdc.transferFrom(msg.sender, address(this), amountUsdc), "USDC transfer failed");

        invoices[invoiceId] = Invoice({
            delegator: msg.sender,
            worker: worker,
            amountUsdc: amountUsdc,
            taskHash: taskHash,
            expirationTimestamp: block.timestamp + durationSeconds,
            status: EscrowStatus.Locked
        });

        emit EscrowCreated(invoiceId, msg.sender, worker, amountUsdc);
    }

    /**
     * @notice Releases escrow to worker upon verified DharmaGate manifest.sha256 delivery.
     */
    function releaseEscrow(
        bytes32 invoiceId,
        bytes32 manifestSha256,
        bytes calldata signature
    ) external {
        Invoice storage inv = invoices[invoiceId];
        require(inv.status == EscrowStatus.Locked, "Escrow not locked");

        // Verify oracle/sealer signature over (invoiceId, manifestSha256, "PROXY_PASS")
        bytes32 messageHash = keccak256(abi.encodePacked(invoiceId, manifestSha256, "PROXY_PASS"));
        bytes32 ethSignedHash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", messageHash));
        address signer = recoverSigner(ethSignedHash, signature);
        require(signer == owner || signer == inv.delegator, "Unauthorized evidence signature");

        inv.status = EscrowStatus.Released;
        require(usdc.transfer(inv.worker, inv.amountUsdc), "USDC payout failed");

        emit EscrowReleased(invoiceId, inv.worker, manifestSha256);
    }

    /**
     * @notice Refunds delegator if task expires without verified delivery or physical breach.
     */
    function refundEscrow(bytes32 invoiceId, string calldata reason) external {
        Invoice storage inv = invoices[invoiceId];
        require(inv.status == EscrowStatus.Locked, "Escrow not locked");
        require(msg.sender == inv.delegator || msg.sender == owner, "Only delegator or owner");
        require(block.timestamp >= inv.expirationTimestamp || msg.sender == owner, "Escrow not expired");

        inv.status = EscrowStatus.Refunded;
        require(usdc.transfer(inv.delegator, inv.amountUsdc), "USDC refund failed");

        emit EscrowRefunded(invoiceId, inv.delegator, reason);
    }

    function recoverSigner(bytes32 ethSignedHash, bytes memory sig) internal pure returns (address) {
        require(sig.length == 65, "Invalid signature length");
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        return ecrecover(ethSignedHash, v, r, s);
    }
}

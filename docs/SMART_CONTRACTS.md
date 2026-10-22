# Tancoin smart contracts (TVM)

Ethereum uses the **EVM** (stack machine + rich opcode set + persistent storage). Tancoin ships a **Tancoin Virtual Machine (TVM)** — a **small, deterministic** stack machine implemented in `tancoin_core/vm.py`. It is **not bytecode-compatible** with Ethereum; the similarity is **conceptual**: deploy bytecode, call with calldata, pay implicit fees in the UTXO layer, and persist **per-contract key/value storage**.

## Deployment model

- **Deploy:** a `TxOutput` with `kind: "contract_deploy"`, `value: 0`, `recipient_pubkey_hash` typically all zeros, and `payload` = TVM bytecode. After the transaction is included in a block, the contract **address** is:

  `contract_id = RIPEMD160(SHA256(txid || output_index))` (with the same `hash160` fallback as P2PKH when RIPEMD160 is unavailable).

- **Call:** a `TxOutput` with `kind: "contract_call"`, `recipient_pubkey_hash` = **20-byte contract id**, `payload` = calldata passed into the VM (opaque bytes; your convention).

Execution runs when the block is applied; on success, updated `storage` is persisted on the in-memory / replayed chain state.

## Opcodes (reference)

| Opcode (hex) | Name | Effect |
|--------------|------|--------|
| `0x00` | STOP | End execution |
| `0x01` | PUSH1 | Read next byte as uint8, push to stack |
| `0x10` | ADD | Pop a, b; push (a+b) mod 2²⁵⁶ |
| `0x11` | SUB | Pop a, b; push (a-b) mod 2²⁵⁶ |
| `0x12` | MUL | Pop a, b; push (a*b) mod 2²⁵⁶ |
| `0x20` | DUP | Duplicate top |
| `0x21` | SWAP | Swap top two |
| `0x30` | SLOAD | Pop key as uint256; push 32-byte storage value as integer |
| `0x31` | SSTORE | Pop value, pop key; store 32-byte value |
| `0x40` | TIMESTAMP | Push block timestamp |
| `0x41` | CALLER_BALANCE | Push 0 (reserved / extension hook) |

**Gas:** each instruction consumes gas; `SSTORE` is more expensive. Limits are enforced via `DEFAULT_CONTRACT_GAS_LIMIT` in `tancoin_core.constants`.

## Minimal bytecode example

Push block timestamp onto the stack and stop (useful smoke test after deploy+call with empty calldata still runs constructor-less code once):

```text
40 00   → TIMESTAMP, STOP
```

Hex: `4000`.

A slightly richer example: load storage key `0`, add `5`, store back. `SSTORE` pops **value** then **key**, so after `ADD` use `PUSH1 0` then `SWAP` so the stack is `[key, value]` with **value on top**:

```text
01 00 30 01 05 10 01 00 21 31 00
```

(`21` = `OP_SWAP`, `31` = `SSTORE`, `00` = `STOP`.)

## HTTP helpers

- `POST /api/contracts/deploy/` — see [API.md](./API.md).  
- `POST /api/contracts/call/` — pass `calldata_hex` as needed.

After deploy/call submission, **`POST /api/chain/mine/`** to include the transaction in a block.

## Porting from Ethereum

Map **concepts**, not bytecode:

| Ethereum | Tancoin |
|----------|---------|
| Contract address | `contract_id_hex` from deploy output / `GET /api/contracts/` |
| `msg.sender` | `caller_pubkey_hash` in `TVMContext` (hash of signer pubkey from first input) |
| `block.timestamp` | `OP_TIMESTAMP` |
| Storage slots | `SLOAD` / `SSTORE` with 32-byte keys |

For production-grade smart contracts, you would either extend TVM with safer typing/syscalls or bridge to an external rollup — this repository targets **clarity and integration**, not EVM equivalence.

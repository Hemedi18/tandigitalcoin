# Tancoin HTTP API

Base URL: your Django site root (e.g. `http://127.0.0.1:8000/`).

Responses are JSON objects with `"ok": true` or `"ok": false` and optional `"error"`.

## Chain

### `GET /api/chain/status/`

Returns `chain`: `{ coin, name, decimals, height, tip, reference_price_usd, mempool_count, initial_difficulty_bits }`.

### `GET /api/chain/blocks/?limit=20`

Recent blocks (newest at end of list), each including `transactions` as dicts.

### `GET /api/chain/block/<block_hash>/`

Full block by hex hash (with or without `0x` prefix).

### `GET /api/chain/tx/<txid>/`

Transaction by id; includes `confirmed` boolean.

### `GET /api/chain/utxo/<address>/`

Spendable outputs for a Base58Check address: list of `{ txid, index, value, kind }`.

### `GET /api/chain/mempool/`

Pending signed transactions not yet mined.

## Wallet (helper)

### `GET /api/wallet/new/`

Creates a keypair; returns `address`, `wif`, and a security `warning`.

## Mutations (JSON POST bodies)

### `POST /api/chain/tx/submit/`

Body:

```json
{
  "transaction": {
    "version": 1,
    "inputs": [
      {
        "prev_txid": "<hex>",
        "prev_index": 0,
        "script_sig": "<hex pubkey||signature>"
      }
    ],
    "outputs": [
      {
        "value": 100000000,
        "recipient_pubkey_hash": "<20-byte hex>",
        "kind": "transfer",
        "payload": ""
      }
    ],
    "locktime": 0
  }
}
```

Returns `{ "ok": true, "txid": "..." }`.

### `POST /api/chain/mine/`

Optional body: `{ "miner_wif": "<optional>" }`.  
Builds a block from mempool, finds proof-of-work, extends the chain, clears mempool.  
Returns `{ "ok": true, "block": { ... } }`.

### `POST /api/chain/price/`

Body: `{ "reference_price_usd": 0.02 }` — updates the mock reference price persisted with the chain.

## Contracts (high level)

### `POST /api/contracts/deploy/`

```json
{
  "deployer_wif": "<wif>",
  "fee_satoshis": 50000,
  "bytecode_hex": "<tvm bytecode hex>"
}
```

Builds a funded deploy transaction (largest UTXO on the deployer), submits to mempool. Mine separately to confirm.

### `POST /api/contracts/call/`

```json
{
  "caller_wif": "<wif>",
  "contract_id_hex": "<40 hex chars, 20-byte id>",
  "calldata_hex": "",
  "fee_satoshis": 50000
}
```

### `GET /api/contracts/`

Lists known contracts: `contract_id_hex`, `code_size`, `storage_keys`.

## Development only

### `GET /api/dev/genesis-wallet/`

Returns the first miner wallet used at initial genesis (so you can fund test accounts). **Do not expose in production.**

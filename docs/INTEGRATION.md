# Tancoin (TAN) — developer integration

Tancoin is a **Python** reference implementation: UTXO model and proof-of-work similar in spirit to Bitcoin, plus a **Tancoin Virtual Machine (TVM)** for on-chain logic inspired by the *account + contract* idea from Ethereum. A **Django** app exposes HTTP JSON endpoints so other applications can submit transactions, mine blocks, and query state without importing the core library.

## What to integrate

| Layer | Role |
|--------|------|
| **`tancoin_core`** | Pure Python: blocks, transactions, wallets, chain validation, TVM. No Django import. Ship it as a library inside your monorepo or install via `PYTHONPATH`. |
| **`chain_api`** (Django) | JSON API + on-disk node state under `TANCOIN_DATA_DIR` (default: `<project>/data/`). |

## Units and ticker

- **Symbol:** `TAN`
- **Decimals:** `8` (same granularity style as Bitcoin satoshis).
- **Smallest unit:** 1 / 10⁸ TAN (internally called *satoshis* in code constants).

All API amounts are **integers in satoshis**.

## “Price” and external apps

There is **no built-in decentralized exchange** or oracle network. For wallets, dashboards, and merchant apps you typically:

1. Read **`reference_price_usd`** from `GET /api/chain/status/` — a **configurable mock / reference** field for demos and UIs (default `0.01` in `tancoin_core.constants`).
2. Update it with `POST /api/chain/price/` (JSON: `{"reference_price_usd": 0.02}`) on staging, **or** replace this with your own pricing microservice and ignore the built-in field in production.

Document clearly to end users whether a displayed price is **market**, **oracle**, or **reference/mock**.

## Typical integration flows

1. **Create or load keys**  
   - `GET /api/wallet/new/` returns `address` + `wif` (treat WIF like a password).  
   - Or use `tancoin_core.Wallet.generate()` inside your Python service.

2. **Discover spendable coins**  
   - `GET /api/chain/utxo/<address>/` → list of `{txid, index, value, kind}`.

3. **Build and sign a transfer**  
   - In Python: `Chain.create_transfer(from_wallet, to_address, amount, [(txid, index), ...], change)`.  
   - Submit: `POST /api/chain/tx/submit/` with `{"transaction": { ... }}` (same shape as `Transaction.to_dict()`).

4. **Confirm**  
   - Run a miner (your infrastructure): `POST /api/chain/mine/` with optional `{"miner_wif": "..."}` so fees go to your pool wallet.  
   - Poll `GET /api/chain/tx/<txid>/` until `confirmed: true`.

5. **Contracts**  
   - See [SMART_CONTRACTS.md](./SMART_CONTRACTS.md). Deploy and call via dedicated endpoints or by crafting `TxOutput` with `kind` `contract_deploy` / `contract_call`.

## Security notes

- **WIF** and **genesis** keys must be protected (`data/genesis_wallet.json` on first boot).  
- `GET /api/dev/genesis-wallet/` is for **local development only**; disable or protect it behind auth in production.  
- CSRF: mutating endpoints use `@csrf_exempt` for simple JSON clients. For browser-based apps, prefer **session auth + CSRF**, **API keys**, or **token** middleware instead of leaving endpoints open.

## Django settings

In `tancoin/settings.py`:

- `INSTALLED_APPS` includes `chain_api`.
- `TANCOIN_DATA_DIR` points to the directory for `chain.json` and `genesis_wallet.json`.

## Non-Django Python services

```python
from tancoin_core.chain import Chain
from tancoin_core.wallet import Wallet

c = Chain()
w = Wallet.generate()
c.genesis(w)
```

Use the same transaction and block structures as the HTTP API (see [API.md](./API.md)).

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from django.conf import settings

from tancoin_core import constants
from tancoin_core.block import Block
from tancoin_core.chain import Chain
from tancoin_core.transaction import OutputKind, Transaction, TxInput, TxOutput
from tancoin_core.wallet import Wallet

_lock = threading.RLock()
_chain: Chain | None = None
_mempool: list[Transaction] = []
_genesis_wallet: Wallet | None = None


def _data_dir() -> Path:
    p = getattr(settings, "TANCOIN_DATA_DIR", Path(settings.BASE_DIR) / "data")
    p.mkdir(parents=True, exist_ok=True)
    return Path(p)


def _chain_path() -> Path:
    return _data_dir() / "chain.json"


def _genesis_wallet_path() -> Path:
    return _data_dir() / "genesis_wallet.json"


def ensure_initialized() -> None:
    global _chain, _genesis_wallet
    with _lock:
        if _chain is not None:
            return
        path = _chain_path()
        gwp = _genesis_wallet_path()
        if path.exists():
            _chain = Chain.from_json(path.read_text(encoding="utf-8"))
            if gwp.exists():
                data = json.loads(gwp.read_text(encoding="utf-8"))
                _genesis_wallet = Wallet.from_wif(data["wif"])
            return

        _chain = Chain()
        if gwp.exists():
            data = json.loads(gwp.read_text(encoding="utf-8"))
            _genesis_wallet = Wallet.from_wif(data["wif"])
        else:
            _genesis_wallet = Wallet.generate()
            gwp.write_text(
                json.dumps(
                    {
                        "wif": _genesis_wallet.to_wif(),
                        "address": _genesis_wallet.address(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        assert _genesis_wallet is not None
        _chain.genesis(_genesis_wallet)
        _persist_locked()


def _persist_locked() -> None:
    if _chain is None:
        return
    target = _chain_path()
    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text(_chain.to_json(), encoding="utf-8")
    tmp_path.replace(target)


def get_chain() -> Chain:
    ensure_initialized()
    assert _chain is not None
    return _chain


def get_genesis_wallet() -> Wallet | None:
    ensure_initialized()
    return _genesis_wallet


def get_mempool() -> list[Transaction]:
    with _lock:
        return list(_mempool)


def set_reference_price_usd(price: float) -> None:
    with _lock:
        c = get_chain()
        c.reference_price_usd = float(price)
        _persist_locked()


def submit_transaction(tx_dict: dict[str, Any]) -> str:
    tx = Transaction.from_dict(tx_dict)
    with _lock:
        c = get_chain()
        tid = tx.txid()
        if any(m.txid() == tid for m in _mempool):
            raise ValueError("transaction already in mempool")
        mempool_spent = {
            (inp.prev_txid, inp.prev_index)
            for m in _mempool
            for inp in m.inputs
        }
        for inp in tx.inputs:
            if (inp.prev_txid, inp.prev_index) in mempool_spent:
                raise ValueError(
                    "UTXO already spent by another pending mempool transaction"
                )
        c.validate_transaction(tx)
        _mempool.append(tx)
    return tx.txid().hex()


def mine_block(miner: Wallet | None = None) -> Block:
    with _lock:
        c = get_chain()
        m = miner or _genesis_wallet or Wallet.generate()
        b = c.build_candidate_block(m, _mempool)
        c.mine_block_header(b)
        c.add_block(b)
        _mempool.clear()
        _persist_locked()
        return b


def chain_summary() -> dict[str, Any]:
    c = get_chain()
    with _lock:
        mp = len(_mempool)
    return {
        "coin": "TAN",
        "name": "Tancoin",
        "decimals": 8,
        "height": c.height,
        "tip": c.tip_hash().hex(),
        "reference_price_usd": c.reference_price_usd,
        "mempool_count": mp,
        "initial_difficulty_bits": constants.INITIAL_DIFFICULTY_BITS,
    }


def build_deploy_transaction(
    from_w: Wallet, bytecode: bytes, fee_satoshis: int
) -> Transaction:
    c = get_chain()
    utxos = c.get_utxos_for_address(from_w.address())
    if not utxos:
        raise ValueError("no utxo for deployer")
    u = max(utxos, key=lambda x: x["value"])
    txid = bytes.fromhex(u["txid"])
    idx = int(u["index"])
    prev = c.utxo.get((txid, idx))
    if not prev:
        raise ValueError("stale utxo")
    total_in = prev.value
    if total_in <= fee_satoshis:
        raise ValueError("utxo too small for fee")
    deploy = TxOutput(
        value=0,
        recipient_pubkey_hash=bytes(20),
        kind=OutputKind.CONTRACT_DEPLOY,
        payload=bytecode,
    )
    change = total_in - fee_satoshis
    change_out = TxOutput(
        value=change,
        recipient_pubkey_hash=from_w.pubkey_hash(),
        kind=OutputKind.TRANSFER,
    )
    tx = Transaction(
        version=1,
        inputs=[TxInput(prev_txid=txid, prev_index=idx)],
        outputs=[deploy, change_out],
    )
    tx.inputs[0].script_sig = from_w.sign_tx(tx, 0)
    return tx


def build_call_transaction(
    from_w: Wallet, contract_id_hex: str, calldata: bytes, fee_satoshis: int
) -> Transaction:
    c = get_chain()
    utxos = c.get_utxos_for_address(from_w.address())
    if not utxos:
        raise ValueError("no utxo")
    u = max(utxos, key=lambda x: x["value"])
    txid = bytes.fromhex(u["txid"])
    idx = int(u["index"])
    prev = c.utxo.get((txid, idx))
    if not prev:
        raise ValueError("stale utxo")
    total_in = prev.value
    if total_in <= fee_satoshis:
        raise ValueError("utxo too small for fee")
    raw = contract_id_hex.strip().lower().removeprefix("0x")
    if len(raw) != 40:
        raise ValueError("contract_id_hex must be 20 bytes (40 hex chars)")
    addr20 = bytes.fromhex(raw)
    call_out = TxOutput(
        value=0,
        recipient_pubkey_hash=addr20,
        kind=OutputKind.CONTRACT_CALL,
        payload=calldata,
    )
    change = total_in - fee_satoshis
    change_out = TxOutput(
        value=change,
        recipient_pubkey_hash=from_w.pubkey_hash(),
        kind=OutputKind.TRANSFER,
    )
    tx = Transaction(
        version=1,
        inputs=[TxInput(prev_txid=txid, prev_index=idx)],
        outputs=[call_out, change_out],
    )
    tx.inputs[0].script_sig = from_w.sign_tx(tx, 0)
    return tx

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from tancoin_core import constants
from tancoin_core.block import Block, pow_valid
from tancoin_core.crypto import hash160
from tancoin_core.transaction import OutputKind, Transaction, TxInput, TxOutput
from tancoin_core.vm import TVM, TVMContext, contract_address_from_deploy
from tancoin_core.wallet import Wallet

COINBASE_REWARD = 50 * constants.SATOSHIS_PER_COIN


def _utxo_key(txid: bytes, index: int) -> tuple[bytes, int]:
    return (txid, index)


@dataclass
class ContractState:
    code: bytes
    storage: dict[bytes, bytes] = field(default_factory=dict)


@dataclass
class Chain:
    """UTXO chain + TVM contract accounts (Ethereum-like state for contracts only)."""

    blocks: list[Block] = field(default_factory=list)
    utxo: dict[tuple[bytes, int], TxOutput] = field(default_factory=dict)
    contracts: dict[bytes, ContractState] = field(default_factory=dict)
    height: int = 0
    reference_price_usd: float = constants.REFERENCE_PRICE_USD_DEFAULT

    def tip_hash(self) -> bytes:
        if not self.blocks:
            return b"\x00" * 32
        return self.blocks[-1].block_hash()

    def get_utxos_for_address(self, address: str) -> list[dict[str, Any]]:
        from tancoin_core import crypto

        h = crypto.pubkeyhash_from_address(address)
        rows: list[dict[str, Any]] = []
        for (txid, idx), o in self.utxo.items():
            if o.recipient_pubkey_hash == h:
                rows.append(
                    {
                        "txid": txid.hex(),
                        "index": idx,
                        "value": o.value,
                        "kind": o.kind.value,
                    }
                )
        return rows

    def to_json(self) -> str:
        return json.dumps(
            {
                "height": self.height,
                "tip": self.tip_hash().hex(),
                "reference_price_usd": self.reference_price_usd,
                "blocks": [b.to_dict() for b in self.blocks],
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, s: str) -> Chain:
        d = json.loads(s)
        c = cls(
            reference_price_usd=float(
                d.get("reference_price_usd", constants.REFERENCE_PRICE_USD_DEFAULT)
            )
        )
        for bd in d.get("blocks", []):
            c._apply_block(Block.from_dict(bd), validate=False)
        return c

    def genesis(self, miner: Wallet) -> Block:
        coinbase = Transaction(
            version=1,
            inputs=[],
            outputs=[
                TxOutput(
                    value=COINBASE_REWARD,
                    recipient_pubkey_hash=miner.pubkey_hash(),
                    kind=OutputKind.TRANSFER,
                )
            ],
        )
        b = Block(
            version=1,
            prev_hash=b"\x00" * 32,
            timestamp=int(time.time()),
            difficulty_bits=constants.INITIAL_DIFFICULTY_BITS,
            nonce=0,
            transactions=[coinbase],
        )
        b.rebuild_merkle()
        self.mine_block_header(b)
        self._apply_block(b, validate=False)
        return b

    def mine_block_header(self, block: Block) -> None:
        block.rebuild_merkle()
        block.nonce = 0
        while not pow_valid(block.block_hash(), block.difficulty_bits):
            block.nonce += 1
            if block.nonce > 2**64 - 2:
                block.timestamp += 1
                block.nonce = 0

    def _apply_block(self, block: Block, validate: bool) -> None:
        if not block.transactions:
            raise ValueError("empty block")
        coinbase = block.transactions[0]
        if coinbase.inputs:
            raise ValueError("coinbase must be first with no inputs")
        if validate:
            if self.blocks and block.prev_hash != self.tip_hash():
                raise ValueError("prev hash mismatch")
            if block.merkle_root != Block.compute_merkle(block.transactions):
                raise ValueError("merkle root mismatch")
            if not pow_valid(block.block_hash(), block.difficulty_bits):
                raise ValueError("invalid pow")

        temp = self._snapshot()
        fees = 0
        for tx in block.transactions[1:]:
            fees += temp._fee_for_tx(tx)
            temp._apply_transaction(tx, block.timestamp, skip_utxo_remove=False)
        expected_coinbase = COINBASE_REWARD + fees
        if coinbase.outputs[0].value != expected_coinbase:
            raise ValueError("coinbase reward mismatch")

        for tx in block.transactions[1:]:
            self._apply_transaction(tx, block.timestamp, skip_utxo_remove=False)
        self._apply_coinbase(coinbase)
        self.blocks.append(block)
        self.height = len(self.blocks)

    def _apply_coinbase(self, tx: Transaction) -> None:
        txid = tx.txid()
        for i, out in enumerate(tx.outputs):
            self.utxo[_utxo_key(txid, i)] = out

    def _fee_for_tx(self, tx: Transaction) -> int:
        in_sum = 0
        for inp in tx.inputs:
            k = _utxo_key(inp.prev_txid, inp.prev_index)
            prev = self.utxo.get(k)
            if not prev:
                raise ValueError("missing utxo input")
            in_sum += prev.value
        out_sum = sum(o.value for o in tx.outputs)
        if in_sum < out_sum:
            raise ValueError("insufficient inputs")
        return in_sum - out_sum

    def _apply_transaction(
        self, tx: Transaction, block_ts: int, skip_utxo_remove: bool
    ) -> None:
        if not tx.inputs:
            raise ValueError("non-coinbase must have inputs")
        in_sum = 0
        for j, inp in enumerate(tx.inputs):
            k = _utxo_key(inp.prev_txid, inp.prev_index)
            prev = self.utxo.get(k)
            if not prev:
                raise ValueError("missing utxo input")
            if not Wallet.verify_input(tx, j, prev):
                raise ValueError("invalid signature")
            in_sum += prev.value
            if not skip_utxo_remove:
                del self.utxo[k]
        out_sum = sum(o.value for o in tx.outputs)
        if in_sum < out_sum:
            raise ValueError("insufficient inputs")
        txid = tx.txid()
        for i, out in enumerate(tx.outputs):
            if out.kind == OutputKind.CONTRACT_DEPLOY and out.payload:
                addr = contract_address_from_deploy(txid, i)
                self.contracts[addr] = ContractState(code=bytes(out.payload))
            if out.kind == OutputKind.CONTRACT_CALL:
                self._run_contract_call(out, tx, block_ts)
            self.utxo[_utxo_key(txid, i)] = out

    def _run_contract_call(self, out: TxOutput, tx: Transaction, block_ts: int) -> None:
        addr = out.recipient_pubkey_hash
        st = self.contracts.get(addr)
        if not st:
            return
        inp0 = tx.inputs[0].script_sig if tx.inputs else b""
        caller_pub = inp0[:65] if len(inp0) >= 65 else b""
        caller_hash = hash160(caller_pub) if caller_pub else b"\x00" * 20
        vm = TVM(st.code, storage=dict(st.storage))
        ctx = TVMContext(
            block_timestamp=block_ts,
            caller_pubkey_hash=caller_hash,
            contract_address=addr,
            gas_limit=constants.DEFAULT_CONTRACT_GAS_LIMIT,
        )
        res = vm.run(out.payload, ctx)
        if res.success:
            st.storage = vm.storage

    def add_block(self, block: Block) -> None:
        self._apply_block(block, validate=True)

    def build_candidate_block(
        self, miner: Wallet, mempool_txs: list[Transaction]
    ) -> Block:
        temp = self._snapshot()
        fees = 0
        valid: list[Transaction] = []
        for tx in mempool_txs:
            try:
                fees += temp._fee_for_tx(tx)
                temp._apply_transaction(tx, int(time.time()), skip_utxo_remove=False)
                valid.append(tx)
            except Exception:
                continue
        coinbase = Transaction(
            version=1,
            inputs=[],
            outputs=[
                TxOutput(
                    value=COINBASE_REWARD + fees,
                    recipient_pubkey_hash=miner.pubkey_hash(),
                    kind=OutputKind.TRANSFER,
                )
            ],
        )
        b = Block(
            version=1,
            prev_hash=self.tip_hash(),
            timestamp=int(time.time()),
            difficulty_bits=constants.INITIAL_DIFFICULTY_BITS,
            nonce=0,
            transactions=[coinbase] + valid,
        )
        b.rebuild_merkle()
        return b

    def _snapshot(self) -> Chain:
        import copy

        return Chain(
            blocks=list(self.blocks),
            utxo=copy.deepcopy(self.utxo),
            contracts=copy.deepcopy(self.contracts),
            height=self.height,
            reference_price_usd=self.reference_price_usd,
        )

    def validate_transaction(self, tx: Transaction) -> None:
        snap = self._snapshot()
        snap._apply_transaction(tx, int(time.time()), skip_utxo_remove=False)

    def create_transfer(
        self,
        from_w: Wallet,
        to_address: str,
        amount: int,
        utxo_refs: list[tuple[bytes, int]],
        change: int,
    ) -> Transaction:
        from tancoin_core import crypto

        to_hash = crypto.pubkeyhash_from_address(to_address)
        inputs = []
        for txid, idx in utxo_refs:
            inputs.append(TxInput(prev_txid=txid, prev_index=idx))
        outputs = [
            TxOutput(
                value=amount, recipient_pubkey_hash=to_hash, kind=OutputKind.TRANSFER
            )
        ]
        if change > 0:
            outputs.append(
                TxOutput(
                    value=change,
                    recipient_pubkey_hash=from_w.pubkey_hash(),
                    kind=OutputKind.TRANSFER,
                )
            )
        tx = Transaction(version=1, inputs=inputs, outputs=outputs)
        for i in range(len(inputs)):
            tx.inputs[i].script_sig = from_w.sign_tx(tx, i)
        return tx

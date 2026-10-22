from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tancoin_core import crypto


class OutputKind(str, Enum):
    TRANSFER = "transfer"
    CONTRACT_DEPLOY = "contract_deploy"
    CONTRACT_CALL = "contract_call"


@dataclass
class TxInput:
    prev_txid: bytes
    prev_index: int
    script_sig: bytes = b""  # pubkey + signature for TRANSFER spends

    def serialize(self) -> bytes:
        return (
            self.prev_txid
            + self.prev_index.to_bytes(4, "big")
            + len(self.script_sig).to_bytes(2, "big")
            + self.script_sig
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TxInput:
        return cls(
            prev_txid=bytes.fromhex(d["prev_txid"]),
            prev_index=int(d["prev_index"]),
            script_sig=bytes.fromhex(d.get("script_sig", "") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prev_txid": self.prev_txid.hex(),
            "prev_index": self.prev_index,
            "script_sig": self.script_sig.hex(),
        }


@dataclass
class TxOutput:
    value: int
    recipient_pubkey_hash: bytes
    kind: OutputKind = OutputKind.TRANSFER
    payload: bytes = b""  # bytecode for deploy; calldata for call

    def serialize(self) -> bytes:
        k = self.kind.value.encode()
        return (
            self.value.to_bytes(8, "big")
            + self.recipient_pubkey_hash
            + len(k).to_bytes(1, "big")
            + k
            + len(self.payload).to_bytes(4, "big")
            + self.payload
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TxOutput:
        kind = OutputKind(d.get("kind", OutputKind.TRANSFER.value))
        rph = d.get("recipient_pubkey_hash")
        if isinstance(rph, str):
            rph_b = bytes.fromhex(rph)
        else:
            rph_b = bytes(rph)
        pl = d.get("payload", "") or ""
        payload = bytes.fromhex(pl) if isinstance(pl, str) else bytes(pl)
        return cls(
            value=int(d["value"]),
            recipient_pubkey_hash=rph_b,
            kind=kind,
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "recipient_pubkey_hash": self.recipient_pubkey_hash.hex(),
            "kind": self.kind.value,
            "payload": self.payload.hex(),
        }


@dataclass
class Transaction:
    version: int = 1
    inputs: list[TxInput] = field(default_factory=list)
    outputs: list[TxOutput] = field(default_factory=list)
    locktime: int = 0

    def txid(self) -> bytes:
        return crypto.sha256d(self.serialize_unsigned())

    def serialize_unsigned(self) -> bytes:
        parts = [self.version.to_bytes(4, "big")]
        parts.append(len(self.inputs).to_bytes(2, "big"))
        for i in self.inputs:
            parts.append(i.prev_txid + i.prev_index.to_bytes(4, "big"))
        parts.append(len(self.outputs).to_bytes(2, "big"))
        for o in self.outputs:
            parts.append(o.serialize())
        parts.append(self.locktime.to_bytes(4, "big"))
        return b"".join(parts)

    def signing_digest(self, input_index: int) -> bytes:
        """Simplified Bitcoin-style commitment for one input (P2PKH-like)."""
        body = self.serialize_unsigned()
        return crypto.sha256d(body + input_index.to_bytes(4, "big"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "locktime": self.locktime,
            "txid": self.txid().hex(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Transaction:
        return cls(
            version=int(d.get("version", 1)),
            inputs=[TxInput.from_dict(x) for x in d.get("inputs", [])],
            outputs=[TxOutput.from_dict(x) for x in d.get("outputs", [])],
            locktime=int(d.get("locktime", 0)),
        )

    def json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def txid_hex(tx: Transaction) -> str:
    return tx.txid().hex()

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from tancoin_core import crypto
from tancoin_core.transaction import Transaction


@dataclass
class Block:
    version: int = 1
    prev_hash: bytes = field(default_factory=lambda: b"\x00" * 32)
    merkle_root: bytes = field(default_factory=lambda: b"\x00" * 32)
    timestamp: int = field(default_factory=lambda: int(time.time()))
    difficulty_bits: int = 20
    nonce: int = 0
    transactions: list[Transaction] = field(default_factory=list)

    def header_for_hash(self) -> bytes:
        parts = [
            self.version.to_bytes(4, "big"),
            self.prev_hash,
            self.merkle_root,
            self.timestamp.to_bytes(8, "big"),
            self.difficulty_bits.to_bytes(4, "big"),
            self.nonce.to_bytes(8, "big"),
        ]
        return b"".join(parts)

    def block_hash(self) -> bytes:
        return crypto.sha256d(self.header_for_hash())

    @staticmethod
    def compute_merkle(transactions: list[Transaction]) -> bytes:
        if not transactions:
            return crypto.sha256d(b"")
        leaves = [crypto.sha256d(tx.serialize_unsigned()) for tx in transactions]
        return crypto.merkle_root(leaves)

    def rebuild_merkle(self) -> None:
        self.merkle_root = self.compute_merkle(self.transactions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "prev_hash": self.prev_hash.hex(),
            "merkle_root": self.merkle_root.hex(),
            "timestamp": self.timestamp,
            "difficulty_bits": self.difficulty_bits,
            "nonce": self.nonce,
            "hash": self.block_hash().hex(),
            "transactions": [t.to_dict() for t in self.transactions],
        }

    @staticmethod
    def _bytes32_from_dict_field(value: Any) -> bytes:
        """Parse hex or raw bytes; always return exactly 32 bytes (explorer URLs need non-empty hashes)."""
        if value is None or value == "":
            return b"\x00" * 32
        if isinstance(value, (bytes, bytearray)):
            raw = bytes(value)
        else:
            s = str(value).strip().lower().removeprefix("0x")
            if not s:
                return b"\x00" * 32
            raw = bytes.fromhex(s)
        if len(raw) == 32:
            return raw
        if len(raw) > 32:
            return raw[:32]
        return raw.rjust(32, b"\x00")

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Block:
        txs = [Transaction.from_dict(x) for x in d.get("transactions", [])]
        return cls(
            version=int(d.get("version", 1)),
            prev_hash=cls._bytes32_from_dict_field(d.get("prev_hash")),
            merkle_root=cls._bytes32_from_dict_field(d.get("merkle_root")),
            timestamp=int(d["timestamp"]),
            difficulty_bits=int(d["difficulty_bits"]),
            nonce=int(d["nonce"]),
            transactions=txs,
        )

    def json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def pow_valid(block_hash: bytes, difficulty_bits: int) -> bool:
    """True if the hash is below target 2^(256 - difficulty_bits)."""
    if difficulty_bits <= 0 or difficulty_bits > 256:
        return False
    x = int.from_bytes(block_hash, "big")
    return x < (1 << (256 - difficulty_bits))

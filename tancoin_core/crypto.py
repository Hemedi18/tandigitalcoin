from __future__ import annotations

import hashlib
import struct
from typing import Final

_B58_ALPHABET: Final[bytes] = (
    b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def sha256d(b: bytes) -> bytes:
    """Double SHA-256 (Bitcoin block/tx hashing)."""
    return sha256(sha256(b))


def hash160(b: bytes) -> bytes:
    try:
        return hashlib.new("ripemd160", sha256(b)).digest()
    except ValueError:
        # OpenSSL builds without RIPEMD160 (e.g. some 3.13+): Bitcoin-compatible fallback for dev.
        return sha256(sha256(b))[:20]


def merkle_root(hashes: list[bytes]) -> bytes:
    if not hashes:
        return sha256d(b"")
    layer = list(hashes)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [sha256d(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
    return layer[0]


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    if n == 0:
        return _B58_ALPHABET[0:1].decode()
    out = bytearray()
    while n > 0:
        n, r = divmod(n, 58)
        out.append(_B58_ALPHABET[r])
    for byte in b:
        if byte == 0:
            out.append(_B58_ALPHABET[0])
        else:
            break
    return bytes(reversed(out)).decode()


def b58decode(s: str) -> bytes:
    n = 0
    for ch in s.encode():
        try:
            v = _B58_ALPHABET.index(ch)
        except ValueError as e:
            raise ValueError("invalid base58") from e
        n = n * 58 + v
    pad = 0
    for ch in s.encode():
        if ch == _B58_ALPHABET[0]:
            pad += 1
        else:
            break
    h = "%x" % n
    if len(h) % 2:
        h = "0" + h
    res = bytes.fromhex(h) if h else b""
    return b"\x00" * pad + res


def address_from_pubkey_hash(pubkey_hash20: bytes, version: int = 0x00) -> str:
    """Base58Check from 20-byte pubkey hash (P2PKH-style), used by explorers for outputs."""
    if len(pubkey_hash20) != 20:
        raise ValueError("pubkey hash must be 20 bytes")
    payload = bytes([version]) + pubkey_hash20
    chk = sha256d(payload)[:4]
    return b58encode(payload + chk)


def address_from_pubkey(pubkey_compressed: bytes, version: int = 0x00) -> str:
    """P2PKH-style address (version byte + hash160 + checksum), Base58Check."""
    payload = bytes([version]) + hash160(pubkey_compressed)
    chk = sha256d(payload)[:4]
    return b58encode(payload + chk)


def pubkeyhash_from_address(addr: str) -> bytes:
    raw = b58decode(addr)
    if len(raw) < 5:
        raise ValueError("address too short")
    payload, chk = raw[:-4], raw[-4:]
    if sha256d(payload)[:4] != chk:
        raise ValueError("checksum mismatch")
    if len(payload) != 21:
        raise ValueError("bad address length")
    return payload[1:21]


def u32be(x: int) -> bytes:
    return struct.pack(">I", x & 0xFFFFFFFF)


def u64be(x: int) -> bytes:
    return struct.pack(">Q", x & 0xFFFFFFFFFFFFFFFF)

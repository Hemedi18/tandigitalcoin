from __future__ import annotations

from dataclasses import dataclass

from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import sigdecode_string, sigencode_string_canonize

from tancoin_core import crypto
from tancoin_core.transaction import OutputKind, Transaction, TxOutput


@dataclass
class Wallet:
    """Secp256k1 keypair; addresses are Base58Check P2PKH-style (uncompressed pubkey in scripts)."""

    signing_key: SigningKey

    @classmethod
    def generate(cls) -> Wallet:
        return cls(SigningKey.generate(curve=SECP256k1))

    @classmethod
    def from_wif(cls, wif: str) -> Wallet:
        raw = crypto.b58decode(wif)
        if len(raw) not in (37, 38):
            raise ValueError("invalid WIF length")
        payload, chk = raw[:-4], raw[-4:]
        if crypto.sha256d(payload)[:4] != chk:
            raise ValueError("checksum mismatch")
        key_bytes = raw[1:33]
        return cls(SigningKey.from_string(key_bytes, curve=SECP256k1))

    def to_wif(self, compressed: bool = True, version: int = 0x80) -> str:
        sk = self.signing_key.to_string()
        payload = bytes([version]) + sk + (b"\x01" if compressed else b"")
        chk = crypto.sha256d(payload)[:4]
        return crypto.b58encode(payload + chk)

    @property
    def verifying_key(self) -> VerifyingKey:
        return self.signing_key.get_verifying_key()

    def pubkey_serialized(self) -> bytes:
        return b"\x04" + self.verifying_key.to_string()

    def address(self) -> str:
        return crypto.address_from_pubkey(self.pubkey_serialized())

    def pubkey_hash(self) -> bytes:
        return crypto.hash160(self.pubkey_serialized())

    def sign_tx(self, tx: Transaction, input_index: int) -> bytes:
        digest = tx.signing_digest(input_index)
        sig = self.signing_key.sign_digest(digest, sigencode=sigencode_string_canonize)
        return self.pubkey_serialized() + sig

    @staticmethod
    def verify_input(tx: Transaction, input_index: int, prev_output: TxOutput) -> bool:
        inp = tx.inputs[input_index]
        if len(inp.script_sig) < 65 + 64:
            return False
        pub = inp.script_sig[:65]
        sig = inp.script_sig[65:]
        if pub[0:1] != b"\x04" or len(pub) != 65:
            return False
        if crypto.hash160(pub) != prev_output.recipient_pubkey_hash:
            return False
        try:
            vk = VerifyingKey.from_string(pub[1:], curve=SECP256k1)
        except Exception:
            return False
        digest = tx.signing_digest(input_index)
        try:
            return vk.verify_digest(sig, digest, sigdecode=sigdecode_string)
        except Exception:
            return False


def coinbase_output(wallet: Wallet, value: int) -> TxOutput:
    return TxOutput(
        value=value,
        recipient_pubkey_hash=wallet.pubkey_hash(),
        kind=OutputKind.TRANSFER,
    )

"""
Tancoin Virtual Machine (TVM) — small deterministic stack machine for smart contracts.

This is *not* the EVM: opcodes differ, but the model (code + storage + gas) is familiar
to Ethereum developers. See ``docs/SMART_CONTRACTS.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Opcodes
OP_STOP = 0x00
OP_PUSH1 = 0x01
OP_ADD = 0x10
OP_SUB = 0x11
OP_MUL = 0x12
OP_DUP = 0x20
OP_SWAP = 0x21
OP_SLOAD = 0x30
OP_SSTORE = 0x31
OP_TIMESTAMP = 0x40
OP_CALLER_BALANCE = 0x41  # pushes mock balance 0 for now (hook for extensions)


@dataclass
class TVMContext:
    block_timestamp: int
    caller_pubkey_hash: bytes
    contract_address: bytes
    gas_limit: int


@dataclass
class TVMResult:
    success: bool
    gas_used: int
    return_data: bytes
    error: str | None = None


@dataclass
class TVM:
    code: bytes
    storage: dict[bytes, bytes] = field(default_factory=dict)
    stack: list[int] = field(default_factory=list)
    pc: int = 0
    gas: int = 0

    def _consume(self, amount: int, ctx: TVMContext) -> bool:
        self.gas += amount
        return self.gas <= ctx.gas_limit

    def _push(self, v: int) -> None:
        self.stack.append(v & ((1 << 256) - 1))

    def _pop(self) -> int:
        if not self.stack:
            raise TVMError("stack underflow")
        return self.stack.pop()

    def run(self, calldata: bytes, ctx: TVMContext) -> TVMResult:
        self.pc = 0
        self.gas = 0
        ret = bytearray()
        try:
            while self.pc < len(self.code):
                op = self.code[self.pc]
                self.pc += 1
                if op == OP_STOP:
                    break
                if op == OP_PUSH1:
                    if not self._consume(3, ctx):
                        raise TVMError("out of gas")
                    if self.pc >= len(self.code):
                        raise TVMError("truncated PUSH1")
                    self._push(self.code[self.pc])
                    self.pc += 1
                elif op == OP_ADD:
                    if not self._consume(3, ctx):
                        raise TVMError("out of gas")
                    a, b = self._pop(), self._pop()
                    self._push(a + b)
                elif op == OP_SUB:
                    if not self._consume(3, ctx):
                        raise TVMError("out of gas")
                    a, b = self._pop(), self._pop()
                    self._push(a - b)
                elif op == OP_MUL:
                    if not self._consume(5, ctx):
                        raise TVMError("out of gas")
                    a, b = self._pop(), self._pop()
                    self._push(a * b)
                elif op == OP_DUP:
                    if not self._consume(3, ctx):
                        raise TVMError("out of gas")
                    x = self._pop()
                    self._push(x)
                    self._push(x)
                elif op == OP_SWAP:
                    if not self._consume(3, ctx):
                        raise TVMError("out of gas")
                    a, b = self._pop(), self._pop()
                    self._push(a)
                    self._push(b)
                elif op == OP_SLOAD:
                    if not self._consume(10, ctx):
                        raise TVMError("out of gas")
                    k = self._pop().to_bytes(32, "big")
                    v = self.storage.get(k, b"\x00" * 32)
                    self._push(int.from_bytes(v[:32], "big"))
                elif op == OP_SSTORE:
                    if not self._consume(20, ctx):
                        raise TVMError("out of gas")
                    val = self._pop()
                    key = self._pop().to_bytes(32, "big")
                    self.storage[key] = val.to_bytes(32, "big")
                elif op == OP_TIMESTAMP:
                    if not self._consume(2, ctx):
                        raise TVMError("out of gas")
                    self._push(ctx.block_timestamp)
                elif op == OP_CALLER_BALANCE:
                    if not self._consume(2, ctx):
                        raise TVMError("out of gas")
                    self._push(0)
                else:
                    raise TVMError(f"unknown opcode {op:#x}")
            return TVMResult(True, self.gas, bytes(ret), None)
        except TVMError as e:
            return TVMResult(False, self.gas, bytes(ret), str(e))


class TVMError(Exception):
    pass


def contract_address_from_deploy(txid: bytes, output_index: int) -> bytes:
    from tancoin_core import crypto

    return crypto.hash160(txid + output_index.to_bytes(4, "big"))

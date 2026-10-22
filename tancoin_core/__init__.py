"""
Tancoin (TAN) — modular blockchain core (Python only, no Django dependency).

Import from applications::

    from tancoin_core import Chain, Wallet, Transaction
    from tancoin_core import constants

Public HTTP API is provided by the Django app ``chain_api``.
"""

from tancoin_core.chain import Chain
from tancoin_core.constants import COIN_SYMBOL, COIN_DECIMALS, SATOSHIS_PER_COIN
from tancoin_core.transaction import Transaction, TxInput, TxOutput, OutputKind
from tancoin_core.wallet import Wallet

__all__ = [
    "Chain",
    "Wallet",
    "Transaction",
    "TxInput",
    "TxOutput",
    "OutputKind",
    "COIN_SYMBOL",
    "COIN_DECIMALS",
    "SATOSHIS_PER_COIN",
]

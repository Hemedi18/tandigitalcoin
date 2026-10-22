"""Chain identity and economic parameters (documented for integrators)."""

COIN_NAME = "Tancoin"
COIN_SYMBOL = "TAN"
COIN_DECIMALS = 8
SATOSHIS_PER_COIN = 10**COIN_DECIMALS

# Proof-of-work: leading zero bits required for block hash (hex digest).
# Lower values mine faster (dev). Production-style networks typically use much harder targets.
INITIAL_DIFFICULTY_BITS = 18

# Max coin supply cap (in satoshis) — informational; enforcement in coinbase validation.
MAX_SUPPLY_SATOSHIS = 21_000_000 * SATOSHIS_PER_COIN

# Reference "price" for demos / mock tickers (USD per 1 TAN). Not a market feed.
REFERENCE_PRICE_USD_DEFAULT = 0.01

# Contract execution
DEFAULT_CONTRACT_GAS_LIMIT = 100_000

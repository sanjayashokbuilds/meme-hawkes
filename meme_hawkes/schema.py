"""The one table format every data source must produce.

One row = one trade on one token. Whether the data came from Dune or Helius,
it is converted into exactly these columns, so nothing downstream needs to
know where it came from.
"""

import pandas as pd

TRADE_COLUMNS = {
    "mint": "token address (identifies the token)",
    "slot": "Solana slot number (one slot is roughly 400 ms)",
    "tx_index": "position of the transaction inside its slot (orders same-slot trades)",
    "signature": "transaction id (used to drop duplicate rows)",
    "wallet": "address of the wallet that traded",
    "side": "'buy' or 'sell'",
    "sol_amount": "SOL paid (buy) or received (sell)",
}


def validate_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Raise an error early if a data source hands us a badly shaped table."""
    missing = set(TRADE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"trade table is missing columns: {sorted(missing)}")

    bad_sides = set(df["side"].unique()) - {"buy", "sell"}
    if bad_sides:
        raise ValueError(f"unexpected values in 'side': {sorted(bad_sides)}")

    if (df["sol_amount"] < 0).any():
        raise ValueError("sol_amount must be non-negative")

    return df

"""Turn a raw trade table into a clean, time-ordered one."""

import hashlib

import pandas as pd

from .schema import validate_trades

SLOT_SECONDS = 0.4  # Solana's target slot length; checked against real block times in Stage 2


def clean_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, drop duplicates, order trades in time, and add a clock.

    Adds two columns:
      t         seconds since the token's first trade, from slot numbers
      slot_ties how many trades share this trade's slot (ties are handled in Stage 3)
    """
    df = validate_trades(df.copy())

    # The same trade can appear twice if a source pages its results.
    df = df.drop_duplicates(subset=["signature", "wallet", "side"])

    # Time order: by slot, then by position inside the slot.
    df = df.sort_values(["mint", "slot", "tx_index"]).reset_index(drop=True)

    first_slot = df.groupby("mint")["slot"].transform("min")
    df["t"] = (df["slot"] - first_slot) * SLOT_SECONDS
    df["slot_ties"] = df.groupby(["mint", "slot"])["slot"].transform("size")
    return df


def anonymise_wallets(df: pd.DataFrame, salt: str) -> pd.DataFrame:
    """Replace wallet addresses with short salted hashes before anything is published.

    The same wallet always gets the same code (so analysis still works),
    but the code can't be turned back into the address without the salt.
    """
    df = df.copy()
    df["wallet"] = df["wallet"].map(
        lambda w: hashlib.sha256((salt + w).encode()).hexdigest()[:12]
    )
    return df

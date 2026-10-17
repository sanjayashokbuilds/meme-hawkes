"""Turn a raw trade table into a clean, time-ordered one."""

import hashlib

import pandas as pd

from .schema import validate_trades

DEFAULT_SLOT_SECONDS = 0.4  # fallback only; real slot length is measured per token


def seconds_per_slot(slots: pd.Series, block_times: pd.Series) -> float:
    """Measure how long a slot really lasts, from the token's own trades.

    Block times are whole seconds but accurate over longer spans; slots are
    precise in order but their length varies. Fitting a straight line of
    block time against slot gives the real seconds-per-slot (the slope).
    Falls back to 0.4 s when there's too little spread to measure it.
    """
    ok = block_times.notna()
    x, y = slots[ok].astype(float), block_times[ok].astype(float)
    if x.nunique() < 2 or y.max() - y.min() < 10:  # under 10 s of data: too noisy
        return DEFAULT_SLOT_SECONDS
    slope = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()
    return float(slope) if 0.05 < slope < 2 else DEFAULT_SLOT_SECONDS


def clean_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, drop duplicates, order trades in time, and add a clock.

    Adds three columns:
      t                 seconds since the token's first trade (slots x measured slot length)
      seconds_per_slot  the measured slot length for that token
      slot_ties         how many trades share this trade's slot (ties are handled in Stage 3)
    """
    df = validate_trades(df.copy())

    # The same trade can appear twice if a source pages its results.
    # (One transaction can hold several trades, so the key is signature + position.)
    df = df.drop_duplicates(subset=["signature", "tx_index"])

    # Time order: by slot, then by position inside the slot.
    df = df.sort_values(["mint", "slot", "tx_index"]).reset_index(drop=True)

    if "block_time" not in df:
        df["block_time"] = None
    lengths = {
        mint: seconds_per_slot(g["slot"], pd.to_numeric(g["block_time"]))
        for mint, g in df.groupby("mint")
    }
    df["seconds_per_slot"] = df["mint"].map(lengths)
    first_slot = df.groupby("mint")["slot"].transform("min")
    df["t"] = (df["slot"] - first_slot) * df["seconds_per_slot"]
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

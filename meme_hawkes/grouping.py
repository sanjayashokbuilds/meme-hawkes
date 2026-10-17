"""Label each wallet as an early-slot buyer or an ordinary trader.

Heuristic: a wallet is "early" on a token if its first buy lands within the
first `first_slots` slots of that token's trading. Buying that fast is a
strong sign of an automated, likely coordinated sniper. It is a proxy for
coordination, not proof of it.

It only needs one token's trades, so it works for live lookups in the app.
"""

import pandas as pd


def label_groups(df: pd.DataFrame, first_slots: int = 5) -> pd.DataFrame:
    """Add 'group' ('early' or 'ordinary') and 'event_type' (e.g. 'early_buy').

    Expects a table from clean_trades. The group is a property of the wallet,
    so an early wallet's later sells count as 'early_sell'.
    """
    df = df.copy()
    launch_slot = df.groupby("mint")["slot"].transform("min")
    is_early_buy = (df["side"] == "buy") & (df["slot"] - launch_slot < first_slots)

    early_wallets = set(zip(df.loc[is_early_buy, "mint"], df.loc[is_early_buy, "wallet"]))
    df["group"] = [
        "early" if (m, w) in early_wallets else "ordinary"
        for m, w in zip(df["mint"], df["wallet"])
    ]
    df["event_type"] = df["group"] + "_" + df["side"]
    return df

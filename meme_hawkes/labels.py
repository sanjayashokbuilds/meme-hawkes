"""Label each token as a pump-and-dump or not, using its price path only.

PRE-REGISTERED: this rule was fixed and committed before any Hawkes model was
fitted to real data, so the early-warning evaluation can't be tuned to it.

Primary rule (one token, within its observation window):
  1. Find the highest price reached (the peak).
  2. PUMP: the peak is at least 2x the lowest price seen before it (+100%).
  3. DUMP: after the peak, the price falls to half the peak or lower (-50%).
  A token is a pump-and-dump if both happen. The dump time is the first trade
  at or below half the peak; Stage 5 measures warnings against it.

Sensitivity rule: the thresholds of Mongardini & Mei (+50% pump, -30% dump).
They were designed for hourly data on exchanges; on a bonding curve, prices
move faster and mechanically with every buy, so the primary rule is stricter.

Price only, deliberately: wallet groups and trade timing are what the model
uses, so letting them into the label would make the evaluation circular.
"""

import numpy as np
import pandas as pd


def label_token(t: pd.Series, price: pd.Series, pump: float = 2.0, dump: float = 0.5) -> dict:
    """Apply the rule to one token's trade times and post-trade prices (in time order)."""
    t, price = np.asarray(t, float), np.asarray(price, float)
    if np.all(np.isnan(price)):  # no usable prices: can't be labelled, so excluded later
        return {"pump_and_dump": None, "peak_time": np.nan, "dump_time": np.nan, "peak_over_low": np.nan}
    peak_i = int(np.nanargmax(price))
    low_before = np.nanmin(price[: peak_i + 1])
    pumped = price[peak_i] >= pump * low_before

    after = np.where(price[peak_i:] <= dump * price[peak_i])[0]
    dumped = len(after) > 0
    return {
        "pump_and_dump": bool(pumped and dumped),
        "peak_time": t[peak_i],
        "dump_time": t[peak_i + after[0]] if (pumped and dumped) else np.nan,
        "peak_over_low": price[peak_i] / low_before,
    }


def label_sample(trades: pd.DataFrame) -> pd.DataFrame:
    """One row per token: primary label, dump time, and the sensitivity label."""
    rows = []
    for mint, g in trades.sort_values(["mint", "t"]).groupby("mint"):
        primary = label_token(g["t"], g["price"])
        sensitivity = label_token(g["t"], g["price"], pump=1.5, dump=0.7)
        rows.append({"mint": mint, **primary, "pump_and_dump_mm": sensitivity["pump_and_dump"],
                     "quote": g["quote"].iloc[0] if "quote" in g else "SOL"})
    return pd.DataFrame(rows)

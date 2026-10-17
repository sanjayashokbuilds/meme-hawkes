"""Early-warning signals and their honest evaluation.

Every signal at trade k uses only trades up to and including k, never the
future, so it could have been computed live. A token's *alarm* is the first
time a signal crosses its threshold. For a pump-and-dump an alarm only counts
if it comes before the dump; lead time = dump time - alarm time. For any other
token, an alarm is a false alarm. (Design fixed in docs/DECISIONS.md #27.)
"""

import numpy as np
import pandas as pd

from . import hawkes
from .clean import spread_ties

WINDOW, STEP = 30, 5


def signals(g: pd.DataFrame, window: int = WINDOW, step: int = STEP, seed: int = 0) -> pd.DataFrame:
    """Signals for one token (trades in time order), every `step` trades.

    n             branching ratio fitted to the last `window` trades
    rate          trades per second over the last `window` trades
    price_ratio   current price / lowest price so far
    early_sells   share of the last `window` trades that are early-wallet sells
    """
    g = g.reset_index(drop=True)
    times = spread_ties(g, np.random.default_rng(seed)).to_numpy()
    order = np.argsort(times, kind="stable")
    g, times = g.iloc[order].reset_index(drop=True), times[order]
    price = g["price"].to_numpy(float)
    running_low = np.fmin.accumulate(price)
    early_sell = (g["event_type"] == "early_sell").to_numpy()

    rows = []
    for k in range(window - 1, len(g), step):
        w = times[k - window + 1 : k + 1]
        span = w[-1] - w[0]
        n = np.nan
        if span > 0:
            n = hawkes.fit(w - w[0], span + g["seconds_per_slot"].iloc[0])["n"]
        rows.append({"t": times[k], "n": n, "rate": (window - 1) / span if span > 0 else np.inf,
                     "price_ratio": price[k] / running_low[k],
                     "early_sells": early_sell[k - window + 1 : k + 1].mean()})
    return pd.DataFrame(rows)


def first_alarm(sig: pd.DataFrame, column: str, threshold: float) -> float:
    """Time of the first signal value at or above the threshold (NaN if never)."""
    hit = sig.loc[sig[column] >= threshold, "t"]
    return float(hit.iloc[0]) if len(hit) else np.nan


def evaluate(all_signals: dict, labels: pd.DataFrame, column: str, threshold: float) -> dict:
    """Recall, false-alarm rate, precision and lead time for one signal at one threshold.

    all_signals: {mint: signals DataFrame}; labels: one row per token with
    pump_and_dump and dump_time. Tokens with no signal rows (too few trades) never alarm.
    """
    hits, misses, late, false_alarms, quiet, leads = 0, 0, 0, 0, 0, []
    for _, row in labels.iterrows():
        sig = all_signals.get(row["mint"])
        alarm = first_alarm(sig, column, threshold) if sig is not None and len(sig) else np.nan
        if row["pump_and_dump"]:
            if np.isnan(alarm):
                misses += 1
            elif alarm < row["dump_time"]:
                hits += 1
                leads.append(row["dump_time"] - alarm)
            else:
                late += 1
        else:
            false_alarms += int(not np.isnan(alarm))
            quiet += int(np.isnan(alarm))
    positives, negatives = hits + misses + late, false_alarms + quiet
    return {"signal": column, "threshold": threshold, "hits": hits, "positives": positives,
            "false_alarms": false_alarms, "negatives": negatives,
            "recall": hits / positives if positives else np.nan,
            "false_alarm_rate": false_alarms / negatives if negatives else np.nan,
            "precision": hits / (hits + false_alarms) if hits + false_alarms else np.nan,
            "too_late": late, "median_lead_s": float(np.median(leads)) if leads else np.nan}


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a proportion (Wilson's method, sensible for small samples)."""
    if total == 0:
        return np.nan, np.nan
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return centre - half, centre + half

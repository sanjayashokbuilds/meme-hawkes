"""Checks for the app's analysis function, on a simulated token."""

import numpy as np
import pandas as pd

from meme_hawkes import fading
from meme_hawkes.analysis import analyse


def simulated_token(seed=1):
    rng = np.random.default_rng(seed)
    t = fading.simulate(0.05, 2.0, 0.02, 0.8, 2.0, 600, rng)
    n = len(t)
    return pd.DataFrame({
        "mint": "TOK", "slot": (t / 0.4).astype(int), "tx_index": np.arange(n), "t": t,
        "seconds_per_slot": 0.4, "wallet": rng.choice([f"W{i}" for i in range(30)], n),
        "side": rng.choice(["buy", "sell"], n), "price": np.linspace(1, 2, n), "quote": "SOL",
        "group": np.where(rng.uniform(size=n) < 0.2, "early", "ordinary"),
    })


def test_analysis_returns_numbers_curves_and_sentences():
    r = analyse(simulated_token())
    assert r["ok"] and 0 < r["n"] < 1 and r["half_life_s"] > 0
    assert len(r["curve"]) == 1500 and len(r["ticks"]) == r["trades"]
    assert r["early_to_ordinary"] is not None
    assert all(isinstance(s, str) for s in r["sentences"])


def test_wallet_addresses_never_leave_the_analysis():
    r = analyse(simulated_token())
    assert "wallet" not in r["ticks"].columns


def test_too_few_trades_is_explained_not_crashed():
    r = analyse(simulated_token().head(10))
    assert not r["ok"] and "at least" in r["reason"]

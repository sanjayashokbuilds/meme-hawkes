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
    assert len(r["curve"]) > 500 and len(r["ticks"]) == r["trades"]
    assert (r["curve"]["intensity"] >= r["curve"]["background"] - 1e-9).all()
    assert r["early_to_ordinary"] is not None
    assert all(isinstance(s, str) for s in r["sentences"])


def test_wallet_addresses_never_leave_the_analysis():
    r = analyse(simulated_token())
    assert "wallet" not in r["ticks"].columns


def test_too_few_trades_is_explained_not_crashed():
    r = analyse(simulated_token().head(10))
    assert not r["ok"] and "at least" in r["reason"]


def test_reaction_probabilities_are_probabilities_and_average_to_the_share():
    r = analyse(simulated_token())
    p = r["ticks"]["p_reaction"]
    assert p.between(0, 1).all() and p.iloc[0] == 0      # the first trade can't be a reaction
    assert abs(p.mean() - r["reaction_share"]) < 1e-9


def test_reaction_share_is_close_to_the_true_share_on_simulated_data():
    # With true n = 0.4, about 40% of events are reactions once the process is going;
    # the launch burst pulls the share down a little, so allow a wide band.
    r = analyse(simulated_token(seed=3))
    assert 0.2 < r["reaction_share"] < 0.55

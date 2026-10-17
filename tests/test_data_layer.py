"""Checks for the data layer, on a tiny hand-made token we can reason about."""

import pandas as pd
import pytest

from meme_hawkes.clean import anonymise_wallets, clean_trades
from meme_hawkes.grouping import label_groups


def tiny_token():
    # Two wallets buy in the launch slot, one ordinary buyer later,
    # then the early wallet A sells. Row 2 duplicates row 1.
    return pd.DataFrame({
        "mint": ["TOK"] * 5,
        "slot": [100, 100, 100, 130, 160],
        "tx_index": [0, 1, 1, 0, 0],
        "signature": ["s1", "s2", "s2", "s3", "s4"],
        "wallet": ["A", "B", "B", "C", "A"],
        "side": ["buy", "buy", "buy", "buy", "sell"],
        "sol_amount": [1.0, 0.5, 0.5, 0.2, 1.4],
    })


def test_clean_drops_duplicates_and_builds_clock():
    df = clean_trades(tiny_token())
    assert len(df) == 4                                  # duplicate removed
    assert list(df["t"]) == pytest.approx([0, 0, 12, 24])  # 30 slots x 0.4 s = 12 s
    assert list(df["slot_ties"]) == [2, 2, 1, 1]          # two trades share slot 100


def test_clock_is_calibrated_to_real_block_times():
    # 100 trades, one every 10 slots, where block times say each slot lasts 0.25 s.
    slots = list(range(1000, 2000, 10))
    df = pd.DataFrame({
        "mint": "TOK", "slot": slots, "tx_index": 0,
        "signature": [f"s{i}" for i in range(100)], "wallet": "A", "side": "buy",
        "sol_amount": 0.1,
        "block_time": [1_700_000_000 + int((s - 1000) * 0.25) for s in slots],  # whole seconds
    })
    out = clean_trades(df)
    assert out["seconds_per_slot"].iloc[0] == pytest.approx(0.25, abs=0.01)
    assert out["t"].iloc[-1] == pytest.approx(990 * 0.25, rel=0.02)


def test_spread_ties_breaks_ties_inside_the_slot_and_keeps_order():
    import numpy as np
    from meme_hawkes.clean import spread_ties
    df = clean_trades(tiny_token())                      # two trades share slot 100
    t = spread_ties(df, np.random.default_rng(0)).to_numpy()
    assert len(set(t)) == len(t)                         # no ties left
    assert all(np.diff(t) > 0)                           # order kept
    assert all((t >= df["t"]) & (t < df["t"] + 0.4))     # each stays inside its slot


def test_early_wallets_keep_their_label_when_selling():
    df = label_groups(clean_trades(tiny_token()))
    assert list(df["event_type"]) == ["early_buy", "early_buy", "ordinary_buy", "early_sell"]


def test_bad_side_value_is_rejected():
    bad = tiny_token()
    bad.loc[0, "side"] = "swap"
    with pytest.raises(ValueError):
        clean_trades(bad)


def test_anonymised_wallets_are_consistent_and_hidden():
    df = anonymise_wallets(clean_trades(tiny_token()), salt="test")
    assert "A" not in set(df["wallet"])
    assert df["wallet"].iloc[0] == df["wallet"].iloc[3]   # wallet A both times

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

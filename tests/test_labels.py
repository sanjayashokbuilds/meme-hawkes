"""Checks for the pump-and-dump rule on price paths small enough to check by eye."""

import numpy as np
import pandas as pd

from meme_hawkes.labels import label_sample, label_token

T = np.arange(6.0)


def test_classic_pump_and_dump():
    # 1 -> 3 (tripled from the low), then down to 1.2 (below half of 3)
    out = label_token(T, [1, 2, 3, 2.5, 1.2, 1.0])
    assert out["pump_and_dump"] and out["peak_time"] == 2 and out["dump_time"] == 4


def test_pump_without_dump():
    assert not label_token(T, [1, 2, 3, 2.8, 2.5, 2.9])["pump_and_dump"]


def test_slow_bleed_without_pump():
    # never doubles, so a later fall doesn't count
    assert not label_token(T, [1, 1.5, 1.8, 1.2, 0.8, 0.5])["pump_and_dump"]


def test_sensitivity_rule_is_looser():
    trades = pd.DataFrame({"mint": "TOK", "t": T, "price": [1, 1.4, 1.6, 1.3, 1.1, 1.0]})
    row = label_sample(trades).iloc[0]
    assert not row["pump_and_dump"]          # +60% isn't a doubling
    assert row["pump_and_dump_mm"]           # but it is +50% then -30%


def test_token_without_prices_is_left_unlabelled_not_crashed():
    assert label_token(T, [np.nan] * 6)["pump_and_dump"] is None

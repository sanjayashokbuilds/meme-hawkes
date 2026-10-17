"""Checks for the early-warning evaluation on tiny hand-made cases."""

import numpy as np
import pandas as pd
import pytest

from meme_hawkes.warning import evaluate, first_alarm, signals

LABELS = pd.DataFrame({"mint": ["A", "B", "C", "D"], "pump_and_dump": [True, True, False, False],
                       "dump_time": [50.0, 20.0, np.nan, np.nan]})


def sig(times, values):
    return pd.DataFrame({"t": times, "x": values})


def test_first_alarm_is_the_first_crossing():
    assert first_alarm(sig([1, 2, 3], [0.1, 0.9, 0.95]), "x", 0.9) == 2
    assert np.isnan(first_alarm(sig([1, 2], [0.1, 0.2]), "x", 0.9))


def test_alarm_only_counts_before_the_dump():
    s = {"A": sig([10, 40], [0.0, 1.0]),    # alarm at 40, dump at 50: hit, 10 s lead
         "B": sig([10, 30], [0.0, 1.0]),    # alarm at 30, dump at 20: too late
         "C": sig([5], [1.0]),              # alarm on a non-dump token: false alarm
         "D": sig([5], [0.0])}              # quiet non-dump token
    out = evaluate(s, LABELS, "x", 0.5)
    assert out["recall"] == 0.5 and out["too_late"] == 1
    assert out["false_alarm_rate"] == 0.5 and out["precision"] == 0.5
    assert out["median_lead_s"] == 10


def test_signals_only_use_the_past():
    # Prices jump at trade 40; the price signal must not react before trade 40 arrives.
    n = 60
    g = pd.DataFrame({"mint": "A", "slot": np.arange(n) * 10, "t": np.arange(n, dtype=float),
                      "seconds_per_slot": 0.1, "price": [1.0] * 40 + [5.0] * 20,
                      "event_type": "ordinary_buy"})
    s = signals(g, window=30, step=5)
    before = s[s["t"] < 40]
    assert (before["price_ratio"] < 1.01).all()
    assert s["price_ratio"].iloc[-1] == pytest.approx(5.0, rel=0.01)

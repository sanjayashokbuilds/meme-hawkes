"""Checks for the sampling rule, with the blockchain calls replaced by fakes."""

import pytest

from meme_hawkes import sample


def fake_chain(monkeypatch, launches_per_tx, tx_counts):
    """launches_per_tx: mints found in each launch transaction; tx_counts: first-hour size per mint."""
    sigs = [f"sig{i}" for i in range(len(launches_per_tx))]
    monkeypatch.setattr(sample, "launch_signatures", lambda url, start, end: list(sigs))
    monkeypatch.setattr(sample, "rpc", lambda url, method, params: {"sig": params[0]})
    monkeypatch.setattr(sample, "launches_in_transaction", lambda tx: launches_per_tx[int(tx["sig"][3:])])

    def history(url, mint):
        if tx_counts[mint] is None:
            raise ValueError("too large")
        return [{"signature": f"{mint}-{k}", "blockTime": 1000 + k} for k in range(tx_counts[mint])]

    monkeypatch.setattr(sample, "list_signatures", history)


def test_keeps_only_active_tokens_and_logs_every_decision(monkeypatch):
    fake_chain(monkeypatch, [["A"], ["B"], ["C"]], {"A": 150, "B": 20, "C": None})
    kept, log = sample.choose_tokens("url", n_tokens=10, min_tx=100)
    assert [k["mint"] for k in kept] == ["A"]
    assert {row["mint"]: row["kept"] for row in log} == {"A": True, "B": False, "C": False}


def test_stops_once_enough_tokens(monkeypatch):
    fake_chain(monkeypatch, [["A"], ["B"], ["C"]], {"A": 150, "B": 150, "C": 150})
    kept, _ = sample.choose_tokens("url", n_tokens=2, min_tx=100)
    assert len(kept) == 2


def test_wrong_mint_authority_is_caught(monkeypatch):
    fake_chain(monkeypatch, [[] for _ in range(25)], {})
    with pytest.raises(RuntimeError, match="address is probably wrong"):
        sample.choose_tokens("url")

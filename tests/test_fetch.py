"""Checks for the event decoders, using hand-built fake events (no internet needed).

These prove the unpacking logic is right. Whether the real on-chain format
still matches is checked by running scripts/fetch_one.py on a real token.
"""

import base64
import struct

import base58
import pytest

from meme_hawkes.fetch import (
    CREATE_EVENT,
    EVENT_LAYOUT,
    TRADE_EVENT,
    decode_create_events,
    decode_trade_events,
    events_in_transaction,
    launches_in_transaction,
)

MINT = bytes(range(32))
USER = bytes(range(32, 64))


def fake_trade(is_buy=True, lamports=1_500_000_000):
    # Reserves: 40 SOL and 800 million tokens -> price 40 / 800e6 = 5e-8 SOL per token.
    body = EVENT_LAYOUT.pack(MINT, lamports, 999, is_buy, USER, 1_700_000_000, 40 * 10**9, 800_000_000 * 10**6)
    extra_fields = struct.pack("<QQ", 1, 2)  # real events carry more fields after these
    return TRADE_EVENT + body + extra_fields


def fake_create(name=b"Dog Coin", symbol=b"DOG", uri=b"https://example.com/x.json"):
    strings = b"".join(struct.pack("<I", len(s)) + s for s in (name, symbol, uri))
    return CREATE_EVENT + strings + MINT + USER  # mint, then more keys


def test_trade_decoder_finds_event_inside_other_bytes():
    [event] = decode_trade_events(b"\x01\x02junk-prefix" + fake_trade())
    assert event["mint"] == base58.b58encode(MINT).decode()
    assert event["wallet"] == base58.b58encode(USER).decode()
    assert event["side"] == "buy"
    assert event["sol_amount"] == 1.5
    assert event["price"] == pytest.approx(5e-8)


def test_trade_decoder_reads_sells_and_multiple_events():
    raw = fake_trade(is_buy=True) + fake_trade(is_buy=False)
    assert [e["side"] for e in decode_trade_events(raw)] == ["buy", "sell"]


def test_create_decoder_skips_the_strings_to_find_the_mint():
    assert decode_create_events(b"junk" + fake_create()) == [base58.b58encode(MINT).decode()]


def test_create_decoder_ignores_garbage_after_the_tag():
    assert decode_create_events(CREATE_EVENT + b"\xff\xff\xff\xff") == []


def test_inner_instructions_preferred_over_logs():
    data = base58.b58encode(fake_trade()).decode()
    tx = {"meta": {
        "innerInstructions": [{"instructions": [{"data": data}]}],
        "logMessages": ["Program data: " + base64.b64encode(fake_trade()).decode()],
    }}
    assert len(events_in_transaction(tx)) == 1  # not counted twice


def test_falls_back_to_logs():
    tx = {"meta": {
        "innerInstructions": [],
        "logMessages": ["Program data: " + base64.b64encode(fake_create()).decode()],
    }}
    assert launches_in_transaction(tx) == [base58.b58encode(MINT).decode()]

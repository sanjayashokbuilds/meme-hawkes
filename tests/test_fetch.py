"""Checks for the TradeEvent decoder, using hand-built fake events (no internet needed).

These prove the unpacking logic is right. Whether the real on-chain format
still matches is checked separately by running scripts/fetch_one.py on a real token.
"""

import base64
import struct

import base58

from meme_hawkes.fetch import EVENT_LAYOUT, TRADE_EVENT, decode_trade_events, events_in_transaction

MINT = bytes(range(32))
USER = bytes(range(32, 64))


def fake_event(is_buy=True, lamports=1_500_000_000):
    body = EVENT_LAYOUT.pack(MINT, lamports, 999, is_buy, USER, 1_700_000_000)
    extra_fields = struct.pack("<QQ", 1, 2)  # real events carry more fields after these
    return TRADE_EVENT + body + extra_fields


def test_decoder_finds_event_inside_other_bytes():
    raw = b"\x01\x02junk-prefix" + fake_event()
    [event] = decode_trade_events(raw)
    assert event["mint"] == base58.b58encode(MINT).decode()
    assert event["wallet"] == base58.b58encode(USER).decode()
    assert event["side"] == "buy"
    assert event["sol_amount"] == 1.5


def test_decoder_reads_sells_and_multiple_events():
    raw = fake_event(is_buy=True) + fake_event(is_buy=False)
    assert [e["side"] for e in decode_trade_events(raw)] == ["buy", "sell"]


def test_inner_instructions_preferred_over_logs():
    data = base58.b58encode(fake_event()).decode()
    tx = {"meta": {
        "innerInstructions": [{"instructions": [{"data": data}]}],
        "logMessages": ["Program data: " + base64.b64encode(fake_event()).decode()],
    }}
    assert len(events_in_transaction(tx)) == 1  # not counted twice


def test_falls_back_to_logs():
    tx = {"meta": {
        "innerInstructions": [],
        "logMessages": ["Program data: " + base64.b64encode(fake_event(is_buy=False)).decode()],
    }}
    assert events_in_transaction(tx)[0]["side"] == "sell"

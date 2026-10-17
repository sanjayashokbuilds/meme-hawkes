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
    PUMP_PROGRAM,
    TRADE_EVENT,
    bonding_curve_address,
    decode_create_events,
    decode_trade_events,
    events_in_transaction,
    launches_in_transaction,
    program_address,
)

# A real on-chain event (public data): the first trade of a USDC-priced token,
# copied from its transaction. The transaction's own USDC balance changes show
# 17.913488 USDC went into the curve, leaving 4,309.913488 USDC virtual reserves.
REAL_USDC_TRADE = "BUV4LqTLWqEhXptXmSCkvVHYB8N8rgTJ4LuDfzXyBSUMLgwR3vLoTbjCYCSuSKR41u4q1J8ijr2uWY6sbZ6AnHXQcofsChVLFCUpq7NGw4PuETMJuUPzFqGwB6SvWYZqbV8tRfZNrn3xpCQ4WBkkfzbtJyeFrMdo5PoXpDjS2KsntbAW1WZ69RFEWghggkr1dp6Qtawp3HkSjFk2AggJYMQBwWjamTwxFsmpwbAZysaAHP884rP6RwZ1y3FsPiBt1DzsA8tZ8bgqoRPUZvvTj1DaEViQ2MXTh6koZ1RvSshYmxX3akVZoqknbYkTutYRdcvZZWF4qp67LNrg5g1WfMfSySbLe4mmQvy2LW4Nach5tfy5gTp7SVVJWXXPbPpSFdFk2PDVtEkdRJXo62jg7Jzbr35KAkF6qCEfChkVxcPNNiFaGhsmruqtp8R8dSyek7RGwrsgvnTGm8d1e6s2nUsohf2dGFJo5CWeN9XMJ9UjpfPB4dHaSvJGdNRF6PYWTi4xNd5faRBxp2GtQ86WK"

MINT = bytes(range(32))
USER = bytes(range(32, 64))


def fake_trade(is_buy=True, lamports=1_500_000_000):
    # Reserves: 40 SOL and 800 million tokens -> price 40 / 800e6 = 5e-8 SOL per token.
    body = EVENT_LAYOUT.pack(MINT, lamports, 999, is_buy, USER, 1_700_000_000, 40 * 10**9, 800_000_000 * 10**6)
    extra_fields = struct.pack("<QQ", 1, 2)  # real events carry more fields after these
    return TRADE_EVENT + body + extra_fields


CURVE = bytes(range(64, 96))


def fake_create(name=b"Dog Coin", symbol=b"DOG", uri=b"https://example.com/x.json"):
    strings = b"".join(struct.pack("<I", len(s)) + s for s in (name, symbol, uri))
    return CREATE_EVENT + strings + MINT + CURVE + USER  # mint, bonding curve, then more keys


def test_trade_decoder_finds_event_inside_other_bytes():
    [event] = decode_trade_events(b"\x01\x02junk-prefix" + fake_trade())
    assert event["mint"] == base58.b58encode(MINT).decode()
    assert event["wallet"] == base58.b58encode(USER).decode()
    assert event["side"] == "buy"
    assert event["sol_amount"] == 1.5
    assert event["price"] == pytest.approx(5e-8)
    assert event["quote"] == "SOL" and event["amount"] == 1.5


def test_trade_decoder_reads_sells_and_multiple_events():
    raw = fake_trade(is_buy=True) + fake_trade(is_buy=False)
    assert [e["side"] for e in decode_trade_events(raw)] == ["buy", "sell"]


def test_create_decoder_skips_the_strings_to_find_the_mint_and_curve():
    assert decode_create_events(b"junk" + fake_create()) == [
        {"mint": base58.b58encode(MINT).decode(), "bonding_curve": base58.b58encode(CURVE).decode()}]


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
    assert launches_in_transaction(tx)[0]["mint"] == base58.b58encode(MINT).decode()


def test_bonding_curve_address_matches_real_chain_data():
    # Pairs read from a real launch transaction.
    assert bonding_curve_address("AmxHq6z7B4svddqfSzHBB9TiCYwBBhhdaarMCY2Lpump") == \
        "2F4NrukLW4STzCuruUMYSCJYfHtu5YARRSQw18Ws3wbC"
    assert program_address([b"__event_authority"], PUMP_PROGRAM) == "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"


def test_real_usdc_priced_trade_is_decoded_in_usdc():
    [event] = decode_trade_events(base58.b58decode(REAL_USDC_TRADE))
    assert event["mint"] == "AmxHq6z7B4svddqfSzHBB9TiCYwBBhhdaarMCY2Lpump"
    assert event["side"] == "buy" and event["sol_amount"] == 0
    assert event["quote"] == "USDC" and event["amount"] == pytest.approx(17.913488)
    assert event["price"] == pytest.approx(4309.913488 / 1_068_540_241.68938)


def test_unknown_quote_currency_is_found_from_the_transaction_balances():
    # A token priced in a currency not listed in advance (9 decimals here).
    new_quote = bytes(range(100, 132))
    body = EVENT_LAYOUT.pack(MINT, 0, 999, True, USER, 1_700_000_000, 0, 1_000_000_000 * 10**6)
    body += b"\x00" * 40 + new_quote + struct.pack("<QQ", 2 * 10**9, 50 * 10**9)  # paid 2, reserves 50
    tx = {"meta": {
        "innerInstructions": [{"instructions": [{"data": base58.b58encode(TRADE_EVENT + body).decode()}]}],
        "postTokenBalances": [{"mint": base58.b58encode(new_quote).decode(), "uiTokenAmount": {"decimals": 9}}],
    }}
    [event] = events_in_transaction(tx)
    assert event["amount"] == 2.0
    assert event["price"] == pytest.approx(50 / 1e9)

"""Fetch a pump.fun token's trades straight from the Solana blockchain.

Uses only standard Solana RPC methods, so it works with a free Helius key or,
more slowly, with Solana's public endpoint and no key at all.

How it works:
  1. Ask for the ids of every transaction that touched the token (cheap: 1,000 per call).
  2. Fetch each transaction in full (1 call each, so this is the slow part).
  3. Inside each one, find pump.fun's "TradeEvent" record and unpack it:
     which token, how much SOL, buy or sell, which wallet.
"""

import base64
import os
import struct
import time

import base58
import pandas as pd
import requests

PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"  # the pump.fun bonding-curve program

# Every TradeEvent record starts with these 8 bytes: an Anchor "event
# discriminator", the first 8 bytes of sha256("event:TradeEvent").
TRADE_EVENT = bytes.fromhex("bddb7fd34ee661ee")

# The first six fields after the discriminator, in order:
# mint (32-byte key), sol_amount (u64), token_amount (u64), is_buy (bool),
# user (32-byte key), timestamp (i64). "<" means little-endian, no padding.
EVENT_LAYOUT = struct.Struct("<32sQQ?32sq")  # 89 bytes


def rpc_url() -> str:
    """Helius if a key is in .env, otherwise the public endpoint."""
    key = os.getenv("HELIUS_API_KEY")
    return f"https://mainnet.helius-rpc.com/?api-key={key}" if key else PUBLIC_RPC


def rpc(url: str, method: str, params: list, retries: int = 6):
    """One JSON-RPC call. If rate-limited (HTTP 429), wait 1, 2, 4... seconds and retry."""
    for attempt in range(retries):
        reply = requests.post(
            url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=30
        )
        if reply.status_code == 429:
            time.sleep(2**attempt)
            continue
        reply.raise_for_status()
        body = reply.json()
        if "error" in body:
            raise RuntimeError(f"{method} failed: {body['error']}")
        return body["result"]
    raise RuntimeError(f"{method}: still rate-limited after {retries} tries")


def list_signatures(url: str, mint: str, max_pages: int = 50) -> list[str]:
    """Ids of every successful transaction that touched the token, oldest first.

    The API only pages from newest to oldest, so reaching a token's first trades
    means paging through its whole history. Tokens with more than
    max_pages x 1,000 transactions are refused rather than left running for ages.
    """
    found, before = [], None
    for _ in range(max_pages):
        options = {"limit": 1000} | ({"before": before} if before else {})
        page = rpc(url, "getSignaturesForAddress", [mint, options])
        found += [s["signature"] for s in page if s["err"] is None]
        if len(page) < 1000:
            return found[::-1]  # the API returns newest first
        before = page[-1]["signature"]  # next page starts after the oldest one seen
    raise ValueError(f"token has over {max_pages * 1000:,} transactions: too large for a free-tier lookup")


def decode_trade_events(raw: bytes) -> list[dict]:
    """Find every TradeEvent in a blob of bytes and unpack its first six fields."""
    events = []
    start = raw.find(TRADE_EVENT)
    while start != -1:
        body = raw[start + 8 : start + 8 + EVENT_LAYOUT.size]
        if len(body) == EVENT_LAYOUT.size:
            mint, sol, _tokens, is_buy, user, _ts = EVENT_LAYOUT.unpack(body)
            events.append({
                "mint": base58.b58encode(mint).decode(),
                "wallet": base58.b58encode(user).decode(),
                "side": "buy" if is_buy else "sell",
                "sol_amount": sol / 1e9,  # lamports to SOL
            })
        start = raw.find(TRADE_EVENT, start + 8)
    return events


def events_in_transaction(tx: dict) -> list[dict]:
    """pump.fun records events as inner instructions; older programs log them instead.

    Check inner instructions first; only fall back to logs if none were found,
    so the same event is never counted twice.
    """
    meta = tx["meta"]
    events = []
    for group in meta.get("innerInstructions") or []:
        for ix in group["instructions"]:
            events += decode_trade_events(base58.b58decode(ix["data"]))
    if not events:
        for line in meta.get("logMessages") or []:
            if line.startswith("Program data: "):
                events += decode_trade_events(base64.b64decode(line[len("Program data: "):]))
    return events


def fetch_token_trades(mint: str, max_transactions: int = 1000, url: str | None = None) -> pd.DataFrame:
    """The token's earliest trades, in the project's trade-table format."""
    url = url or rpc_url()
    signatures = list_signatures(url, mint)[:max_transactions]
    rows = []
    for i, sig in enumerate(signatures):
        tx = rpc(url, "getTransaction", [sig, {"encoding": "json", "maxSupportedTransactionVersion": 1}])
        if tx is None:
            continue
        for event in events_in_transaction(tx):
            if event["mint"] != mint:  # ignore events for other tokens in the same transaction
                continue
            rows.append(event | {
                "slot": tx["slot"],
                "tx_index": len(rows),  # keeps the order we received trades in
                "signature": sig,
                "block_time": tx.get("blockTime"),
            })
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(signatures)} transactions fetched")
    return pd.DataFrame(rows)

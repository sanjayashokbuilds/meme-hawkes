"""Fetch a pump.fun token's trades straight from the Solana blockchain.

Uses only standard Solana RPC methods, so it works with a free Helius key or,
more slowly, with Solana's public endpoint and no key at all.

How it works:
  1. Work out the token's bonding-curve account (an address derived from the
     mint, no network call). Only trades touch it, unlike the mint itself,
     which is also touched by wallet-to-wallet transfers.
  2. Ask for the ids of every transaction on that account (cheap: 1,000 per call).
  3. Fetch each transaction in full (1 call each, so this is the slow part).
  4. Inside each one, find pump.fun's "TradeEvent" record and unpack it:
     which token, how much was paid, buy or sell, which wallet, the curve price.
"""

import base64
import hashlib
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

# The first eight fields after the discriminator, in order:
# mint (32-byte key), sol_amount (u64), token_amount (u64), is_buy (bool),
# user (32-byte key), timestamp (i64), virtual_sol_reserves (u64),
# virtual_token_reserves (u64). "<" means little-endian, no padding.
EVENT_LAYOUT = struct.Struct("<32sQQ?32sqQQ")  # 105 bytes

# Most tokens are priced in SOL. Newer ones can be priced in another "quote"
# token instead (seen: USDC). Their events have zero SOL fields, and the real
# amounts sit after the quote token's address, further along the event:
#   quote_mint (32 bytes), quote_amount (u64), virtual_quote_reserves (u64)
# Confirmed against a real USDC-priced trade: the amounts matched the
# transaction's USDC balance changes exactly.
QUOTE_TOKENS = {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6)}  # mint: (name, decimals)

# Token launches are recorded as a CreateEvent: sha256("event:CreateEvent")[:8].
# Its fields start with three strings (name, symbol, uri), then the mint and
# the bonding-curve addresses.
CREATE_EVENT = bytes.fromhex(hashlib.sha256(b"event:CreateEvent").hexdigest()[:16])


# --- The bonding-curve address -------------------------------------------------
# A "program derived address": sha256 of the seeds, a "bump" byte, the program id
# and a fixed label. Valid only if the result is NOT a point on the ed25519 curve
# (so no private key can exist for it); the bump counts down from 255 until that
# holds. Checked against two real addresses in tests/test_fetch.py.
_P = 2**255 - 19
_D = (-121665 * pow(121666, _P - 2, _P)) % _P


def _on_curve(candidate: bytes) -> bool:
    """Is there an ed25519 point with this y-coordinate? (Is x^2 a square mod p?)"""
    y = (int.from_bytes(candidate, "little") & ((1 << 255) - 1)) % _P
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    return x2 == 0 or pow(x2, (_P - 1) // 2, _P) == 1


def program_address(seeds: list[bytes], program: str) -> str:
    """Solana's find_program_address, in plain Python."""
    program_bytes = base58.b58decode(program)
    for bump in range(255, -1, -1):
        h = hashlib.sha256(b"".join(seeds) + bytes([bump]) + program_bytes + b"ProgramDerivedAddress").digest()
        if not _on_curve(h):
            return base58.b58encode(h).decode()
    raise ValueError("no valid program address")


def bonding_curve_address(mint: str) -> str:
    """The account holding a token's bonding curve: seeds 'bonding-curve' + mint."""
    return program_address([b"bonding-curve", base58.b58decode(mint)], PUMP_PROGRAM)


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


def list_signatures(url: str, address: str, max_pages: int = 50) -> list[dict]:
    """Every successful transaction that touched an account, oldest first.

    Each item is a dict with at least 'signature' and 'blockTime' (Unix seconds).

    The API only pages from newest to oldest, so reaching the first transactions
    means paging through the whole history. Tokens with more than
    max_pages x 1,000 transactions are refused rather than left running for ages.
    """
    found, before = [], None
    for _ in range(max_pages):
        options = {"limit": 1000} | ({"before": before} if before else {})
        page = rpc(url, "getSignaturesForAddress", [address, options])
        found += [s for s in page if s["err"] is None]
        if len(page) < 1000:
            return found[::-1]  # the API returns newest first
        before = page[-1]["signature"]  # next page starts after the oldest one seen
    raise ValueError(f"over {max_pages * 1000:,} transactions: too large for a free-tier lookup")


def decode_trade_events(raw: bytes, quotes: dict = QUOTE_TOKENS) -> list[dict]:
    """Find every TradeEvent in a blob of bytes and unpack it.

    quotes: candidate quote tokens, {mint: (name, decimals)}, for tokens not priced in SOL.
    """
    events = []
    start = raw.find(TRADE_EVENT)
    while start != -1:
        body = raw[start + 8 :]
        if len(body) >= EVENT_LAYOUT.size:
            mint, sol, _tokens, is_buy, user, _ts, v_sol, v_tok = EVENT_LAYOUT.unpack_from(body)
            quote, amount, price = "SOL", sol / 1e9, float("nan")
            if v_sol and v_tok:
                # Curve price right after this trade, in SOL per token
                # (SOL has 9 decimals, pump.fun tokens 6).
                price = (v_sol / 1e9) / (v_tok / 1e6)
            else:
                for quote_mint, (name, decimals) in quotes.items():
                    if base58.b58decode(quote_mint) == mint:
                        continue  # the token itself is never its own quote
                    q = body.find(base58.b58decode(quote_mint), EVENT_LAYOUT.size)
                    if q != -1 and len(body) >= q + 48:
                        q_amount, v_quote = struct.unpack_from("<QQ", body, q + 32)
                        quote, amount = name, q_amount / 10**decimals
                        price = (v_quote / 10**decimals) / (v_tok / 1e6) if v_tok else float("nan")
                        break
            events.append({
                "mint": base58.b58encode(mint).decode(),
                "wallet": base58.b58encode(user).decode(),
                "side": "buy" if is_buy else "sell",
                "sol_amount": sol / 1e9,   # lamports to SOL (0 for tokens priced in another quote)
                "quote": quote,            # what the token is priced in
                "amount": amount,          # paid or received, in the quote token
                "price": price,            # curve price after the trade, quote per token
            })
        start = raw.find(TRADE_EVENT, start + 8)
    return events


def decode_create_events(raw: bytes) -> list[dict]:
    """Find every CreateEvent in a blob of bytes: the mint it created and its bonding curve."""
    found = []
    start = raw.find(CREATE_EVENT)
    while start != -1:
        pos = start + 8
        try:
            for _ in range(3):  # skip name, symbol, uri: each is a 4-byte length, then text
                (length,) = struct.unpack_from("<I", raw, pos)
                if length > 500:  # not a real string: this wasn't an event after all
                    raise ValueError
                pos += 4 + length
            if pos + 64 <= len(raw):
                found.append({"mint": base58.b58encode(raw[pos : pos + 32]).decode(),
                              "bonding_curve": base58.b58encode(raw[pos + 32 : pos + 64]).decode()})
        except (struct.error, ValueError):
            pass
        start = raw.find(CREATE_EVENT, start + 8)
    return found


def _decode(tx: dict, decoder) -> list:
    """pump.fun records events as inner instructions; older programs log them instead.

    Check inner instructions first; only fall back to logs if none were found,
    so the same event is never counted twice.
    """
    meta = tx["meta"]
    found = []
    for group in meta.get("innerInstructions") or []:
        for ix in group["instructions"]:
            found += decoder(base58.b58decode(ix["data"]))
    if not found:
        for line in meta.get("logMessages") or []:
            if line.startswith("Program data: "):
                found += decoder(base64.b64decode(line[len("Program data: "):]))
    return found


def events_in_transaction(tx: dict) -> list[dict]:
    """Every pump.fun trade recorded in a transaction.

    Tokens not priced in SOL carry their quote token's address inside the event.
    Every token whose balance changed in the transaction (with its decimals) is a
    candidate, so a new quote currency is picked up without being listed in advance.
    """
    meta = tx["meta"]
    quotes = dict(QUOTE_TOKENS)
    for b in (meta.get("preTokenBalances") or []) + (meta.get("postTokenBalances") or []):
        if b.get("mint") and b["mint"] not in quotes:
            quotes[b["mint"]] = (b["mint"][:4], b["uiTokenAmount"]["decimals"])
    return _decode(tx, lambda raw: decode_trade_events(raw, quotes))


def launches_in_transaction(tx: dict) -> list[dict]:
    """Tokens launched in a transaction: [{'mint': ..., 'bonding_curve': ...}]."""
    return _decode(tx, decode_create_events)


def fetch_token_trades(
    mint: str,
    max_transactions: int = 1000,
    first_seconds: float | None = None,
    signatures: list[dict] | None = None,
    url: str | None = None,
) -> pd.DataFrame:
    """The token's earliest trades, in the project's trade-table format.

    first_seconds  only keep transactions within this long of the first one
    signatures     pass the output of list_signatures if you already have it

    Lists transactions on the token's bonding curve, not the mint: busy tokens
    get flooded with wallet-to-wallet transfers that touch the mint but aren't trades.
    """
    url = url or rpc_url()
    signatures = signatures if signatures is not None else list_signatures(url, bonding_curve_address(mint))
    if first_seconds is not None and signatures:
        start = signatures[0]["blockTime"]
        signatures = [s for s in signatures if s["blockTime"] is not None and s["blockTime"] - start <= first_seconds]
    signatures = [s["signature"] for s in signatures[:max_transactions]]
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

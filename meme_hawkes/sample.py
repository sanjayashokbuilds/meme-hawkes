"""Choose the token sample by launch time, so it isn't biased towards survivors.

PRE-REGISTERED sampling rule:
  1. Population: every pump.fun token launched between 6 and 2 hours before
     the pull (so each token's first hour is complete).
  2. Shuffle the launches with a fixed seed (reproducible random order).
  3. Go down the shuffled list and keep a token if it had at least 100
     successful bonding-curve transactions (i.e. trades) in its first hour,
     enough events to fit a model.
     AMENDMENT 1 (17 Oct 2026, before any model was fitted to real data): the
     original rule counted every transaction touching the mint. The first pull
     showed busy tokens' mints are flooded with wallet-to-wallet transfers that
     aren't trades (one token: 2,087 transactions, 11 trades), so the count
     now uses the bonding-curve account, which only trades touch.
  4. Stop at 40 tokens. Every token checked, kept or not, is logged with a reason.

Launches are found through pump.fun's mint-authority account, which signs every
token creation. That address isn't in the official docs we checked, so
choose_tokens verifies it: if the transactions it returns contain no launch
records, it stops with an error instead of quietly sampling the wrong thing.
"""

import random
import time

from .fetch import bonding_curve_address, launches_in_transaction, list_signatures, rpc

PUMP_MINT_AUTHORITY = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"
TX_OPTIONS = {"encoding": "json", "maxSupportedTransactionVersion": 1}


def launch_signatures(url: str, start: int, end: int) -> list[str]:
    """Signatures of mint-authority transactions with block time in [start, end]."""
    found, before = [], None
    while True:
        options = {"limit": 1000} | ({"before": before} if before else {})
        page = rpc(url, "getSignaturesForAddress", [PUMP_MINT_AUTHORITY, options])
        if not page:
            return found
        found += [s["signature"] for s in page
                  if s["err"] is None and s["blockTime"] and start <= s["blockTime"] <= end]
        oldest = page[-1]["blockTime"]
        if oldest is not None and oldest < start:
            return found
        before = page[-1]["signature"]


def choose_tokens(url: str, n_tokens: int = 40, min_tx: int = 100, seed: int = 2026,
                  hours_from: float = 6, hours_to: float = 2, max_checked: int = 800):
    """Apply the sampling rule. Returns (kept tokens, log of every token checked)."""
    now = int(time.time())
    sigs = launch_signatures(url, now - int(hours_from * 3600), now - int(hours_to * 3600))
    random.Random(seed).shuffle(sigs)
    print(f"{len(sigs)} launch-window transactions found; checking in random order")

    kept, log, verified = [], [], False
    for i, sig in enumerate(sigs[:max_checked]):
        tx = rpc(url, "getTransaction", [sig, TX_OPTIONS])
        launches = launches_in_transaction(tx) if tx else []
        if launches:
            verified = True
        elif i >= 19 and not verified:
            raise RuntimeError("No launch records in the first 20 mint-authority transactions: "
                               "the address is probably wrong. Tell Claude.")
        for launch_record in launches:
            mint = launch_record["mint"]
            # Self-check: our derived bonding-curve address must match the one in the launch record.
            if bonding_curve_address(mint) != launch_record["bonding_curve"]:
                raise RuntimeError(f"Bonding-curve address mismatch for {mint}. Tell Claude.")
            try:
                history = list_signatures(url, launch_record["bonding_curve"])
            except ValueError:
                log.append({"mint": mint, "kept": False, "reason": "over 50,000 transactions"})
                continue
            if not history:
                log.append({"mint": mint, "kept": False, "reason": "no trades"})
                continue
            launch = history[0]["blockTime"]
            first_hour = [s for s in history if s["blockTime"] and s["blockTime"] - launch <= 3600]
            ok = len(first_hour) >= min_tx
            log.append({"mint": mint, "kept": ok, "first_hour_tx": len(first_hour), "launch_time": launch,
                        "reason": "" if ok else f"under {min_tx} transactions in first hour"})
            if ok:
                kept.append({"mint": mint, "signatures": first_hour})
                print(f"  kept {len(kept)}/{n_tokens} (checked {len(log)})")
            if len(kept) >= n_tokens:
                return kept, log
    return kept, log

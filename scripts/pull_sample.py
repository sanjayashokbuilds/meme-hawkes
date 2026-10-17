"""Pull the research sample, then build the processed dataset.

Usage (from the repo root):
    python scripts/pull_sample.py             # choose tokens, fetch them, build dataset
    python scripts/pull_sample.py --refetch   # re-fetch only tokens that are missing or have no
                                              # usable prices (same sample), then build
    python scripts/pull_sample.py --build     # only rebuild the dataset from what's downloaded

Safe to stop (Ctrl-C) and re-run: tokens already downloaded are skipped.
Takes roughly an hour on the Helius free tier, so leave it running in its own
terminal window while we work on the model.

Writes:
  data/raw/sample_log.csv         every token checked, kept or not, and why
  data/raw/<mint>.csv             each kept token's trades (raw wallets; not committed)
  data/processed/trades.csv       all trades, cleaned, grouped, wallets hashed (committed)
  data/processed/labels.csv       one row per token: pump-and-dump labels (committed)
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, ".")
from meme_hawkes.clean import anonymise_wallets, clean_trades  # noqa: E402
from meme_hawkes.fetch import fetch_token_trades, rpc_url  # noqa: E402
from meme_hawkes.grouping import label_groups  # noqa: E402
from meme_hawkes.labels import label_sample  # noqa: E402
from meme_hawkes.sample import choose_tokens  # noqa: E402

RAW, PROCESSED = Path("data/raw"), Path("data/processed")


def pull():
    url = rpc_url()
    kept, log = choose_tokens(url)
    pd.DataFrame(log).to_csv(RAW / "sample_log.csv", index=False)
    print(f"\nSample: {len(kept)} tokens. Fetching their first-hour trades (max 1,000 transactions each).")
    for i, token in enumerate(kept, 1):
        path = RAW / f"{token['mint']}.csv"
        if path.exists():
            continue
        print(f"[{i}/{len(kept)}] {token['mint']}")
        trades = fetch_token_trades(token["mint"], max_transactions=1000, signatures=token["signatures"], url=url)
        trades.to_csv(path, index=False)


def kept_mints() -> list[str]:
    log = pd.read_csv(RAW / "sample_log.csv")
    return list(log.loc[log["kept"], "mint"])


def refetch():
    """Re-download tokens that are missing or have no usable prices, keeping the same sample."""
    url = rpc_url()
    for mint in kept_mints():
        path = RAW / f"{mint}.csv"
        if path.exists() and pd.read_csv(path)["price"].notna().any():
            continue
        print(f"re-fetching {mint}")
        fetch_token_trades(mint, max_transactions=1000, first_seconds=3600, url=url).to_csv(path, index=False)


def build():
    salt = os.getenv("ANONYMISE_SALT")
    if not salt:
        sys.exit("Set ANONYMISE_SALT in .env first (any long random string).")
    files = [RAW / f"{m}.csv" for m in kept_mints() if (RAW / f"{m}.csv").exists()]
    trades = label_groups(clean_trades(pd.concat([pd.read_csv(f) for f in files])))
    labels = label_sample(trades)

    # Per-token check, printed every time so problems are visible straight away.
    check = trades.groupby("mint").agg(trades=("price", "size"), wallets=("wallet", "nunique"),
                                       priced=("price", lambda p: int(p.notna().sum())), quote=("quote", "first"))
    check.index = check.index.str[:6]
    print(check.sort_values("trades").to_string())

    labelled = labels[labels["pump_and_dump"].notna()]
    unpriced = labels.loc[labels["pump_and_dump"].isna(), "mint"].str[:6].tolist()
    anonymise_wallets(trades, salt).drop(columns=["signature"]).to_csv(PROCESSED / "trades.csv", index=False)
    labels.to_csv(PROCESSED / "labels.csv", index=False)
    print(f"\n{len(files)} tokens, {len(trades):,} trades. Quotes: {check['quote'].value_counts().to_dict()}")
    print(f"Pump-and-dumps: {labelled['pump_and_dump'].astype(bool).sum()} of {len(labelled)} labelled tokens "
          f"(primary rule), {labelled['pump_and_dump_mm'].astype(bool).sum()} (looser rule).")
    if unpriced:
        print(f"WARNING: no usable prices for {unpriced}: run with --refetch, and tell Claude if it persists.")


if __name__ == "__main__":
    load_dotenv(".env")
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if "--refetch" in sys.argv:
        refetch()
    elif "--build" not in sys.argv:
        pull()
    build()

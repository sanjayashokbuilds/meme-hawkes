"""Pull the research sample, then build the processed dataset.

Usage (from the repo root):
    python scripts/pull_sample.py            # choose tokens, fetch them, build dataset
    python scripts/pull_sample.py --build    # only rebuild the dataset from what's downloaded

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


def build():
    salt = os.getenv("ANONYMISE_SALT")
    if not salt:
        sys.exit("Set ANONYMISE_SALT in .env first (any long random string).")
    log = pd.read_csv(RAW / "sample_log.csv")
    files = [RAW / f"{m}.csv" for m in log.loc[log["kept"], "mint"] if (RAW / f"{m}.csv").exists()]
    trades = label_groups(clean_trades(pd.concat([pd.read_csv(f) for f in files])))
    labels = label_sample(trades)
    anonymise_wallets(trades, salt).drop(columns=["signature"]).to_csv(PROCESSED / "trades.csv", index=False)
    labels.to_csv(PROCESSED / "labels.csv", index=False)
    print(f"{len(files)} tokens, {len(trades):,} trades. "
          f"Pump-and-dumps: {labels['pump_and_dump'].sum()} (primary rule), "
          f"{labels['pump_and_dump_mm'].sum()} (looser rule).")


if __name__ == "__main__":
    load_dotenv()
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if "--build" not in sys.argv:
        pull()
    build()

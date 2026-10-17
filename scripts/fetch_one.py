"""Smoke test on real data: fetch one token's earliest trades and print sanity checks.

Usage (from the repo root, with the virtual environment active):
    python scripts/fetch_one.py <token mint address> [number of transactions]
"""

import sys

from dotenv import load_dotenv

sys.path.insert(0, ".")  # so the meme_hawkes package can be imported from the repo root
from meme_hawkes.clean import clean_trades  # noqa: E402
from meme_hawkes.fetch import fetch_token_trades, rpc_url  # noqa: E402
from meme_hawkes.grouping import label_groups  # noqa: E402

load_dotenv()
mint = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 200

print("Endpoint:", "Helius" if "helius" in rpc_url() else "public Solana RPC")
raw = fetch_token_trades(mint, max_transactions=n)
if raw.empty:
    sys.exit("No trades decoded. Either the address is wrong or the event format has changed: tell Claude.")

df = label_groups(clean_trades(raw))
print(f"\n{len(df)} trades from {df['wallet'].nunique()} wallets over {df['t'].max():.0f} seconds")
print(df["event_type"].value_counts().to_string())
quote = df["quote"].iloc[0]
print(f"\nPriced in {quote}. Paid per trade: median", round(df["amount"].median(), 4), "| max", round(df["amount"].max(), 2))

# Clock check: the calibrated slot clock should now agree with real block times (whole seconds).
elapsed_real = df["block_time"].max() - df["block_time"].min()
print(f"Measured slot length: {df['seconds_per_slot'].iloc[0]:.3f} s")
print(f"Slot clock says {df['t'].max():.0f} s; block times say {elapsed_real} s")
print("\nFirst five trades (wallets shortened):")
print(df.assign(wallet=df["wallet"].str[:6])[["slot", "t", "wallet", "side", "amount", "price", "group"]].head().to_string(index=False))

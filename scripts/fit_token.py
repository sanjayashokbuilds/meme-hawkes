"""Fit the univariate Hawkes model to one real token and check the fit.

Usage (from the repo root): python scripts/fit_token.py <token mint address>

Uses the token's first hour (at most 1,000 transactions), all trades pooled
into one stream. Downloads once and caches to data/raw/<mint>.csv.
Ties within a slot are spread randomly, so the fit is repeated with 5 different
random spreads: if the branching ratio barely moves, the tie handling isn't
driving the result.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, ".")
from meme_hawkes import hawkes  # noqa: E402
from meme_hawkes.clean import clean_trades, spread_ties  # noqa: E402
from meme_hawkes.fetch import fetch_token_trades  # noqa: E402
from meme_hawkes.plots import intensity_plot, qq_plot  # noqa: E402

load_dotenv()
mint = sys.argv[1]
cache = Path(f"data/raw/{mint}.csv")
if cache.exists():
    raw = pd.read_csv(cache)
else:
    raw = fetch_token_trades(mint, max_transactions=1000, first_seconds=3600)
    raw.to_csv(cache, index=False)

df = clean_trades(raw)
fits = []
for seed in range(5):
    times = np.sort(spread_ties(df, np.random.default_rng(seed)).to_numpy())
    T = times[-1] + df["seconds_per_slot"].iloc[0]  # observation ends just after the last trade
    fits.append((times, T, hawkes.fit(times, T)))

ns = [f["n"] for _, _, f in fits]
times, T, best = fits[0]
p = hawkes.goodness_of_fit(times, best)
print(f"{len(times)} trades over {T:.0f} s")
print(f"mu = {best['mu']:.4f}/s   alpha = {best['alpha']:.3f}   beta = {best['beta']:.3f}/s "
      f"(memory ~{1 / best['beta']:.1f} s)")
print(f"branching ratio n = {best['n']:.3f}   (range over 5 tie spreads: {min(ns):.3f} to {max(ns):.3f})")
print(f"goodness of fit: KS p = {p:.3f}  ->  {'fits acceptably' if p > 0.05 else 'model REJECTED for this token'}")

fig, (left, right) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [2, 1]})
grid = np.linspace(0, T, 3000)
intensity_plot(left, grid, hawkes.intensity(grid, times, best["mu"], best["alpha"], best["beta"]), times,
               f"Fitted intensity, token {mint[:6]}… (n = {best['n']:.2f})")
qq_plot(right, hawkes.rescaled_gaps(times, best["mu"], best["alpha"], best["beta"]), f"Fit check (KS p = {p:.2f})")
fig.tight_layout()
out = f"figures/token_{mint[:6]}.png"
fig.savefig(out, dpi=160)
print(f"Figure saved to {out}")

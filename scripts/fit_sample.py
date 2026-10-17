"""Stage 4: fit the Hawkes models to every eligible token and compare pump-and-dumps with the rest.

Usage (from the repo root): python scripts/fit_sample.py
Reads data/processed/trades.csv and labels.csv (from pull_sample.py).
Writes data/processed/excitation.csv, figures/excitation_by_label.png and docs/RESULTS.md.
Takes roughly 10-15 minutes.

For each token with at least 100 trades (decision #24):
  * univariate branching ratio n (all trades pooled)
  * two-type model, early-slot wallets vs ordinary wallets: the branching matrix,
    especially early -> ordinary, and its spectral radius
  * each fit repeated over 3 random tie spreads; the median is reported
  * robustness: early defined by 2 or 10 slots instead of 5, and with heavy
    wallets (>=10% of a token's trades and >=20 trades) removed (decision #25)

IMPORTANT: these use each token's whole first hour, including trades after any
dump. They describe how excitation differs between token types; they are not a
prediction test. Stage 5 does the prediction test using only past data.
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, ".")
from meme_hawkes import hawkes  # noqa: E402
from meme_hawkes import multivariate as mv  # noqa: E402
from meme_hawkes.clean import spread_ties  # noqa: E402
from meme_hawkes.grouping import label_groups  # noqa: E402
from meme_hawkes.plots import BLUE, INK_SOFT, ORANGE  # noqa: E402

MIN_TRADES, MIN_PER_TYPE, SEEDS = 100, 10, (0, 1, 2)
NULL_95 = 0.121  # 95th percentile of early->ordinary estimates under no effect (docs/VALIDATION_MULTIVARIATE.md)


def two_type(df: pd.DataFrame, seed: int) -> dict | None:
    """Fit early (type 0) vs ordinary (type 1). None if either type has too few trades."""
    types = (df["group"] == "ordinary").to_numpy().astype(int)
    if min(np.bincount(types, minlength=2)) < MIN_PER_TYPE:
        return None
    times = spread_ties(df, np.random.default_rng(seed)).to_numpy()
    order = np.argsort(times, kind="stable")
    times, types = times[order], types[order]
    T = times[-1] + df["seconds_per_slot"].iloc[0]
    est = mv.fit(times, types, T)
    est["ks"] = mv.goodness_of_fit(times, types, est)
    return est


def heavy_wallets_removed(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["wallet"].value_counts()
    heavy = counts[(counts >= 20) & (counts >= 0.1 * len(df))].index
    return df[~df["wallet"].isin(heavy)]


def analyse_token(g: pd.DataFrame) -> dict:
    row = {"mint": g["mint"].iloc[0], "trades": len(g), "wallets": g["wallet"].nunique(),
           "early_share": float((g["group"] == "early").mean())}
    uni = []
    for seed in SEEDS:
        times = np.sort(spread_ties(g, np.random.default_rng(seed)).to_numpy())
        fit = hawkes.fit(times, times[-1] + g["seconds_per_slot"].iloc[0])
        uni.append((fit["n"], hawkes.goodness_of_fit(times, fit)))
    row["n"] = float(np.median([u[0] for u in uni]))
    row["n_ks_p"] = uni[0][1]

    fits = [f for f in (two_type(g, s) for s in SEEDS) if f is not None]
    if not fits:
        row["skipped_two_type"] = f"fewer than {MIN_PER_TYPE} early or ordinary trades"
        return row
    for name, (i, j) in {"early_to_ordinary": (1, 0), "ordinary_to_ordinary": (1, 1),
                         "early_to_early": (0, 0), "ordinary_to_early": (0, 1)}.items():
        row[name] = float(np.median([f["branching"][i, j] for f in fits]))
    row["spectral_radius"] = float(np.median([f["spectral_radius"] for f in fits]))
    row["ks_p_early"], row["ks_p_ordinary"] = fits[0]["ks"]

    # Robustness checks (one tie spread each)
    for slots in (2, 10):
        alt = two_type(label_groups(g.drop(columns=["group", "event_type"]), first_slots=slots), 0)
        row[f"e2o_slots{slots}"] = alt["branching"][1, 0] if alt else np.nan
    trimmed = heavy_wallets_removed(g)
    alt = two_type(trimmed, 0) if len(trimmed) >= MIN_TRADES else None
    row["e2o_no_heavy"] = alt["branching"][1, 0] if alt else np.nan
    return row


def compare(results: pd.DataFrame, column: str) -> str:
    a = results.loc[results["pump_and_dump"] == True, column].dropna()   # noqa: E712
    b = results.loc[results["pump_and_dump"] == False, column].dropna()  # noqa: E712
    p = stats.mannwhitneyu(a, b).pvalue if len(a) >= 3 and len(b) >= 3 else np.nan
    return f"| {column} | {len(a)} | {a.median():.3f} | {len(b)} | {b.median():.3f} | {p:.3f} |"


def main():
    trades = pd.read_csv("data/processed/trades.csv")
    labels = pd.read_csv("data/processed/labels.csv")
    eligible = trades.groupby("mint").filter(lambda g: len(g) >= MIN_TRADES)
    mints = eligible["mint"].unique()
    print(f"{len(mints)} of {trades['mint'].nunique()} tokens have >= {MIN_TRADES} trades")

    rows = []
    for k, (mint, g) in enumerate(eligible.sort_values(["mint", "slot", "tx_index"]).groupby("mint"), 1):
        print(f"[{k}/{len(mints)}] {mint[:6]} ({len(g)} trades)")
        rows.append(analyse_token(g.reset_index(drop=True)))
    results = pd.DataFrame(rows).merge(labels[["mint", "pump_and_dump", "pump_and_dump_mm"]], on="mint")
    results.to_csv("data/processed/excitation.csv", index=False)

    two = results.dropna(subset=["early_to_ordinary"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    jitter = np.random.default_rng(0)
    for ax, (col, title) in zip(axes, [("n", "Univariate branching ratio n"),
                                       ("early_to_ordinary", "Early → ordinary branching")]):
        for x, (flag, name) in enumerate([(False, "No pump-and-dump"), (True, "Pump-and-dump")]):
            v = results.loc[results["pump_and_dump"] == flag, col].dropna()
            ax.plot(x + jitter.uniform(-0.12, 0.12, len(v)), v, "o", ms=6, color=BLUE, alpha=0.7)
            if len(v):
                ax.plot([x - 0.25, x + 0.25], [v.median()] * 2, color=ORANGE, lw=2.5)
        if col == "early_to_ordinary":
            ax.axhline(NULL_95, color=INK_SOFT, ls="--", lw=1)
            ax.text(1.45, NULL_95, " noise bar", va="bottom", ha="right", fontsize=9, color=INK_SOFT)
        ax.set_xticks([0, 1], ["No pump-and-dump", "Pump-and-dump"])
        ax.set(title=title, xlim=(-0.5, 1.5))
    fig.text(0.01, 0.01, "Each dot is one token; orange lines are medians.", fontsize=9, color=INK_SOFT)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig("figures/excitation_by_label.png", dpi=160)

    fitted_ok = (two[["ks_p_early", "ks_p_ordinary"]].min(axis=1) > 0.05).mean() if len(two) else np.nan
    lines = [
        "# Results\n",
        "## Stage 4: excitation by token type (descriptive)\n",
        f"Generated by `scripts/fit_sample.py`. {len(results)} tokens with at least {MIN_TRADES} trades; "
        f"{len(two)} had enough early *and* ordinary trades for the two-type model.\n",
        "**These numbers use each token's whole first hour, including trades after any dump, so they "
        "describe differences between token types. They are not evidence of prediction (that's Stage 5).**\n",
        "| Measure | Pump-and-dump tokens | Median | Other tokens | Median | Mann-Whitney p |",
        "|---|---|---|---|---|---|",
        compare(results, "n"), compare(results, "early_to_ordinary"),
        compare(results, "ordinary_to_ordinary"), compare(results, "spectral_radius"),
        "",
        f"- Tokens whose early→ordinary estimate clears the noise bar ({NULL_95}): "
        f"{(two['early_to_ordinary'] > NULL_95).sum()} of {len(two)}.",
        f"- Two-type model passes the fit check (KS p > 0.05 for both types): {fitted_ok:.0%} of tokens.",
        f"- Univariate model passes the fit check: {(results['n_ks_p'] > 0.05).mean():.0%} of tokens.",
        "- Robustness (median early→ordinary): "
        f"5 slots {two['early_to_ordinary'].median():.3f}, 2 slots {results['e2o_slots2'].median():.3f}, "
        f"10 slots {results['e2o_slots10'].median():.3f}, heavy wallets removed {results['e2o_no_heavy'].median():.3f}.",
        "\n![Excitation by token type](../figures/excitation_by_label.png)\n",
    ]
    open("docs/RESULTS.md", "w").write("\n".join(lines))
    print("\n".join(lines[4:13]))
    print("\nWrote data/processed/excitation.csv, figures/excitation_by_label.png, docs/RESULTS.md")


if __name__ == "__main__":
    main()

"""Stage 5b: refit every eligible token with a fading launch-time background.

Usage (from the repo root): python scripts/fit_fading.py
Reads data/processed/trades.csv, labels.csv and excitation.csv (Stage 4).
Writes data/processed/fading.csv, figures/fading_vs_constant.png and the
Stage 5b section of docs/RESULTS.md. Takes roughly 10-15 minutes.

Question: is the near-critical n of Stage 4 real, or the constant-background
artefact the simulation in docs/VALIDATION_FADING.md shows can happen?
Models compared with AIC (= 2 x parameters - 2 x log-likelihood; lower is better),
which charges the fading model for its two extra parameters.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, ".")
from meme_hawkes import fading, hawkes  # noqa: E402
from meme_hawkes.clean import spread_ties  # noqa: E402
from meme_hawkes.plots import BLUE, INK_SOFT, ORANGE  # noqa: E402
from meme_hawkes.report import write_section  # noqa: E402

MIN_TRADES, MIN_PER_TYPE = 100, 10


def analyse(g: pd.DataFrame) -> dict:
    times = spread_ties(g, np.random.default_rng(0)).to_numpy()
    order = np.argsort(times, kind="stable")
    times = times[order]
    T = times[-1] + g["seconds_per_slot"].iloc[0]
    const, fade = hawkes.fit(times, T), fading.fit(times, T)
    row = {"mint": g["mint"].iloc[0], "trades": len(g),
           "n_constant": const["n"], "n_fading": fade["n"],
           "fit_ok_constant": hawkes.goodness_of_fit(times, const) > 0.05,
           "fit_ok_fading": fading.goodness_of_fit(times, fade) > 0.05,
           "aic_constant": 2 * 3 - 2 * const["log_likelihood"],
           "aic_fading": 2 * 5 - 2 * fade["log_likelihood"],
           "burst_half_life_s": np.log(2) / fade["gamma"]}
    types = (g["group"].to_numpy()[order] == "ordinary").astype(int)
    if min(np.bincount(types, minlength=2)) >= MIN_PER_TYPE:
        two = fading.fit_2(times, types, T)
        row["early_to_ordinary_fading"] = two["branching"][1, 0]
        row["fit_ok_two_type_fading"] = min(fading.goodness_of_fit_2(times, types, two)) > 0.05
    return row


def main():
    trades = pd.read_csv("data/processed/trades.csv")
    labels = pd.read_csv("data/processed/labels.csv")
    stage4 = pd.read_csv("data/processed/excitation.csv")[["mint", "early_to_ordinary", "ks_p_early", "ks_p_ordinary"]]
    eligible = trades.groupby("mint").filter(lambda g: len(g) >= MIN_TRADES)

    saved = Path("data/processed/fading.csv")
    if saved.exists() and "--recompute" not in sys.argv:
        print("Using saved fits (run with --recompute to refit)")
        report(pd.read_csv(saved))
        return
    partial = Path("data/processed/fading_partial.csv")
    rows = pd.read_csv(partial).to_dict("records") if partial.exists() else []
    done = {r["mint"] for r in rows}
    groups = list(eligible.sort_values(["mint", "slot", "tx_index"]).groupby("mint"))
    for k, (mint, g) in enumerate(groups, 1):
        if mint in done:
            continue
        print(f"[{k}/{len(groups)}] {mint[:6]} ({len(g)} trades)")
        try:
            rows.append(analyse(g.reset_index(drop=True)))
        except Exception as err:
            print(f"  failed: {err}")
            rows.append({"mint": mint, "trades": len(g), "error": str(err)[:200]})
        pd.DataFrame(rows).to_csv(partial, index=False)

    res = pd.DataFrame(rows).merge(labels[["mint", "pump_and_dump"]], on="mint").merge(stage4, on="mint", how="left")
    res.to_csv(saved, index=False)
    partial.unlink()
    report(res)


def compare(ok: pd.DataFrame, column: str) -> str:
    pd_mask = ok["pump_and_dump"].astype(str) == "True"
    a, b = ok.loc[pd_mask, column].dropna(), ok.loc[~pd_mask, column].dropna()
    p = stats.mannwhitneyu(a, b).pvalue if len(a) >= 3 and len(b) >= 3 else np.nan
    return f"| {column} | {len(a)} | {a.median():.3f} | {len(b)} | {b.median():.3f} | {p:.3f} |"


def report(res: pd.DataFrame):
    ok = res.dropna(subset=["n_fading"])
    prefers_fading = (ok["aic_fading"] < ok["aic_constant"]).mean()
    drop = ok["n_constant"] - ok["n_fading"]
    wilcoxon_p = stats.wilcoxon(ok["n_constant"], ok["n_fading"]).pvalue

    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 4))
    for flag, colour, name in [(True, BLUE, "Pump-and-dump"), (False, ORANGE, "Other")]:
        s = ok[ok["pump_and_dump"].astype(str) == str(flag)]
        left.plot(s["n_constant"], s["n_fading"], "o", ms=7, color=colour, alpha=0.8, label=name)
    left.plot([0, 1], [0, 1], color=INK_SOFT, ls="--", lw=1, label="Same estimate")
    left.set(title="Branching ratio: constant vs fading background", xlabel="n, constant background (Stage 4)",
             ylabel="n, fading background (Stage 5b)", xlim=(0, 1.02), ylim=(0, 1.02))
    left.legend(fontsize=8, frameon=False, loc="upper left")
    shares = [ok["fit_ok_constant"].mean(), ok["fit_ok_fading"].mean()]
    right.bar([0, 1], shares, color=[INK_SOFT, BLUE], width=0.55)
    for x, v in enumerate(shares):
        right.text(x, v, f"{v:.0%}", ha="center", va="bottom", fontsize=10, color=INK_SOFT)
    right.set_xticks([0, 1], ["Constant background", "Fading background"])
    right.set(title="Tokens passing the fit check", ylabel="Share of tokens", ylim=(0, 1))
    fig.tight_layout()
    fig.savefig("figures/fading_vs_constant.png", dpi=160)

    two = ok.dropna(subset=["early_to_ordinary_fading"])
    body = "\n".join([
        f"Generated by `scripts/fit_fading.py`. {len(ok)} tokens refitted with a launch-time background that fades, "
        "μ(t) = μ₀ + μ₁·e^(−γt). Simulation shows a fading burst can make the constant model nearly double n "
        "([validation](VALIDATION_FADING.md)).",
        "",
        "| | Constant background | Fading background |",
        "|---|---|---|",
        f"| Median branching ratio n | {ok['n_constant'].median():.3f} | {ok['n_fading'].median():.3f} |",
        f"| Tokens passing the fit check | {ok['fit_ok_constant'].mean():.0%} | {ok['fit_ok_fading'].mean():.0%} |",
        f"| Two-type model passing the fit check | {((two['ks_p_early'] > 0.05) & (two['ks_p_ordinary'] > 0.05)).mean():.0%} "
        f"| {two['fit_ok_two_type_fading'].astype(bool).mean():.0%} |",
        f"| Median early→ordinary branching | {two['early_to_ordinary'].median():.3f} | {two['early_to_ordinary_fading'].median():.3f} |",
        "",
        f"- The fading model is preferred by AIC for {prefers_fading:.0%} of tokens.",
        f"- n falls by a median of {drop.median():.3f} when the launch burst is modelled "
        f"(Wilcoxon signed-rank p = {wilcoxon_p:.2g}).",
        f"- Median launch-burst half-life: {ok['burst_half_life_s'].median():.0f} s.",
        "",
        "**Pump-and-dump tokens vs the rest, under the fading model:**",
        "",
        "| Measure | Pump-and-dump tokens | Median | Other tokens | Median | Mann-Whitney p |",
        "|---|---|---|---|---|---|",
        compare(ok, "n_fading"), compare(ok, "early_to_ordinary_fading"), compare(ok, "burst_half_life_s"),
        "",
        "Caveat: the noise bar for early→ordinary (0.121) was calibrated for the constant-background model; "
        "the fading model has more parameters, so its bar for a single token is likely higher.",
        "",
        "![Constant vs fading background](../figures/fading_vs_constant.png)",
    ])
    write_section("## Stage 5b: launch-and-fade background", body)
    print(body)


if __name__ == "__main__":
    main()

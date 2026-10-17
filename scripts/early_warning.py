"""Stage 5: does excitation warn of a dump before it happens, better than simple baselines?

Usage (from the repo root): python scripts/early_warning.py
Reads data/processed/trades.csv and labels.csv.
Writes data/processed/signals.csv, figures/early_warning.png and the Stage 5
section of docs/RESULTS.md. Design fixed beforehand: docs/DECISIONS.md #27.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from meme_hawkes import hawkes  # noqa: E402
from meme_hawkes.plots import INK_SOFT  # noqa: E402
from meme_hawkes.report import write_section  # noqa: E402
from meme_hawkes.warning import WINDOW, evaluate, signals, wilson  # noqa: E402

SWEEPS = {
    "n": [0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99],
    "rate": [0.5, 1, 2, 5, 10, 20],
    "price_ratio": [1.25, 1.5, 2, 3],
    "early_sells": [0.05, 0.1, 0.2, 0.3, 0.5],
}
PRESET = {"n": 0.9, "rate": 2, "price_ratio": 1.5, "early_sells": 0.2}
NAMES = {"n": "Branching ratio n (Hawkes)", "rate": "Trade rate (baseline)",
         "price_ratio": "Price vs low (baseline)", "early_sells": "Early-wallet selling"}
COLOURS = {"n": "#2a78d6", "rate": "#eb6834", "price_ratio": "#1baf7a", "early_sells": "#eda100"}


def small_window_noise(reps: int = 200) -> str:
    """How precisely can n be estimated from just 30 events? (Simulation.)"""
    rng = np.random.default_rng(2026)
    out = []
    for n_true in (0.3, 0.8):
        est = []
        while len(est) < reps:
            t = hawkes.simulate(1.0 * (1 - n_true), n_true * 2.0, 2.0, 60, rng)
            if len(t) >= WINDOW:
                w = t[:WINDOW]
                est.append(hawkes.fit(w - w[0], w[-1] - w[0] + 0.01)["n"])
        lo, hi = np.quantile(est, [0.1, 0.9])
        out.append(f"true n = {n_true}: average estimate {np.mean(est):.2f}, middle 80% between {lo:.2f} and {hi:.2f}")
    return "; ".join(out)


def main():
    trades = pd.read_csv("data/processed/trades.csv")
    labels = pd.read_csv("data/processed/labels.csv").dropna(subset=["pump_and_dump"])
    labels["pump_and_dump"] = labels["pump_and_dump"].astype(str) == "True"

    cache = Path("data/processed/signals.csv")
    if cache.exists() and "--recompute" not in sys.argv:
        print("Using saved signals (run with --recompute to rebuild them)")
        all_signals = {m: s.drop(columns="mint") for m, s in pd.read_csv(cache).groupby("mint")}
    else:
        all_signals, frames = {}, []
        for k, (mint, g) in enumerate(trades.sort_values(["mint", "slot", "tx_index"]).groupby("mint"), 1):
            if len(g) < WINDOW:
                continue  # too few trades to compute any signal: never alarms
            print(f"[{k}/{trades['mint'].nunique()}] {mint[:6]} ({len(g)} trades)")
            s = signals(g)
            all_signals[mint] = s
            frames.append(s.assign(mint=mint))
        pd.concat(frames).to_csv(cache, index=False)

    sweep = pd.DataFrame([evaluate(all_signals, labels, col, th) for col, ths in SWEEPS.items() for th in ths])
    preset = sweep[[PRESET[c] == th for c, th in zip(sweep["signal"], sweep["threshold"])]]

    # Figure: recall vs false-alarm rate for every threshold; preset points ringed.
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4))
    for col in SWEEPS:
        s = sweep[sweep["signal"] == col].sort_values("false_alarm_rate")
        left.plot(s["false_alarm_rate"], s["recall"], "-o", color=COLOURS[col], lw=2, ms=6, label=NAMES[col])
        p = preset[preset["signal"] == col]
        left.plot(p["false_alarm_rate"], p["recall"], "o", ms=13, mfc="none", mec=COLOURS[col], mew=2)
    left.plot([0, 1], [0, 1], color=INK_SOFT, ls="--", lw=1, label="No better than chance")
    left.set(title="Warnings before the dump", xlabel="False-alarm rate (other tokens)",
             ylabel="Share of dumps warned in time", xlim=(-0.03, 1.03), ylim=(-0.03, 1.03))
    left.legend(loc="lower right", fontsize=8, frameon=False)

    for x, col in enumerate(SWEEPS):
        p = preset[preset["signal"] == col].iloc[0]
        right.bar(x, p["median_lead_s"] if np.isfinite(p["median_lead_s"]) else 0, color=COLOURS[col], width=0.6)
        right.text(x, (p["median_lead_s"] if np.isfinite(p["median_lead_s"]) else 0), f" {p['median_lead_s']:.0f}s",
                   ha="center", va="bottom", fontsize=9, color=INK_SOFT)
    right.set_xticks(range(len(SWEEPS)), [NAMES[c].split(" (")[0] for c in SWEEPS], fontsize=8)
    right.set(title="Median warning time at preset thresholds", ylabel="Seconds before the dump")
    fig.tight_layout()
    fig.savefig("figures/early_warning.png", dpi=160)

    base = labels["pump_and_dump"].mean()
    def fmt(r, ci=False):
        recall, far = f"{r['recall']:.0%}", f"{r['false_alarm_rate']:.0%}"
        if ci:
            lo, hi = wilson(r["hits"], r["positives"])
            recall += f" ({lo:.0%}–{hi:.0%})"
            lo, hi = wilson(r["false_alarms"], r["negatives"])
            far += f" ({lo:.0%}–{hi:.0%})"
        return (f"| {NAMES[r['signal']]} | {r['threshold']} | {recall} | {far} | "
                f"{r['precision']:.0%} | {r['too_late']} | {r['median_lead_s']:.0f} |")
    body = "\n".join([
        f"Generated by `scripts/early_warning.py`, design fixed beforehand (decision #27). "
        f"{int(labels['pump_and_dump'].sum())} pump-and-dumps and {int((~labels['pump_and_dump']).sum())} other tokens. "
        f"Signals use only past trades, every 5 trades, over the last {WINDOW} trades.",
        "",
        f"**Base rate:** {base:.0%} of tokens are pump-and-dumps, so alarming on every token gives {base:.0%} precision. "
        "A signal is only useful if it beats that *and* the baselines.",
        "",
        "### At the preset thresholds (95% confidence intervals in brackets)",
        "| Signal | Threshold | Dumps warned in time | False-alarm rate | Precision | Warned too late | Median lead (s) |",
        "|---|---|---|---|---|---|---|",
        *[fmt(r, ci=True) for _, r in preset.iterrows()],
        "",
        "### Every threshold tried",
        "| Signal | Threshold | Dumps warned in time | False-alarm rate | Precision | Warned too late | Median lead (s) |",
        "|---|---|---|---|---|---|---|",
        *[fmt(r) for _, r in sweep.iterrows()],
        "",
        f"**How noisy is n from {WINDOW} trades?** (simulation) {small_window_noise()}.",
        "",
        "![Early-warning results](../figures/early_warning.png)",
    ])
    write_section("## Stage 5: early-warning test", body)
    print(preset.to_string(index=False))
    print("\nWrote data/processed/signals.csv, figures/early_warning.png, docs/RESULTS.md (Stage 5 section)")


if __name__ == "__main__":
    main()

"""Figures for the README and the app, in one consistent, quiet style."""

import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURFACE, INK, INK_SOFT, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"  # first two slots of a colour-blind-checked palette

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK_SOFT, "axes.labelcolor": INK_SOFT, "text.color": INK,
    "xtick.color": INK_SOFT, "ytick.color": INK_SOFT, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "axes.axisbelow": True, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def qq_plot(ax, gaps: np.ndarray, title: str):
    """Rescaled gaps against Exponential(1) quantiles: on the diagonal = good fit."""
    gaps = np.sort(gaps)
    theory = -np.log(1 - (np.arange(1, len(gaps) + 1) - 0.5) / len(gaps))
    top = max(theory[-1], gaps[-1])
    ax.plot([0, top], [0, top], color=INK_SOFT, lw=1, ls="--")
    ax.plot(theory, gaps, "o", ms=3, color=BLUE, alpha=0.7)
    ax.set(title=title, xlabel="Exponential(1) quantile", ylabel="Rescaled gap")


def recovery_panel(ax, estimates: np.ndarray, truth: float, title: str):
    """Histogram of estimates from many simulations, with the true value marked."""
    ax.hist(estimates, bins=20, color=BLUE, alpha=0.85, edgecolor=SURFACE, linewidth=1)
    ax.axvline(truth, color=ORANGE, lw=2)
    ax.text(truth, 0.98, " true value", transform=ax.get_xaxis_transform(), va="top", fontsize=9,
            color=INK_SOFT, bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1})
    ax.set(title=title, ylabel="Simulations")


def intensity_plot(ax, grid: np.ndarray, lam: np.ndarray, times: np.ndarray, title: str):
    """Fitted intensity over time, with each trade as a tick along the bottom."""
    ax.plot(grid, lam, color=BLUE, lw=2)
    ax.plot(times, np.zeros_like(times), "|", color=INK_SOFT, ms=8, alpha=0.6)
    ax.set(title=title, xlabel="Seconds since launch", ylabel="Trades per second (fitted)")

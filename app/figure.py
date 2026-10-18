"""The cascade figure: every trade as a dot on the price path, coloured by how likely it
was set off by an earlier trade, above the fitted trading rate. Pure Python -> SVG text.

Two sizes are drawn (wide and phone) and CSS shows the right one, so text in the
figure stays readable instead of shrinking with the page.
"""

from html import escape

import numpy as np
import pandas as pd

SYMLOG_C = 5.0
# Grey -> indigo, evenly spaced in OKLab (checked with the dataviz palette validator).
RAMP = ["#A2ACC3", "#919DC1", "#808EBF", "#707FBC", "#6070B9", "#5260B5", "#444FB1", "#383DAD", "#2E28A8"]
INK, INK_2, GRID, SHEET, VERMILION = "#131A2A", "#4E5A6E", "#E3E8EF", "#FAFBFC", "#E4472E"
TICKS = [(0, "0"), (1, "1 s"), (5, "5 s"), (10, "10 s"), (30, "30 s"), (60, "1 min"), (120, "2 min"),
         (300, "5 min"), (600, "10 min"), (1800, "30 min"), (3600, "1 h")]


def ramp(p: float) -> str:
    return RAMP[int(round(np.clip(p, 0, 1) * (len(RAMP) - 1)))]


def _symlog(t):
    return np.log1p(np.asarray(t, float) / SYMLOG_C)


def _nice_log_ticks(lo: float, hi: float, max_ticks: int = 4) -> list[float]:
    """Price ticks at round values inside [lo, hi]: 1, 2, 5 x 10^k, finer steps if the range is narrow."""
    for steps in ((1, 2, 5), (1, 1.5, 2, 3, 4, 5, 7)):
        out = [m * 10.0 ** k for k in range(int(np.floor(np.log10(lo))), int(np.ceil(np.log10(hi))) + 1)
               for m in steps if lo <= m * 10.0 ** k <= hi]
        if len(out) >= 2:
            break
    if len(out) < 2:  # very narrow range: three evenly spaced (log) values
        out = list(np.exp(np.linspace(np.log(lo), np.log(hi), 5))[1:4])
    while len(out) > max_ticks:
        out = out[::2]
    return out


def _fmt_price(v: float) -> str:
    exponent = int(np.floor(np.log10(v)))
    mantissa = f"{v / 10 ** exponent:.2g}"
    return f"{mantissa}×10<tspan dy='-5' font-size='0.72em'>{exponent}</tspan>"


def cascade_svg(report: dict, width: int, compact: bool = False) -> str:
    ticks: pd.DataFrame = report["ticks"]
    curve: pd.DataFrame = report["curve"]
    T = float(report["seconds"])
    font = 11 if compact else 12
    left, right, top = (44, 10, 10) if compact else (62, 18, 14)
    price_h, gap, rate_h, axis_h = (230, 26, 92, 34) if compact else (300, 30, 116, 38)
    height = top + price_h + gap + rate_h + axis_h
    plot_w = width - left - right
    r_dot = 2.3 if compact else 2.9

    def x(t):
        return left + plot_w * _symlog(t) / _symlog(T)

    # Price panel (log scale)
    price = ticks["price"].to_numpy(float)
    ok = np.isfinite(price) & (price > 0)
    lo, hi = np.nanmin(price[ok]), np.nanmax(price[ok])
    if hi / lo < 1.5:  # nearly flat: give it some room
        lo, hi = lo / 1.25, hi * 1.25
    lo, hi = lo / 1.08, hi * 1.08

    def y_price(v):
        return top + price_h * (1 - (np.log(v) - np.log(lo)) / (np.log(hi) - np.log(lo)))

    # Rate panel (square-root scale, so spikes don't flatten everything else)
    rate_top = top + price_h + gap
    peak = max(float(curve["intensity"].max()), 1e-9)

    def y_rate(v):
        return rate_top + rate_h * (1 - np.sqrt(np.clip(v, 0, None) / peak))

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" '
             f'aria-label="Every trade on the price path, coloured by how likely it was a reaction, above the fitted trading rate" '
             f'font-family="Schibsted Grotesk, sans-serif" font-size="{font}">',
             f'<rect x="{left}" y="{top}" width="{plot_w}" height="{price_h}" fill="{SHEET}"/>',
             f'<rect x="{left}" y="{rate_top}" width="{plot_w}" height="{rate_h}" fill="{SHEET}"/>']

    # Fine "chart paper" grid, then labelled time gridlines
    for v in np.linspace(0, 1, 41 if not compact else 21)[1:-1]:
        gx = left + plot_w * v
        parts.append(f'<line x1="{gx:.1f}" x2="{gx:.1f}" y1="{top}" y2="{rate_top + rate_h}" stroke="{GRID}" stroke-width="0.5" opacity="0.6"/>')
    labelled = [(t, s) for t, s in TICKS if t <= T * 1.001]
    if compact:
        labelled = [(t, s) for t, s in labelled if t in (0, 5, 60, 600, 3600) or t == labelled[-1][0]]
    for t, label in labelled:
        gx = x(t)
        parts.append(f'<line x1="{gx:.1f}" x2="{gx:.1f}" y1="{top}" y2="{rate_top + rate_h}" stroke="#CDD5E0" stroke-width="1"/>')
        anchor = "start" if t == 0 else "middle"
        parts.append(f'<text x="{gx:.1f}" y="{rate_top + rate_h + 20}" text-anchor="{anchor}" fill="{INK_2}">{label}</text>')
    parts.append(f'<text x="{left + plot_w:.1f}" y="{rate_top + rate_h + 34}" text-anchor="end" fill="{INK_2}" '
                 f'font-size="{font - 1}">time since launch, stretched near the start</text>' if not compact else "")

    # Price ticks
    for v in _nice_log_ticks(lo, hi):
        gy = y_price(v)
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="#CDD5E0" stroke-width="1"/>')
        parts.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" text-anchor="end" fill="{INK_2}">{_fmt_price(v)}</text>')
    parts.append(f'<text x="{left - 8}" y="{top + 2}" text-anchor="end" dominant-baseline="hanging" fill="{INK_2}" '
                 f'font-size="{font - 1}">price</text>' if not compact else "")

    # Price path, thin, behind the dots
    order = np.argsort(ticks["t"].to_numpy())
    pts = " ".join(f"{x(t):.1f},{y_price(v):.1f}" for t, v in zip(ticks["t"].to_numpy()[order], price[order]) if v > 0)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#C3CBD8" stroke-width="1"/>')

    # Trades: low-probability first so reactions sit on top
    parts.append('<g class="trades">')
    for _, row in ticks.iloc[np.argsort(ticks["p_reaction"].to_numpy(), kind="stable")].iterrows():
        if not (row["price"] > 0):
            continue
        cx, cy = x(row["t"]), y_price(row["price"])
        early = row["group"] == "Early-slot wallet"
        ring = f' stroke="{VERMILION}" stroke-width="1.6"' if early else f' stroke="{SHEET}" stroke-width="0.6"'
        who = "early-slot wallet" if early else "ordinary wallet"
        tip = f"{row['t']:.1f} s, {row['side']} by an {who}: {row['p_reaction']:.0%} chance it was a reaction"
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_dot + (0.6 if early else 0)}" '
                     f'fill="{ramp(row["p_reaction"])}"{ring}><title>{escape(tip)}</title></circle>')
    parts.append("</g>")

    # Rate panel: fitted rate (filled) over the fading background (dashed)
    ct, ci, cb = curve["t"].to_numpy(), curve["intensity"].to_numpy(), curve["background"].to_numpy()
    line = " ".join(f"{x(t):.1f},{y_rate(v):.1f}" for t, v in zip(ct, ci))
    parts.append(f'<polygon points="{x(ct[0]):.1f},{rate_top + rate_h} {line} {x(ct[-1]):.1f},{rate_top + rate_h}" '
                 f'fill="{RAMP[5]}" opacity="0.18"/>')
    parts.append(f'<polyline points="{line}" fill="none" stroke="{RAMP[7]}" stroke-width="1.3"/>')
    bg = " ".join(f"{x(t):.1f},{y_rate(v):.1f}" for t, v in zip(ct, cb))
    parts.append(f'<polyline points="{bg}" fill="none" stroke="{INK}" stroke-width="1.4" stroke-dasharray="4 3"/>')
    for v in (peak / 4, peak):
        gy = y_rate(v)
        parts.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" text-anchor="end" fill="{INK_2}">{v:.0f}/s</text>'
                     if v >= 1 else f'<text x="{left - 8}" y="{gy + 4:.1f}" text-anchor="end" fill="{INK_2}">{v:.1f}/s</text>')
    parts.append(f'<text x="{left + plot_w - 8}" y="{rate_top + 14}" text-anchor="end" fill="{INK_2}" '
                 f'font-size="{font - 1}">trades per second, fitted</text>')
    parts.append("</svg>")
    return "".join(p for p in parts if p)

"""Meme Hawkes: how much of a new memecoin's trading is trades setting off more trades.

Run locally from the repo root:  streamlit run app/streamlit_app.py
The app draws; all the maths lives in meme_hawkes/analysis.py.
"""

import json
import os
import sys
from pathlib import Path

import altair as alt
import base58
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from meme_hawkes.analysis import analyse  # noqa: E402
from meme_hawkes.clean import clean_trades  # noqa: E402
from meme_hawkes.fetch import fetch_first_hour  # noqa: E402
from meme_hawkes.grouping import label_groups  # noqa: E402

REPO = "https://github.com/sanjayashokbuilds/meme-hawkes"
INK, SLATE, BLUE, ORANGE, GRID = "#17202B", "#5B6573", "#2A78D6", "#EB6834", "#DCE1E8"
LIVE_LOOKUPS_PER_SESSION = 5
MAX_SCANNED = 20_000  # transactions read per live lookup, to keep each one affordable

st.set_page_config(page_title="Meme Hawkes", page_icon="〰️", layout="centered")
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Instrument+Serif&display=swap');
html, body, .stApp, .stMarkdown, button, input, label {{ font-family: 'Instrument Sans', sans-serif; }}
h1, h2, h3, .readout-number {{ font-family: 'Instrument Serif', serif; font-weight: 400; color: {INK}; }}
h1 {{ font-size: 3.2rem; line-height: 1.05; margin-bottom: 0.2rem; }}
.lede {{ font-size: 1.15rem; color: {SLATE}; max-width: 38rem; margin-bottom: 1.5rem; }}
.facts {{ color: {SLATE}; margin-top: -0.6rem; }}
.readout-number {{ font-size: 2.8rem; line-height: 1; }}
.readout-label {{ color: {INK}; font-weight: 500; margin-top: 0.35rem; }}
.readout-note {{ color: {SLATE}; font-size: 0.9rem; margin-top: 0.2rem; }}
.not-box {{ border-left: 3px solid {ORANGE}; padding: 0.2rem 0 0.2rem 1rem; color: {INK}; }}
</style>
""", unsafe_allow_html=True)


# ---------- data ------------------------------------------------------------------------

@st.cache_data
def load_examples() -> dict:
    with open(ROOT / "data/processed/app_examples.json") as f:
        return json.load(f)


def live_key() -> str | None:
    if os.getenv("MEME_HAWKES_OFFLINE"):  # set by the tests: examples only, no network
        return None
    try:
        return st.secrets["HELIUS_API_KEY"]
    except Exception:  # no secrets file locally: fall back to .env / environment
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        return os.getenv("HELIUS_API_KEY") or None


@st.cache_data(ttl=24 * 3600, max_entries=200, show_spinner=False)
def live_report(mint: str) -> dict:
    os.environ["HELIUS_API_KEY"] = live_key() or ""
    raw = fetch_first_hour(mint, max_scanned=MAX_SCANNED)
    if raw.empty:
        return {"ok": False, "reason": "No pump.fun bonding-curve trades found for this address. "
                                       "Check it's a pump.fun token, not a wallet or a graduated pool."}
    report = analyse(label_groups(clean_trades(raw)))
    report["scan_capped"] = bool(raw.attrs.get("truncated"))
    return report


def as_frames(report: dict) -> dict:
    """Examples come from JSON; turn their tables back into DataFrames."""
    return {k: pd.DataFrame(v) if k in ("curve", "ticks") and not isinstance(v, pd.DataFrame) else v
            for k, v in report.items()}


def valid_address(text: str) -> bool:
    try:
        return len(base58.b58decode(text)) == 32
    except ValueError:
        return False


# ---------- drawing ---------------------------------------------------------------------

def seismograph(r: dict) -> alt.VConcatChart:
    """Fitted trading intensity, every trade as a tick, and the price, on one stretched time axis."""
    marks = [0] + [t for t in (1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600) if t <= r["seconds"]]
    scale = alt.Scale(type="symlog", constant=5, domain=[0, r["seconds"]], nice=False)
    label = "datum.value >= 60 ? (datum.value >= 3600 ? '1 h' : datum.value / 60 + ' min') : datum.value + ' s'"
    x = alt.X("t:Q", title="Time since launch (stretched near launch)", scale=scale,
              axis=alt.Axis(values=marks, labelExpr=label))
    x_hidden = alt.X("t:Q", title=None, scale=scale, axis=alt.Axis(values=marks, labels=False, ticks=False))
    base = dict(width="container")
    curve = alt.Chart(r["curve"]).mark_line(color=BLUE, strokeWidth=2).encode(
        x=x_hidden,
        y=alt.Y("intensity:Q", title="Trades per second", axis=alt.Axis(tickCount=4)),
        tooltip=[alt.Tooltip("t:Q", title="Seconds", format=".1f"),
                 alt.Tooltip("intensity:Q", title="Trades per second", format=".2f")],
    ).properties(height=220, **base)
    ticks = alt.Chart(r["ticks"]).mark_tick(thickness=1.5, size=22).encode(
        x=x_hidden,
        color=alt.Color("group:N", title=None, legend=alt.Legend(orient="top", direction="horizontal"),
                        scale=alt.Scale(domain=["Early-slot wallet", "Ordinary wallet"], range=[ORANGE, BLUE])),
        tooltip=[alt.Tooltip("t:Q", title="Seconds", format=".2f"), alt.Tooltip("group:N", title="Wallet"),
                 alt.Tooltip("side:N", title="Side")],
    ).properties(height=40, **base)
    price = alt.Chart(r["ticks"]).mark_line(color=SLATE, strokeWidth=1.5, interpolate="step-after").encode(
        x=x, y=alt.Y("price:Q", title=f"Price ({r.get('quote', 'SOL')})", axis=alt.Axis(format=".1e", tickCount=3),
                     scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("t:Q", title="Seconds", format=".1f"), alt.Tooltip("price:Q", title="Price", format=".3e")],
    ).properties(height=120, **base)
    return (alt.vconcat(curve, ticks, price, spacing=6)
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor=GRID, labelColor=SLATE, titleColor=SLATE, domainColor=GRID,
                            labelFont="Instrument Sans", titleFont="Instrument Sans", titleFontWeight=500)
            .configure_legend(labelColor=INK, labelFont="Instrument Sans", symbolType="square", symbolSize=120))


def readout(column, number: str, label: str, note: str):
    column.markdown(f'<div class="readout-number">{number}</div><div class="readout-label">{label}</div>'
                    f'<div class="readout-note">{note}</div>', unsafe_allow_html=True)


def show(mint: str, r: dict):
    if not r["ok"]:
        st.info(r["reason"])
        return
    st.subheader(f"Token {mint[:6]}…{mint[-4:]}")
    capped = " (capped at the first 3,000 trades)" if r.get("capped") else ""
    if r.get("scan_capped"):
        capped += ". Bot spam stopped the scan early, so this covers part of the hour"
    st.markdown(f'<p class="facts">{r["trades"]:,} trades from {r["wallets"]:,} wallets in the first '
                f'{r["seconds"]:,.0f} seconds{capped}.</p>', unsafe_allow_html=True)
    st.altair_chart(seismograph(r), use_container_width=True)

    a, b, c = st.columns(3)
    readout(a, f"{r['n']:.0%}", "of trades look like reactions to earlier trades",
            f"{r['n_constant']:.0%} if the launch rush is ignored")
    if r["early_to_ordinary"] is None:
        readout(b, "—", "early-slot → ordinary", "too few early-slot trades to separate")
    else:
        readout(b, f"{r['early_to_ordinary']:.2f}", "extra ordinary trades per early-slot trade",
                "one token's estimate is noisy (±0.16)")
    readout(c, f"{r['half_life_s']:.0f}s", "half-life of launch-time interest",
            "model fits this token well" if r["fit_ok"] else "model fits this token poorly")

    st.markdown("### What this means")
    st.markdown("\n".join(f"- {s}" for s in r["sentences"]))


# ---------- page ------------------------------------------------------------------------

st.markdown("<h1>Meme Hawkes</h1>", unsafe_allow_html=True)
st.markdown('<p class="lede">How much of a new pump.fun token\'s trading is trades setting off more trades, '
            "and how much of that comes from wallets that bought in its first seconds.</p>",
            unsafe_allow_html=True)

examples = load_examples()
names = {m: f"{m[:6]}…  {e.get('trades', 0):,} trades, "
            f"{'price doubled then halved' if e.get('dumped') else 'no pump-and-dump'}"
         for m, e in sorted(examples.items(), key=lambda kv: -kv[1].get("trades", 0))}

address = st.text_input("Token address", placeholder="Paste a pump.fun token address, e.g. …pump")
example = st.selectbox("Or open a token from the research sample", list(names), format_func=names.get, index=2)

st.session_state.setdefault("lookups", 0)
if address.strip():
    mint = address.strip()
    if mint in examples:
        show(mint, as_frames(examples[mint]))
    elif not valid_address(mint):
        st.error("That isn't a Solana address. Token addresses are 32–44 letters and numbers.")
    elif not live_key():
        st.info("Live lookups aren't switched on for this copy of the app. Open a research-sample token instead.")
    elif st.session_state["lookups"] >= LIVE_LOOKUPS_PER_SESSION:
        st.info(f"This session has used its {LIVE_LOOKUPS_PER_SESSION} live lookups. Reload the page later, "
                "or open a research-sample token.")
    else:
        with st.spinner("Reading the token's first hour from the blockchain and fitting the models…"):
            try:
                report = live_report(mint)
                st.session_state["lookups"] += 1
            except Exception as err:
                report = {"ok": False, "reason": f"The lookup failed: {err}. Try again in a minute."}
        show(mint, report)
else:
    show(example, as_frames(examples[example]))

st.markdown("### What this is not")
st.markdown(
    '<div class="not-box">This is not a pump-and-dump warning. In a study of 40 tokens, these excitation '
    "measures didn't warn of dumps any better than the simple rule \"the price has already doubled\". "
    "It's research on public blockchain data, not trading advice. Wallets are pseudonymous, and none are "
    "shown or accused of anything.</div>", unsafe_allow_html=True)

with st.expander("How it works"):
    st.markdown(f"""
Every trade on a pump.fun token is recorded on the Solana blockchain with the wallet that made it.
The app reads a token's first hour of trades and fits a **Hawkes process**: a model where each trade
briefly raises the chance of more trades.

- **Reactions share** is the branching ratio n: the average number of trades each trade sets off.
- The background rate is allowed to **fade after launch**. Without that, the launch rush gets mistaken
  for trades setting off trades, which is why the "if the launch rush is ignored" figure is higher.
- **Early-slot wallets** are those whose first buy landed within about a second of launch, which
  effectively takes a bot. That's a proxy for coordination, not proof of it.

Code, data, validation and every modelling decision: [GitHub]({REPO}).
""")

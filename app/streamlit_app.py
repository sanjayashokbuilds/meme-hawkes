"""Meme Hawkes: how much of a new memecoin's trading is trades setting off more trades.

Run locally from the repo root:  streamlit run app/streamlit_app.py
The app only draws. The maths is in meme_hawkes/analysis.py, the figure in app/figure.py.
"""

import json
import os
import sys
from html import escape
from pathlib import Path

import base58
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from figure import RAMP, VERMILION, cascade_svg  # noqa: E402

from meme_hawkes.analysis import SINGLE_TOKEN_SPREAD, analyse  # noqa: E402
from meme_hawkes.clean import clean_trades  # noqa: E402
from meme_hawkes.fetch import fetch_first_hour  # noqa: E402
from meme_hawkes.grouping import label_groups  # noqa: E402

REPO = "https://github.com/sanjayashokbuilds/meme-hawkes"
LIVE_LOOKUPS_PER_SESSION = 5
MAX_SCANNED = 20_000  # transactions read per live lookup, to keep each one affordable
MIN_EARLY_SHOWN = 30  # the two-type model was validated with ~40 early trades; below 30 we don't show a number
DEFAULT_TOKEN = "48UVWd"  # the clearest example of the main finding
STORIES = [  # (mint prefix, title, one line), chosen from the research sample; numbers from data/processed/app_examples.json
    ("48UVWd", "Mistaken for a frenzy", "A simple model says 98% of trades were reactions. Allow for the launch rush and it's 37%."),
    ("9xKXir", "A crowd feeding itself", "87% of trades were reactions, and early-slot wallets made only 5% of them."),
    ("8s3fys", "Run by its first buyers", "Wallets that bought in the first seconds made 59% of all 402 trades."),
    ("DoMDTY", "364 trades, 4 wallets", "Almost all the activity came from a handful of wallets trading back and forth."),
]

st.set_page_config(page_title="Meme Hawkes", page_icon="〰️", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Schibsted+Grotesk:wght@400;500;600&display=swap');
:root {
  --paper: #EEF1F5; --sheet: #FAFBFC; --ink: #131A2A; --ink-2: #4E5A6E; --ink-3: #7A8597;
  --rule: #D5DCE5; --indigo: #2E28A8; --vermilion: #E4472E;
}
html, body, .stApp { background: var(--paper); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button, .stApp div {
  font-family: 'Schibsted Grotesk', system-ui, sans-serif; color: var(--ink);
}
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1080px; padding: 2.2rem 1.25rem 4rem !important;
}
@media (max-width: 640px) { .block-container, [data-testid="stMainBlockContainer"] { padding-top: 1.2rem !important; } }

/* Top bar */
.mh-bar { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2.4rem; }
.stApp .mh-mark { font-family: 'Newsreader', serif !important; font-size: 1.5rem; letter-spacing: -0.01em; color: var(--ink); }
.mh-mark span { display: inline-block; width: 1.6rem; height: 0.7rem; margin-right: 0.45rem; vertical-align: 0.05rem;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 14'%3E%3Cpath d='M0 10 L6 10 L8 2 L10 12 L12 6 L14 9 L18 9 L19 4 L21 11 L23 9 L32 9' fill='none' stroke='%232E28A8' stroke-width='1.6' stroke-linejoin='round'/%3E%3C/svg%3E") no-repeat center/contain; }
.stApp .mh-bar a { color: var(--ink-2); text-decoration: none !important; font-size: 0.95rem; border-bottom: 1px solid var(--rule); }
.mh-bar a:hover { color: var(--ink); border-color: var(--ink); }

/* Lookup */
.mh-intro { font-size: 1.12rem; line-height: 1.55; color: var(--ink-2); max-width: 40rem; margin: 0 0 1.1rem; }
[data-testid="stForm"] { border: none !important; padding: 0 !important; }
/* Text input: style whichever wrapper directly holds the <input>, so it survives Streamlit DOM changes */
[data-testid="stTextInput"] div:has(> div > input), [data-testid="stTextInput"] div:has(> input) {
  height: 3.05rem !important; min-height: 3.05rem; border-radius: 10px !important; }
[data-testid="stTextInput"] div:has(> input) { background: var(--sheet) !important; border: 1px solid var(--rule) !important; }
[data-testid="stTextInput"] div:has(> input):focus-within { border-color: var(--indigo) !important;
  box-shadow: 0 0 0 3px rgba(46,40,168,0.14) !important; }
[data-testid="stTextInput"] div:has(> div > input) { border: none !important; background: transparent !important; box-shadow: none !important; }
[data-testid="stTextInput"] input { font-size: 1.02rem !important; padding: 0 0.95rem !important; height: 100% !important;
  background: transparent !important; color: var(--ink) !important; }
[data-testid="stTextInput"] input::placeholder { color: var(--ink-3); }
[data-testid="stSelectbox"] div:has(> div > input), [data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: var(--sheet) !important; border-color: var(--rule) !important; border-radius: 10px !important; }
/* Streamlit expander, restyled to match our own rows */
[data-testid="stExpander"] details { border: none !important; border-top: 1px solid var(--rule) !important;
  border-bottom: 1px solid var(--rule) !important; border-radius: 0 !important; background: transparent !important; }
[data-testid="stExpander"] summary { padding: 1rem 0 !important; font-weight: 500; display: flex !important;
  justify-content: space-between; }
[data-testid="stExpander"] summary > span { padding: 0 !important; margin: 0 !important; }
[data-testid="stExpander"] summary::after { content: "+"; color: var(--ink-2); font-size: 1.2rem; line-height: 1; }
[data-testid="stExpander"] details[open] summary::after { content: "–"; }
[data-testid="stExpander"] summary span:has(> [data-testid="stIconMaterial"]) { display: none !important; }
[data-testid="stExpander"] summary p { font-size: 1rem !important; font-weight: 500 !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"] { padding: 0 0 1rem !important; }
[data-testid="stFormSubmitButton"] button { background: var(--ink) !important; border: 1px solid var(--ink) !important;
  border-radius: 10px !important; height: 3.05rem; }
[data-testid="stFormSubmitButton"] button p { color: #FFFFFF !important; font-weight: 500; font-size: 1rem; }
[data-testid="stFormSubmitButton"] button:hover { background: var(--indigo) !important; border-color: var(--indigo) !important; }
[data-testid="stFormSubmitButton"] button:focus-visible { outline: 3px solid rgba(46,40,168,0.35); outline-offset: 2px; }

/* Stories */
.mh-stories { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0 1.6rem; margin: 1.6rem 0 3.2rem; }
.stApp .mh-stories a { text-decoration: none !important; display: block; padding: 0.9rem 0 0; border-top: 2px solid var(--rule); }
.mh-stories a:hover, .mh-stories a.on { border-top-color: var(--indigo); }
.mh-stories b { display: block; font-weight: 600; color: var(--ink); margin-bottom: 0.25rem; font-size: 0.98rem; }
.mh-stories span { color: var(--ink-2); font-size: 0.9rem; line-height: 1.45; display: block; }
@media (max-width: 860px) { .mh-stories { grid-template-columns: repeat(2, 1fr); gap: 1.1rem 1.4rem; } }

/* Headline */
.stApp .mh-headline { font-family: 'Newsreader', serif !important; font-weight: 400; font-size: clamp(2.1rem, 4.6vw, 3.55rem);
  line-height: 1.08; letter-spacing: -0.015em; color: var(--ink); max-width: 19ch; margin: 0 0 1rem; }
.mh-sub { font-size: 1.05rem; line-height: 1.55; color: var(--ink-2); max-width: 46rem; margin: 0 0 0.4rem; }
.mh-warn { display: inline-block; margin-top: 0.6rem; font-size: 0.95rem; color: var(--ink); background: #FCE8E4;
  border-radius: 6px; padding: 0.35rem 0.65rem; }

/* Figure */
.mh-figure { margin: 2rem 0 0.6rem; }
.mh-figure .phone { display: none; }
@media (max-width: 640px) { .mh-figure .wide { display: none; } .mh-figure .phone { display: block; } }
.mh-figure circle { transition: r 0.12s; }
.mh-figure circle:hover { r: 6; }
.mh-legend { display: flex; flex-wrap: wrap; gap: 0.6rem 1.8rem; align-items: center; color: var(--ink-2);
  font-size: 0.92rem; margin: 0.2rem 0 0 0; }
.mh-ramp { display: inline-flex; align-items: center; gap: 0.55rem; white-space: nowrap; }
.mh-legend > span { white-space: nowrap; }
@media (max-width: 640px) { .mh-ramp i { width: 3.5rem !important; } .mh-legend { font-size: 0.86rem; gap: 0.5rem 1.2rem; } }
.mh-ramp i { display: inline-block; width: 7.5rem; height: 0.55rem; border-radius: 3px; }
.mh-ring { display: inline-block; width: 0.8rem; height: 0.8rem; border-radius: 50%; vertical-align: -0.1rem;
  margin-right: 0.45rem; border: 2px solid var(--vermilion); background: #808EBF; }
.mh-dash { display: inline-block; width: 1.6rem; border-top: 2px dashed var(--ink); vertical-align: 0.25rem; margin-right: 0.45rem; }

/* Readouts */
.mh-readouts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.4rem 2.4rem; margin: 2.8rem 0 3rem; }
.mh-readouts > div { padding-top: 0.2rem; }
.stApp .mh-num { font-family: 'Newsreader', serif !important; font-size: 2.7rem; line-height: 1; color: var(--ink); }
.mh-num small { font-size: 1.1rem; color: var(--ink-2); margin-left: 0.3rem; }
.mh-what { margin-top: 0.55rem; font-weight: 500; line-height: 1.4; }
.mh-note { margin-top: 0.3rem; color: var(--ink-2); font-size: 0.92rem; line-height: 1.45; }
@media (max-width: 760px) { .mh-readouts { grid-template-columns: 1fr; } }

/* Sections */
.mh-section { border-top: 1px solid var(--rule); padding-top: 2rem; margin-top: 1rem; }
.stApp .mh-h2 { font-family: 'Newsreader', serif !important; font-weight: 400; font-size: 1.9rem; margin: 0 0 1.2rem; color: var(--ink); }
.mh-prose { font-size: 1.04rem; line-height: 1.65; max-width: 42rem; color: var(--ink); }
.mh-prose p { margin: 0 0 0.9rem; }
.mh-findings { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.6rem 2.4rem; margin-bottom: 1.4rem; }
.mh-findings b { display: block; font-weight: 600; margin-bottom: 0.4rem; line-height: 1.35; }
.mh-findings p { margin: 0; color: var(--ink-2); line-height: 1.55; font-size: 0.97rem; }
@media (max-width: 760px) { .mh-findings { grid-template-columns: 1fr; } }
.stApp a.mh-link { color: var(--indigo) !important; text-decoration: none !important; border-bottom: 1px solid rgba(46,40,168,0.3); }
.mh-link:hover { border-bottom-color: var(--indigo); }
details.mh-details { border-top: 1px solid var(--rule); padding: 1rem 0; }
details.mh-details:last-of-type { border-bottom: 1px solid var(--rule); }
details.mh-details summary { cursor: pointer; font-weight: 500; list-style: none; display: flex; justify-content: space-between; }
details.mh-details summary::after { content: "+"; color: var(--ink-2); font-size: 1.2rem; line-height: 1; }
details.mh-details[open] summary::after { content: "–"; }
details.mh-details summary:focus-visible { outline: 2px solid var(--indigo); outline-offset: 4px; }
details.mh-details .body { padding-top: 0.9rem; color: var(--ink); line-height: 1.6; max-width: 46rem; }
table.mh-params { border-collapse: collapse; font-variant-numeric: tabular-nums; margin-top: 0.4rem; }
table.mh-params td { padding: 0.32rem 1.6rem 0.32rem 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
table.mh-params td:first-child { color: var(--ink-2); }
.mh-foot { margin-top: 3rem; color: var(--ink-3); font-size: 0.88rem; line-height: 1.6; max-width: 46rem; }
.mh-message { background: var(--sheet); border: 1px solid var(--rule); border-radius: 10px; padding: 1rem 1.2rem;
  margin: 1.4rem 0; line-height: 1.55; }
@media (prefers-reduced-motion: reduce) { .mh-figure circle { transition: none; } }
</style>
"""


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
        return {"ok": False, "reason": "No pump.fun bonding-curve trades were found for this address. "
                                       "Check it's a pump.fun token, not a wallet or a graduated pool."}
    report = analyse(label_groups(clean_trades(raw)))
    report["scan_capped"] = bool(raw.attrs.get("truncated"))
    return report


def as_frames(report: dict) -> dict:
    return {k: pd.DataFrame(v) if k in ("curve", "ticks") and not isinstance(v, pd.DataFrame) else v
            for k, v in report.items()}


def valid_address(text: str) -> bool:
    try:
        return len(base58.b58decode(text)) == 32
    except ValueError:
        return False


def html(markup: str):
    """Render our own HTML. st.markdown (not st.html) keeps inline SVG; blank lines and
    indentation are removed so Markdown can't mistake parts of it for paragraphs or code."""
    st.markdown("\n".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


# ---------- copy ------------------------------------------------------------------------

def duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    if seconds < 5400:
        return f"{seconds / 60:.0f} minutes"
    return f"{seconds / 3600:.1f} hours"


def headline(r: dict) -> str:
    return f"{r['reaction_share']:.0%} of this token's trades were set off by earlier trades."


def subline(mint: str, r: dict) -> str:
    extra = ""
    if r.get("capped"):
        extra = " The busiest tokens are capped at their first 3,000 trades."
    if r.get("scan_capped"):
        extra += " Bot spam stopped the scan early, so this covers only part of the first hour."
    return (f"Token {escape(mint[:6])}…{escape(mint[-4:])} in its first {duration(r['seconds'])}: "
            f"{r['trades']:,} trades from {r['wallets']:,} wallets. The rest of the trades arrived on their own, "
            f"most of them in a launch rush that faded with a half-life of {r['half_life_s']:.0f} seconds.{extra}")


def reading(r: dict) -> str:
    gap = r["n_constant"] - r["n"]
    paras = [
        f"Each dot is one trade. The darker it is, the more likely the model thinks it was a reaction to the trades "
        f"just before it, rather than someone arriving on their own. Averaged over every trade, that comes to "
        f"{r['reaction_share']:.0%}.",
        f"The dashed line in the lower panel is the rate trades would arrive at with no knock-on effects: high at "
        f"launch, then fading. Everything above it is trades setting off trades. "
        + (f"A model without that fading line would have put the knock-on effect at {r['n_constant']:.2f} trades per "
           f"trade rather than {r['n']:.2f}, because it would mistake the launch rush for a frenzy."
           if gap > 0.05 else "Here, allowing for the launch rush changes little."),
    ]
    e2o = r["early_to_ordinary"] if r.get("early_trades", 0) >= MIN_EARLY_SHOWN else None
    if e2o is None:
        paras.append(f"Wallets that bought in the first couple of seconds (ringed in vermilion) made "
                     f"{r['early_share']:.0%} of trades: too few to say how much they set off ordinary trading.")
    else:
        paras.append(
            f"Wallets that bought in the first couple of seconds (ringed in vermilion) made {r['early_share']:.0%} of "
            f"trades. Each of their trades was followed by about {e2o:.2f} extra trades from ordinary wallets"
            + (", which is within the noise for a single token." if e2o < SINGLE_TOKEN_SPREAD else "."))
    if not r["fit_ok"]:
        paras.append("The model's fit check fails for this token, so read these numbers as rough.")
    return "".join(f"<p>{p}</p>" for p in paras)


# ---------- page pieces -----------------------------------------------------------------

def stories_html(examples: dict, current: str | None) -> str:
    links = []
    for prefix, title, line in STORIES:
        mint = next((m for m in examples if m.startswith(prefix)), None)
        if mint:
            on = " on" if mint == current else ""
            links.append(f'<a class="{on.strip()}" href="?token={mint}" target="_self"><b>{title}</b><span>{line}</span></a>')
    return f'<div class="mh-stories">{"".join(links)}</div>'


def report_html(mint: str, r: dict) -> str:
    gradient = f"linear-gradient(90deg, {', '.join(RAMP)})"
    warn = ('<div class="mh-warn">The model fits this token\'s timing poorly, so read these numbers loosely.</div>'
            if not r["fit_ok"] else "")
    e2o = r["early_to_ordinary"] if r.get("early_trades", 0) >= MIN_EARLY_SHOWN else None
    if e2o is None:
        e2o_num = "–"
        e2o_note = (f"Only {r.get('early_trades', 0)} early-slot trades, too few to estimate this reliably "
                    f"(the model was checked with about 40).")
    else:
        e2o_num = f"{e2o:.2f}"
        e2o_note = ("Within the noise for a single token (about ±0.16)." if e2o < SINGLE_TOKEN_SPREAD
                    else "One token's estimate is noisy, about ±0.16.")
    p = r.get("params", {})
    params = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in [
        ("Knock-on effect per trade, n (fading background)", f"{r['n']:.3f}"),
        ("Knock-on effect per trade, n (constant background)", f"{r['n_constant']:.3f}"),
        ("Long-run background rate μ₀", f"{p.get('mu0', float('nan')):.4f} trades/s"),
        ("Extra launch interest μ₁, fading at rate γ", f"{p.get('mu1', float('nan')):.3f} trades/s, γ = {p.get('gamma', float('nan')):.4f}/s"),
        ("Jump per trade α, fading at rate β", f"α = {p.get('alpha', float('nan')):.3f}, β = {p.get('beta', float('nan')):.3f}/s"),
        ("Fit check, time-rescaling KS p-value", f"{r.get('ks_p', float('nan')):.3f} fading, {r.get('ks_p_constant', float('nan')):.3f} constant"),
        ("AIC (lower is better)", f"{r.get('aic_fading', float('nan')):,.1f} fading, {r.get('aic_constant', float('nan')):,.1f} constant"),
    ])
    return f"""
<p class="mh-headline" role="heading" aria-level="1">{headline(r)}</p>
<p class="mh-sub">{subline(mint, r)}</p>{warn}
<div class="mh-figure">
  <div class="wide">{cascade_svg(r, 1040)}</div>
  <div class="phone">{cascade_svg(r, 420, compact=True)}</div>
</div>
<div class="mh-legend">
  <span class="mh-ramp">on its own <i style="background:{gradient}"></i> set off by earlier trades</span>
  <span><span class="mh-ring"></span>wallet that bought in the first couple of seconds</span>
  <span><span class="mh-dash"></span>rate with no knock-on effects</span>
</div>
<div class="mh-readouts">
  <div><div class="mh-num">{r['n_constant']:.0%}</div>
    <div class="mh-what">what a simpler model would claim</div>
    <div class="mh-note">It treats the launch rush as trades setting off trades, so it overstates the frenzy.</div></div>
  <div><div class="mh-num">{e2o_num}</div>
    <div class="mh-what">extra ordinary trades after each early-slot wallet's trade</div>
    <div class="mh-note">{e2o_note}</div></div>
  <div><div class="mh-num">{r.get('early_share', 0):.0%}</div>
    <div class="mh-what">of trades came from early-slot wallets</div>
    <div class="mh-note">Wallets whose first buy landed within a couple of seconds of launch, which effectively takes a bot.</div></div>
</div>
<div class="mh-section">
  <p class="mh-h2" role="heading" aria-level="2">Reading this token</p>
  <div class="mh-prose">{reading(r)}</div>
  <details class="mh-details"><summary>Model details</summary><div class="body">
    <table class="mh-params">{params}</table></div></details>
</div>
"""


RESEARCH_HTML = f"""
<div class="mh-section" style="margin-top:3rem">
  <p class="mh-h2" role="heading" aria-level="2">What 40 new tokens showed</p>
  <div class="mh-findings">
    <div><b>Most of the apparent frenzy is the launch rush.</b>
      <p>A standard model says each trade sets off 0.95 more, which is close to a runaway. Letting launch interest
      fade brings that down to 0.58. The data prefers the fading model for 82% of tokens.</p></div>
    <div><b>Early-slot wallets nudge ordinary trading, a little.</b>
      <p>Each of their trades is followed by about 0.15 extra ordinary trades. That's real but small,
      and noisy for any single token.</p></div>
    <div><b>It isn't a dump detector.</b>
      <p>As a warning signal, the knock-on effect caught 58% of dumps in time. "The price has already
      doubled" caught 81% with the same false-alarm rate.</p></div>
  </div>
  <p class="mh-prose"><a class="mh-link" href="{REPO}" target="_blank">Read the method, validation and every modelling decision on GitHub</a></p>
</div>
<details class="mh-details"><summary>How it works</summary><div class="body">
  <p>Every trade on a pump.fun token is public on the Solana blockchain, along with the wallet that made it.
  The app reads a token's first hour of trades and fits a <b>Hawkes process</b>: a model in which each trade
  briefly raises the chance of more trades, the way an earthquake raises the chance of aftershocks.</p>
  <p>The model splits the trading rate into a background part (people arriving on their own, high at launch and
  then fading) and a knock-on part (trades setting off trades). For each trade, the share of the rate that was
  knock-on at that moment is the probability it was a reaction. That is the colour of each dot.</p>
  <p>The estimates were checked on thousands of simulated tokens with known answers before being used on real data.</p>
</div></details>
<div class="mh-foot">Research on public blockchain data, not trading advice. Wallets are pseudonymous; none are
shown here or accused of anything. Built by Sanjay Ashok as 24-hour build #4.</div>
"""


# ---------- page ------------------------------------------------------------------------

html(CSS)
html(f'<div class="mh-bar"><div class="mh-mark"><span></span>Meme Hawkes</div>'
     f'<a href="{REPO}" target="_blank">Method and code</a></div>'
     '<p class="mh-intro">Paste a new pump.fun token and see how much of its first hour of trading was trades '
     'setting off more trades, and how much came from wallets that bought in its first seconds.</p>')

examples = load_examples()
default = next(m for m in examples if m.startswith(DEFAULT_TOKEN))
requested = st.query_params.get("token", "").strip()

with st.form("lookup", border=False):
    col_input, col_button = st.columns([5, 1], vertical_alignment="bottom")
    typed = col_input.text_input("Token address", value=requested if requested not in examples else "",
                                 placeholder="Paste a pump.fun token address", label_visibility="collapsed")
    if col_button.form_submit_button("Analyse", use_container_width=True) and typed.strip():
        st.query_params["token"] = typed.strip()
        requested = typed.strip()

current = requested or default
html(stories_html(examples, current))

st.session_state.setdefault("lookups", 0)
if current in examples:
    report = as_frames(examples[current])
elif not valid_address(current):
    report = {"ok": False, "reason": "That isn't a Solana address. Token addresses are 32 to 44 letters and numbers, "
                                     "and pump.fun ones usually end in “pump”."}
elif not live_key():
    report = {"ok": False, "reason": "Live lookups aren't switched on for this copy of the app. "
                                     "Open one of the tokens above instead."}
elif st.session_state["lookups"] >= LIVE_LOOKUPS_PER_SESSION:
    report = {"ok": False, "reason": f"This session has used its {LIVE_LOOKUPS_PER_SESSION} live lookups. "
                                     "Reload later, or open one of the tokens above."}
else:
    with st.spinner("Reading the token's first hour from the blockchain and fitting the models. "
                    "Busy tokens take up to a minute."):
        try:
            report = live_report(current)
            st.session_state["lookups"] += 1
        except Exception as err:
            report = {"ok": False, "reason": f"The lookup failed ({escape(str(err)[:160])}). Try again in a minute."}

if report.get("ok"):
    html(report_html(current, report))
else:
    html(f'<div class="mh-message">{report["reason"]}</div>')

with st.expander("Open any token from the research sample"):
    names = {m: f"{m[:6]}…{m[-4:]}, {e.get('trades', 0):,} trades"
                f"{', price doubled then halved' if e.get('dumped') else ''}"
             for m, e in sorted(examples.items(), key=lambda kv: -kv[1].get("trades", 0))}
    choice = st.selectbox("Sample token", list(names), format_func=names.get, index=None,
                          placeholder="Choose a token", label_visibility="collapsed")
    if choice and choice != current:
        st.query_params["token"] = choice
        st.rerun()

html(RESEARCH_HTML)

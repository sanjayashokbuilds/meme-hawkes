"""Everything the web app shows about one token, computed in one place (no Streamlit here).

Input: one token's trades, already cleaned and grouped (clean_trades + label_groups).
Output: a plain dict of numbers, curves and sentences, so the app only has to draw it.
Uses the models that came out best in the research (docs/RESULTS.md):
  * fading-background model for the headline branching ratio
  * constant-background model alongside it, to show how much the launch rush inflates n
  * two-type fading model for early -> ordinary excitation, when there's enough data
"""

import numpy as np
import pandas as pd

from . import fading, hawkes
from .clean import spread_ties

MIN_TRADES, MIN_PER_TYPE, MAX_TRADES = 30, 10, 3000
SINGLE_TOKEN_SPREAD = 0.16  # spread of one token's early->ordinary estimate (docs/VALIDATION_MULTIVARIATE.md)


def analyse(trades: pd.DataFrame) -> dict:
    """Fit the models to one token and describe the results in plain English."""
    g = trades.sort_values(["slot", "tx_index"]).head(MAX_TRADES).reset_index(drop=True)
    if len(g) < MIN_TRADES:
        return {"ok": False, "reason": f"This token has {len(g)} trades in its first hour. "
                                        f"The models need at least {MIN_TRADES} to say anything."}

    times = spread_ties(g, np.random.default_rng(0)).to_numpy()
    order = np.argsort(times, kind="stable")
    g, times = g.iloc[order].reset_index(drop=True), times[order]
    T = times[-1] + g["seconds_per_slot"].iloc[0]

    constant, fade = hawkes.fit(times, T), fading.fit(times, T)
    out = {
        "ok": True, "trades": len(g), "wallets": int(g["wallet"].nunique()), "seconds": float(T),
        "capped": len(trades) > MAX_TRADES,
        "n": fade["n"], "n_constant": constant["n"],
        "half_life_s": float(np.log(2) / fade["gamma"]),
        "fit_ok": fading.goodness_of_fit(times, fade) > 0.05,
        "fit_ok_constant": hawkes.goodness_of_fit(times, constant) > 0.05,
        "early_trades": int((g["group"] == "early").sum()),
        "early_to_ordinary": None,
    }

    types = (g["group"] == "ordinary").to_numpy().astype(int)
    if min(np.bincount(types, minlength=2)) >= MIN_PER_TYPE:
        out["early_to_ordinary"] = float(fading.fit_2(times, types, T)["branching"][1, 0])

    grid = np.linspace(0, T, 1500)
    out["curve"] = pd.DataFrame({"t": grid, "intensity": fading.intensity(grid, times, fade)})
    out["ticks"] = pd.DataFrame({"t": times, "group": g["group"].map({"early": "Early-slot wallet",
                                                                        "ordinary": "Ordinary wallet"}),
                                 "side": g["side"], "price": g["price"]})
    out["quote"] = str(g["quote"].iloc[0]) if "quote" in g else "SOL"
    out["sentences"] = describe(out)
    return out


def describe(r: dict) -> list[str]:
    """Plain-English reading of the numbers. Careful wording: these are statistical
    patterns in public trades, not claims about anyone's intent."""
    lines = [
        f"About {r['n']:.0%} of this token's trades look like reactions to earlier trades; "
        f"the rest arrive on their own.",
        f"Launch-time interest faded with a half-life of about {r['half_life_s']:.0f} seconds.",
        f"A simpler model that ignores the launch rush would put that share at {r['n_constant']:.0%}. "
        "The difference is the rush being mistaken for trades setting off trades.",
    ]
    e2o = r["early_to_ordinary"]
    if e2o is None:
        lines.append("Too few early-slot or ordinary trades to separate who set off whom.")
    elif e2o < SINGLE_TOKEN_SPREAD:
        lines.append(f"Trades by early-slot wallets were followed by {e2o:.2f} extra ordinary trades each, "
                     "which is within the noise for a single token.")
    else:
        lines.append(f"Each trade by an early-slot wallet was followed by about {e2o:.2f} extra trades "
                     "from ordinary wallets.")
    lines.append("The model describes this token's timing well." if r["fit_ok"] else
                 "The model doesn't describe this token's timing well, so treat these numbers loosely.")
    return lines

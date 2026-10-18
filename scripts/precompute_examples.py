"""Precompute the web app's reports for every token in the research sample.

Usage (from the repo root): python scripts/precompute_examples.py
Writes data/processed/app_examples.json, which the app loads instantly.
"""

import json
import sys

import pandas as pd

sys.path.insert(0, ".")
from meme_hawkes.analysis import analyse  # noqa: E402


def to_jsonable(report: dict) -> dict:
    out = {}
    for key, value in report.items():
        if isinstance(value, pd.DataFrame):
            # Round times and rates to keep the file small; never prices (they're around 1e-8).
            value = value.copy()
            for col in ("t", "intensity"):
                if col in value:
                    value[col] = value[col].round(3)
            out[key] = value.to_dict(orient="list")
        elif hasattr(value, "item"):  # numpy scalars
            out[key] = value.item()
        else:
            out[key] = value
    return out


trades = pd.read_csv("data/processed/trades.csv")
labels = pd.read_csv("data/processed/labels.csv").set_index("mint")
examples = {}
for k, (mint, g) in enumerate(trades.groupby("mint"), 1):
    print(f"[{k}/{trades['mint'].nunique()}] {mint[:6]} ({len(g)} trades)")
    report = to_jsonable(analyse(g))
    report["dumped"] = bool(labels.loc[mint, "pump_and_dump"] is True or str(labels.loc[mint, "pump_and_dump"]) == "True")
    examples[mint] = report
with open("data/processed/app_examples.json", "w") as f:
    json.dump(examples, f)
print("Wrote data/processed/app_examples.json")

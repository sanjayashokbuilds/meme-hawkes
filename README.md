# meme-hawkes

**Do coordinated wallets set off ordinary buyers? Measuring excitation in pump.fun memecoins with multivariate Hawkes processes.**

24-hour build #4 by [sanjayashokbuilds](https://github.com/sanjayashokbuilds). Work in progress.

## The question
On pump.fun, trades are public and every trade has a wallet address. That means we can split traders into "coordinated" wallets and "ordinary" wallets and ask how much of the ordinary buying is triggered by the coordinated buying. A multivariate Hawkes process puts a number on that triggering. We then test whether rising excitation gives an early warning before a pump-and-dump.

The finished project is a web app: paste a pump.fun token address, get an excitation report for that token.

## Build progress
- [x] Stage 0: scaffold
- [x] Stage 1: foundations and literature ([concepts](docs/CONCEPTS.md), [literature](docs/LITERATURE.md))
- [ ] Stage 2: data and wallet grouping (data layer and tests done; real data pull next — see [data notes](docs/DATA.md))
- [ ] Stage 3: univariate Hawkes, validated on simulated data
- [ ] Stage 4: multivariate Hawkes and branching ratios
- [ ] Stage 5: early-warning test against a baseline
- [ ] Stage 6: dashboard
- [ ] Stage 7: write-up

See [`docs/PLAN.md`](docs/PLAN.md) for the schedule and [`docs/DECISIONS.md`](docs/DECISIONS.md) for every modelling choice.

## Repository layout
```
meme_hawkes/   the Python package (data, models, diagnostics, evaluation)
notebooks/     step-by-step analysis notebooks
tests/         checks that the estimators recover known parameters
data/          raw pulls (not committed) and small processed samples
figures/       plots used in this README
app/           Streamlit dashboard
docs/          plan, decision log, concepts, literature, results
```

## Disclaimer
Research only, not trading advice. Wallets are pseudonymous; results describe coordinated behaviour statistically and in aggregate and do not accuse any individual wallet of wrongdoing.

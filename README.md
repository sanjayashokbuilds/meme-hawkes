# meme-hawkes

**Do coordinated wallets set off ordinary buyers? Measuring excitation in pump.fun memecoins with multivariate Hawkes processes.**

24-hour build #4 by [sanjayashokbuilds](https://github.com/sanjayashokbuilds). Work in progress.

## The question
On pump.fun, trades are public and every trade has a wallet address. That means we can split traders into "coordinated" wallets and "ordinary" wallets and ask how much of the ordinary buying is triggered by the coordinated buying. A multivariate Hawkes process puts a number on that triggering. We then test whether rising excitation gives an early warning before a pump-and-dump.

The finished project is a web app: paste a pump.fun token address, get an excitation report for that token.

## Build progress
- [x] Stage 0: scaffold
- [x] Stage 1: foundations and literature ([concepts](docs/CONCEPTS.md), [literature](docs/LITERATURE.md))
- [x] Stage 2: data, wallet grouping, pre-registered sample and pump-and-dump rule ([data notes](docs/DATA.md))
- [x] Stage 3: univariate Hawkes from scratch, validated on simulated data ([validation](docs/VALIDATION.md))
- [x] Stage 4: multivariate Hawkes from scratch, validated ([validation](docs/VALIDATION_MULTIVARIATE.md)); real-data results in [results](docs/RESULTS.md)
- [x] Stage 5: early-warning test against baselines ([results](docs/RESULTS.md#stage-5-early-warning-test))
- [ ] Stage 6: dashboard
- [ ] Stage 7: write-up

## Validation so far
Before touching real data, the estimator was run on 100 simulated trade histories per scenario with known parameters. It recovers the branching ratio with negligible bias. The spread is about ±0.04 at 1,000 trades and about ±0.06 at 300 trades. Full table in [`docs/VALIDATION.md`](docs/VALIDATION.md).

The two-type model (early-slot wallets vs ordinary wallets) was checked the same way, at real token sizes (~40 early and ~300 ordinary trades). It recovers a planted early→ordinary effect without bias (0.50 → 0.505, spread ±0.16). With no planted effect, 95% of estimates stay below 0.12, so it doesn't invent cross-excitation. Details in [`docs/VALIDATION_MULTIVARIATE.md`](docs/VALIDATION_MULTIVARIATE.md).

![Recovery of the branching ratio on simulated data](figures/recovery.png)

See [`docs/PLAN.md`](docs/PLAN.md) for the schedule and [`docs/DECISIONS.md`](docs/DECISIONS.md) for every modelling choice.

## Repository layout
```
meme_hawkes/   the Python package (data, models, diagnostics, evaluation)
notebooks/     step-by-step analysis notebooks
tests/         checks that the estimators recover known parameters
scripts/       command-line tools: fetch, sample, fit, validate, ship
data/          raw pulls (not committed) and small processed samples
figures/       plots used in this README
app/           Streamlit dashboard
docs/          plan, decision log, concepts, literature, results
```

## Disclaimer
Research only, not trading advice. Wallets are pseudonymous; results describe coordinated behaviour statistically and in aggregate and do not accuse any individual wallet of wrongdoing.

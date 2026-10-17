# Decision log

Every modelling or data choice, why it was made, and what the alternative was.
Newest at the bottom.

| # | Stage | Decision | Why | Alternative considered |
|---|---|---|---|---|
| 1 | 0 | Write the Hawkes simulation and estimation from scratch in numpy/scipy | So every step is understood and checkable, rather than trusting a library as a black box | `tick` or `hawkeslib` (may use later only to cross-check our estimates) |

| 2 | 1 | Don't use the RED-COHORT-2026-v1 cohort list as ground truth | The source paper's October 2026 correction withdraws its numbers because the buyer records were faulty | Using it anyway with a caveat |
| 3 | 1 | Research sample from a Dune trial; live app lookups from Helius | Bitquery's trial is about 200 calls with recent data only; Dune's free tier is view-only (its 14-day trial has 2,500 credits); Helius has a permanent free tier (1M credits/month) | Bitquery for both |
| 4 | 1 | App input is a pump.fun token mint address | The method needs wallet identities, which stock exchanges don't publish | Stock tickers |
| 5 | 1 | Wallet addresses are hashed in committed data and never shown in the app | Pseudonymous wallets; no public accusations of individuals | Publishing raw addresses |
| 6 | 1 | The app shows a "warning" only if Stage 5 shows it beats the baseline | A public tool shouldn't present an unvalidated signal as a predictor | Always showing it |
| 7 | 2 | "Early" wallet = first buy within 5 slots (~2 s) of launch; everyone else "ordinary" | Works on a single token (needed for the app) and is transparent; buying that fast effectively requires automation | Cross-token co-occurrence cohorts (needs many tokens; possible robustness check) |
| 8 | 2 | Clock built from slot numbers × 0.4 s | Finer than block times (whole seconds) and keeps within-second order | Block times; error to be checked against real data |

## Open questions
- Tied timestamps: Solana times are slot-level (~400 ms), so many trades share a time. Method to be chosen in Stage 3.
- Helius credit cost per token lookup: to measure in Stage 2 and set the app's caching and limits accordingly.

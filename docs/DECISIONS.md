# Decision log

Every modelling or data choice, why it was made, and what the alternative was.
Newest at the bottom.

| # | Stage | Decision | Why | Alternative considered |
|---|---|---|---|---|
| 1 | 0 | Write the Hawkes simulation and estimation from scratch in numpy/scipy | So every step is understood and checkable, rather than trusting a library as a black box | `tick` or `hawkeslib` (may use later only to cross-check our estimates) |

## Open questions
- Data source: Bitquery vs Dune — decide in Stage 2 based on what the free tiers actually allow.
- Wallet groups: published cohort list (if public and licensed for reuse) vs our own transparent heuristic.
- Published data: whether to replace wallet addresses with hashed IDs in anything committed to this repo.
- Tied timestamps: Solana times are slot-level (~400 ms), so many trades share a time. Method to be chosen in Stage 3.

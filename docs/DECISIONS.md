# Decision log

Every modelling or data choice, why it was made, and what the alternative was.
Newest at the bottom.

| # | Stage | Decision | Why | Alternative considered |
|---|---|---|---|---|
| 1 | 0 | Write the Hawkes simulation and estimation from scratch in numpy/scipy | So every step is understood and checkable, rather than trusting a library as a black box | `tick` or `hawkeslib` (may use later only to cross-check our estimates) |
| 2 | 1 | Don't use the RED-COHORT-2026-v1 cohort list as ground truth | The source paper's October 2026 correction withdraws its numbers because the buyer records were faulty | Using it anyway with a caveat |
| 3 | 2 | All data straight from the Solana blockchain via standard RPC calls, using a free Helius key (public endpoint as a no-account fallback) | Completely free with no card; one source for both research and the app; standard methods mean no lock-in | Dune trial (needs a trial), Bitquery trial (~200 calls, recent data only), pump.fun's own site feed (unofficial, can break) |
| 4 | 1 | App input is a pump.fun token mint address | The method needs wallet identities, which stock exchanges don't publish | Stock tickers |
| 5 | 1 | Wallet addresses are hashed in committed data and never shown in the app | Pseudonymous wallets; no public accusations of individuals | Publishing raw addresses |
| 6 | 1 | The app shows a "warning" only if Stage 5 shows it beats the baseline | A public tool shouldn't present an unvalidated signal as a predictor | Always showing it |
| 7 | 2 | "Early" wallet = first buy within 5 slots (~2 s) of launch; everyone else "ordinary" | Works on a single token (needed for the app) and is transparent; buying that fast effectively requires automation | Cross-token co-occurrence cohorts (needs many tokens; possible robustness check) |
| 8 | 2 | Clock = slots elapsed × slot length *measured per token* (slope of block time on slot) | First real token: a fixed 0.4 s/slot said 150 s, block times said 82 s (~0.22 s/slot). Slots give precise order; block times give the true scale | Fixed 0.4 s/slot (wrong on real data); block times alone (whole seconds, more ties) |
| 9 | 2 | Read trades by decoding pump.fun's own TradeEvent records (mint, SOL amount, buy/sell, wallet) | These are written by the pump.fun program itself, so they're the most direct record of each trade; events for other tokens are filtered out by mint | Inferring trades from balance changes (indirect, error-prone) |
| 10 | 2 | Analyse each token's earliest transactions (default 1,000) | Fetching is one call per transaction, so whole histories are slow; the early-warning question is about the early phase anyway | Full histories (much slower on free limits) |
| 11 | 2 | The project reads public blockchain data only and the app never links to trading on pump.fun | pump.fun's site is region-restricted in the UK; analysing public on-chain data is research, facilitating trading is not | Linking token pages to pump.fun |
| 12 | 2 | **Sample (pre-registered):** tokens launched 6–2 h before the pull, in seeded random order, kept if ≥100 successful transactions in their first hour, stop at 40; every check logged | Sampling by launch avoids favouring survivors; the activity floor gives enough events to fit; the log makes exclusions auditable | Sampling from currently active tokens (biased towards survivors, the opposite of what dumps look like) |
| 13 | 2 | Launches found via pump.fun's mint-authority account, verified at run time | Cheap way to list creations; the address isn't in docs we could check, so the code stops if it returns no launch records | Scanning all pump.fun transactions (tens of thousands of calls) |
| 14 | 2 | Price = curve price after each trade, from the event's virtual reserves | Exactly the bonding-curve price, no fees or rounding from trade sizes | SOL amount ÷ token amount per trade |
| 15 | 2 | **Label (pre-registered):** pump-and-dump = peak ≥ 2× the lowest earlier price, then a fall to ≤ ½ the peak, within the first hour; sensitivity: +50% / −30% (Mongardini & Mei) | Price-only, so the label can't leak from the model's inputs; stricter than the hourly-exchange thresholds because curve prices move mechanically with every buy | Their thresholds as primary; adding volume conditions (volume rises mechanically with price on a curve) |
| 16 | 3 | Ties spread uniformly within the slot, keeping order; every fit repeated over 5 random spreads | Simplest standard fix; repeating shows whether it matters (on simulated slot-rounded data, n moved by under 0.01) | Merging ties into one marked event |
| 17 | 3 | Optimise over (log μ, log β, logit n), so 0 < n < 1 | Every candidate is a valid, non-explosive model, which keeps the optimiser stable | Constrained optimisation on raw parameters |
| 18 | 3 | Observation window ends one slot after the last trade | Avoids inventing a quiet tail we didn't observe | A fixed 3,600 s (would count post-graduation silence as "no trades") |
| 19 | 2 | **Amendment 1 to rule 12** (17 Oct, 22:50, before any model was fitted to real data): count and fetch transactions on the token's *bonding-curve account*, not its mint. Sample re-drawn from scratch; first pull archived in `data/raw_v1/` (not published) | The first pull showed busy tokens' mints are flooded with wallet-to-wallet transfers that aren't trades (e.g. 2,087 transactions, 11 trades), which both inflated the activity filter and used up the 1,000-transaction cap | Keeping the first sample (its filter measured the wrong thing) |
| 20 | 2 | Bonding-curve address derived offline (seeds "bonding-curve" + mint), checked against every launch record during sampling | No extra network calls; verified against real chain data in the tests | Reading it from each token's launch transaction |
| 21 | 2 | Tokens priced in USDC are decoded from the event's quote fields; price = USDC per token | The first pull found 5 of 40 tokens priced in USDC (pump.fun's newer V2 instructions); their SOL fields are zero. Labels use price *ratios*, so mixing currencies is fine | Dropping non-SOL tokens (would bias the sample) |

## Known limitations so far
- **n < 1 by construction.** A pump could genuinely be explosive (n ≥ 1) for a while. Estimates pressing against 1 should be read as "at least near-critical", not as exact values.
- **Pooled stream.** Stage 3 treats all trades as one stream. Splitting by wallet group and buy/sell is Stage 4.
- **Sample size per token.** With ~300 events the branching ratio's spread is about ±0.06 (see `VALIDATION.md`), so small differences between single tokens aren't meaningful.

## Open questions
- Tied timestamps: Solana times are slot-level (~400 ms), so many trades share a time. Method to be chosen in Stage 3.
- Within-slot order: we keep the order the RPC returns. To verify against a block explorer on a few trades.
- Credits per token lookup: expected about 1 per transaction fetched; to measure on real data.
- Bot churn: on the first real token, 120 trades came from 15 wallets, one buying and selling every second or so. The early-slot rule labels such wallets "ordinary". Consider a third group (very-high-frequency wallets) in Stage 4.

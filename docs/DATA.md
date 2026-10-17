# Data

## The trade table
Every source is converted into one format (defined in `meme_hawkes/schema.py`): one row per trade.

| Column | Meaning |
|---|---|
| `mint` | token address |
| `slot` | Solana slot (~400 ms) |
| `tx_index` | position of the transaction inside its slot |
| `signature` | transaction id |
| `wallet` | trading wallet |
| `side` | `buy` or `sell` |
| `sol_amount` | SOL paid or received |

`clean_trades` then adds:
- `t`: seconds since the token's first trade, computed as slots elapsed × 0.4 s.
- `slot_ties`: how many trades share the slot.

## Sources
| Use | Source | Why |
|---|---|---|
| Research sample (20–50 tokens) | Dune, 14-day trial | SQL over decoded Solana tables; one query can pull the whole sample |
| Live lookups in the app | Helius, free plan | Permanent free tier (1M credits/month, rate-limited) |

Bitquery was ruled out: its trial is about 200 calls with recent data only.

## Wallet groups
A wallet is **early** on a token if its first buy lands in the first 5 slots (~2 seconds) of that token's trading. Everyone else is **ordinary**.
- Why: buying within ~2 seconds of launch effectively requires automation, and coordinated sniper groups concentrate in those first slots.
- Limits: it's a proxy. It catches fast solo bots as well as coordinated rings, and misses coordinated wallets that buy later. Results are reported as "early-slot wallets", not "manipulators".
- Robustness: Stage 4 re-runs the main result with 2 and 10 slots to show how much it depends on this choice.
- Not used as ground truth: the RED-COHORT-2026-v1 cohort list (its source paper's numbers were withdrawn; see `LITERATURE.md`).

## Privacy
Wallet addresses are replaced by salted 12-character hashes (`anonymise_wallets`) before any data is committed. The salt lives in `.env`, never in the repo.

## Still to do to finish Stage 2
1. Start the Dune trial. Find the pump.fun trade table in Dune's data explorer and confirm its column names. We write the SQL against what's actually there, not from memory.
2. **Fix the token sample and the pump-and-dump labelling rule *before* fitting any Hawkes model**, so the evaluation can't be tuned to the result.
3. Pull the sample and save it to `data/raw/` (not committed). Save the cleaned, anonymised table to `data/processed/`.
4. Check the slot clock against real block times and record the error here.
5. Write the Helius fetcher for single-token lookups and measure its credit cost per token.

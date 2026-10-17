# Data

## The trade table
Every source is converted into one format (defined in `meme_hawkes/schema.py`): one row per trade.

| Column | Meaning |
|---|---|
| `mint` | token address |
| `slot` | Solana slot (~400 ms) |
| `tx_index` | order of the trade within its slot |
| `signature` | transaction id |
| `wallet` | trading wallet |
| `side` | `buy` or `sell` |
| `sol_amount` | SOL paid or received |

`clean_trades` then adds:
- `t`: seconds since the token's first trade, computed as slots elapsed × that token's measured slot length.
- `seconds_per_slot`: the measured slot length. It's the slope of a straight line fitted to block time against slot, with 0.4 s as a fallback when there's under 10 s of data.
- `slot_ties`: how many trades share the slot.

Why measured: on the first real token, a fixed 0.4 s per slot gave 150 s where block times gave 82 s.

## Source: the Solana blockchain itself
Everything (the research sample and the app's live lookups) comes from standard Solana RPC calls, via `meme_hawkes/fetch.py`:

1. `getSignaturesForAddress` on the token's **bonding-curve account** lists its transactions (1,000 per call). The address is derived from the mint offline. We use the bonding curve rather than the mint because busy tokens' mints are flooded with wallet-to-wallet transfers that aren't trades.
2. `getTransaction` fetches each one (one call per transaction, which is the slow part).
3. Inside each transaction we find pump.fun's **TradeEvent** record. It starts with a fixed 8-byte tag (the first 8 bytes of sha256 of `"event:TradeEvent"`). We unpack mint, amount, buy/sell, wallet and the curve's reserves, which give the price. Events for other tokens are dropped.
4. **Quote currency:** most tokens are priced in SOL. Some newer ones are priced in USDC; their events carry the amounts in separate quote fields, and we read those. Columns `quote`, `amount` (in the quote currency) and `price` (quote per token) cover both.

The endpoint is a free Helius key if one is in `.env` (1M credits a month, up to 10 requests a second, no card), otherwise Solana's public endpoint (no account, slower).

Ruled out: Dune (free tier is view-only), Bitquery (trial of about 200 calls, recent data only), pump.fun's own site feed (unofficial and undocumented).

**Size limit:** the API only lists transactions newest-first, so reaching a token's first trades means paging through its whole history. Tokens with over 50,000 transactions are refused with a clear message. This mostly affects big graduated tokens, which aren't the early-phase tokens we study.

**Finding tokens:** pump.fun's website is region-restricted in the UK. We don't need it, and we don't route around it. `scripts/find_tokens.py` lists tokens straight from the pump.fun program's latest on-chain transactions.

**Check on real data:** the decoder is tested on hand-built events, but pump.fun can append fields to its events over time. `scripts/fetch_one.py` runs it on a real token. If the first fields ever moved, it decodes zero trades for the token and says so, rather than producing wrong numbers.

## The sample (pre-registered, see `meme_hawkes/sample.py`)
1. Population: every pump.fun token launched between 6 and 2 hours before the pull, so each first hour is complete.
2. Shuffled with a fixed seed (2026).
3. Kept if it had at least 100 successful bonding-curve transactions (trades) in its first hour. *Amendment 1: originally "transactions touching the mint"; see `DECISIONS.md` #19.*
4. Stop at 40 tokens. `data/raw/sample_log.csv` records every token checked and why it was kept or dropped.

Each kept token contributes its first hour of bonding-curve trades, capped at 1,000 transactions. Trades after graduation happen on a different program and aren't included.

## Pump-and-dump labels (pre-registered, see `meme_hawkes/labels.py`)
- **Primary:** the price peaks at least 2× above its lowest earlier level, then falls to half the peak or lower, within the first hour. The *dump time* is the first trade at or below half the peak.
- **Sensitivity:** the same with Mongardini & Mei's thresholds (+50%, −30%).
- Price only, so the label never uses wallet groups or trade timing, which are the model's inputs.

Both rules were committed (Stage 2c) before any model was fitted to real data.

## Wallet groups
A wallet is **early** on a token if its first buy lands in the first 5 slots (~2 seconds) of that token's trading. Everyone else is **ordinary**.
- Why: buying within ~2 seconds of launch effectively requires automation, and coordinated sniper groups concentrate in those first slots.
- Limits: it's a proxy. It catches fast solo bots as well as coordinated rings, and misses coordinated wallets that buy later. Results are reported as "early-slot wallets", not "manipulators".
- Robustness: Stage 4 re-runs the main result with 2 and 10 slots to show how much it depends on this choice.
- Not used as ground truth: the RED-COHORT-2026-v1 cohort list (its source paper's numbers were withdrawn; see `LITERATURE.md`).

## Privacy
Wallet addresses are replaced by salted 12-character hashes (`anonymise_wallets`) before any data is committed. The salt lives in `.env`, never in the repo.

## Pulling it
`python scripts/pull_sample.py` (about an hour on the free tier; safe to stop and re-run). Outputs:
- `data/raw/`: per-token trades with real wallet addresses. Not committed.
- `data/processed/trades.csv`: all trades, cleaned, grouped, wallets hashed, signatures dropped.
- `data/processed/labels.csv`: one row per token.

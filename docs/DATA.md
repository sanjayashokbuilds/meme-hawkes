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

1. `getSignaturesForAddress` on the token's mint address lists every transaction that touched it (1,000 per call).
2. `getTransaction` fetches each one (one call per transaction, which is the slow part).
3. Inside each transaction we find pump.fun's **TradeEvent** record. It starts with a fixed 8-byte tag (the first 8 bytes of sha256 of `"event:TradeEvent"`). We unpack its first six fields: mint, SOL amount, token amount, buy/sell, wallet, timestamp. Events for other tokens are dropped.

The endpoint is a free Helius key if one is in `.env` (1M credits a month, up to 10 requests a second, no card), otherwise Solana's public endpoint (no account, slower).

Ruled out: Dune (free tier is view-only), Bitquery (trial of about 200 calls, recent data only), pump.fun's own site feed (unofficial and undocumented).

**Size limit:** the API only lists transactions newest-first, so reaching a token's first trades means paging through its whole history. Tokens with over 50,000 transactions are refused with a clear message. This mostly affects big graduated tokens, which aren't the early-phase tokens we study.

**Finding tokens:** pump.fun's website is region-restricted in the UK. We don't need it, and we don't route around it. `scripts/find_tokens.py` lists tokens straight from the pump.fun program's latest on-chain transactions.

**Check on real data:** the decoder is tested on hand-built events, but pump.fun can append fields to its events over time. `scripts/fetch_one.py` runs it on a real token. If the first fields ever moved, it decodes zero trades for the token and says so, rather than producing wrong numbers.

## Wallet groups
A wallet is **early** on a token if its first buy lands in the first 5 slots (~2 seconds) of that token's trading. Everyone else is **ordinary**.
- Why: buying within ~2 seconds of launch effectively requires automation, and coordinated sniper groups concentrate in those first slots.
- Limits: it's a proxy. It catches fast solo bots as well as coordinated rings, and misses coordinated wallets that buy later. Results are reported as "early-slot wallets", not "manipulators".
- Robustness: Stage 4 re-runs the main result with 2 and 10 slots to show how much it depends on this choice.
- Not used as ground truth: the RED-COHORT-2026-v1 cohort list (its source paper's numbers were withdrawn; see `LITERATURE.md`).

## Privacy
Wallet addresses are replaced by salted 12-character hashes (`anonymise_wallets`) before any data is committed. The salt lives in `.env`, never in the repo.

## Still to do to finish Stage 2
1. Run `scripts/fetch_one.py` on one real token and check the output makes sense.
2. **Fix the token sample and the pump-and-dump labelling rule *before* fitting any Hawkes model**, so the evaluation can't be tuned to the result.
3. Pull the sample and save it to `data/raw/` (not committed). Save the cleaned, anonymised table to `data/processed/`.
4. Check the slot clock against real block times and record the error here.
5. Record the credits used per token from the Helius dashboard.

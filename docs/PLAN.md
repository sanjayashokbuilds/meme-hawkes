# Build plan and push schedule

24-hour solo build. Started Sat 17 Oct 2026, ~20:30 UK time.
Each stage ends with one commit and one tag, so the repo history tells the story of the build.

| Stage | Hours | Target time (UK) | What gets added | Tag |
|---|---|---|---|---|
| 0. Scaffold | 0 | Sat 20:30 | Folder layout, README skeleton, this plan, decision log | `stage-0` |
| 1. Foundations | 0–2 | Sat 22:30 | `docs/CONCEPTS.md` (plain-English notes), `docs/LITERATURE.md` (verified paper summaries, where we sit) | `stage-1` |
| 2. Data | 2–6 | Sun 02:30 | `meme_hawkes/data.py`, `meme_hawkes/grouping.py`, `docs/DATA.md`, small processed sample | `stage-2` |
| 3. Univariate Hawkes | 6–11 | Sun 07:30 | `meme_hawkes/univariate.py` (simulate, log-likelihood, fit), `meme_hawkes/diagnostics.py` (time-rescaling QQ), recovery tests, figures | `stage-3` |
| 4. Multivariate Hawkes | 11–16 | Sun 12:30 | `meme_hawkes/multivariate.py`, rolling branching ratio, excitation-matrix figures | `stage-4` |
| 5. Early warning | 16–19 | Sun 15:30 | `meme_hawkes/warning.py`, baseline, `docs/RESULTS.md` (precision, recall, lead time; negative results included) | `stage-5` |
| 6. Demo + deploy | 19–21 | Sun 17:30 | `app/streamlit_app.py`, deployed from this repo | `stage-6` |
| 7. Write-up | 21–24 | Sun 20:30 | Final README, cleaned notebooks, `v1.0` release | `v1.0` |

## The public web app: how the code is shaped from day one
The end product is a web app where anyone pastes a pump.fun token address and gets an excitation report for that token. To make that easy, the code is split into layers that never reach into each other:

```
fetch   →   clean   →   group   →   fit   →   report   →   app
(API)      (one table   (label     (Hawkes   (numbers +  (Streamlit
           format)      wallets)   models)   figures)     pages)
```

- **Every layer takes a pandas table in and gives a table or numbers out.** The app never contains maths; it just calls `report`.
- **The fetch layer is swappable.** Research data and live app lookups both come straight from the Solana blockchain through standard RPC calls (a free Helius key, or the public endpoint). Any future source just has to produce the same table, so nothing downstream cares where data came from.
- **The app analyses a token's earliest trades** (first 1,000 transactions by default), because fetching is one call per transaction on the free tier.
- **Wallet grouping must work on one token at a time**, because that's all the app sees for a live lookup.
- **The app never displays wallet addresses.** It shows aggregate shares and excitation, not "these wallets are scammers".
- **The app shows a warning signal only if Stage 5 shows it beats the baseline.** Otherwise it shows descriptive measures and says plainly that they aren't a validated predictor.
- **Hosting:** Streamlit Community Cloud, deployed straight from this repo, with the Helius key stored as a secret. Results are cached per token, and a few pre-computed example tokens work even if the API quota runs out.

## If we fall behind
Cut from the bottom. Priority order:
1. Validated univariate Hawkes (Stage 3) — non-negotiable
2. Multivariate excitation results (Stage 4)
3. Early-warning evaluation (Stage 5)
4. Demo (Stage 6)
5. Polish

## Rules for every stage
- Nothing gets committed that I can't explain line by line.
- Estimators are validated on simulated data before they touch real data.
- Every modelling choice goes in `docs/DECISIONS.md` with its reason.
- No API keys in the repo (they live in `.env`, which git ignores).
- No individual wallet is named as acting illegally. Coordinated behaviour is reported in aggregate.

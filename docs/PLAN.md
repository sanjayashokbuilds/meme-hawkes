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

# meme-hawkes v1.0

Self-exciting point processes on wallet-level pump.fun trade data, with a live web app: https://meme-hawkes.streamlit.app/

## Highlights
- **Data:** 40 randomly sampled new pump.fun tokens, full first hour each (13,749 trades), decoded straight from Solana. Wallets are hashed in the published data.
- **Models, written from scratch:** univariate, two-type (early-slot vs ordinary wallets) and fading-background Hawkes processes, with MLE, Ogata simulation and time-rescaling fit checks.
- **Validation:** every estimator recovers known parameters on simulated data at real token sizes.
- **Main finding:** the near-critical branching ratio (median 0.95) is mostly a launch-rush artefact. A fading background cuts it to 0.58, fits better for 82% of tokens, and more than doubles the share of tokens passing the fit check.
- **Negative results, reported:** early-slot wallets' excitation of ordinary trading is small (about 0.15), and excitation does not beat a simple price rule as a pump-and-dump warning.
- **Web app:** every trade drawn on the price path, coloured by how likely it was a reaction. It includes live lookups for any new token, and shareable links.

See the README for method, limitations and how to reproduce.

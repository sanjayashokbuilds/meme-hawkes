# Deploying the web app

The app is `app/streamlit_app.py`. It's hosted free on Streamlit Community Cloud, straight from this GitHub repo.

## Run it on your own computer first
From the repo root, with the virtual environment active:
```
streamlit run app/streamlit_app.py
```
It opens in your browser. Research-sample tokens work with no key. Live lookups use `HELIUS_API_KEY` from your `.env`.

## Put it online (one-off, about 5 minutes)
1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Choose **Create app**, then **Deploy a public app from GitHub**.
3. Repository: `sanjayashokbuilds/meme-hawkes`. Branch: `main`. Main file path: `app/streamlit_app.py`.
4. Optional: pick a custom subdomain, such as `meme-hawkes`.
5. Open **Advanced settings → Secrets** and paste:
   ```
   HELIUS_API_KEY = "your-key-here"
   ```
   The key is stored by Streamlit, never in the repo. Leave it out to run the app with research-sample tokens only.
6. Choose **Deploy**.

Every push to `main` redeploys the app automatically.

## How the app protects your free API credits
- Live lookups are cached for 24 hours per token, so repeat visits cost nothing.
- Each browser session gets 5 live lookups.
- Each lookup reads at most 20,000 transactions (about 2,000 credits at most; usually far fewer).
- Research-sample tokens are precomputed (`data/processed/app_examples.json`) and cost nothing.

If the monthly credits run out, the sample tokens keep working, and live lookups show an error until the credits reset.

## Updating the examples
After re-pulling or re-analysing the sample, run `python scripts/precompute_examples.py` and push.

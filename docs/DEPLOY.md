# Deploying the web app

The app lives in `app/`: `streamlit_app.py` is the page, `figure.py` draws the cascade figure, and `app/requirements.txt` lists what it needs. It's hosted free on Streamlit Community Cloud, straight from this GitHub repo.

## 1. Check it on your own computer
From the repo root, with the virtual environment active:
```
pip install -r app/requirements.txt
streamlit run app/streamlit_app.py
```
It opens at http://localhost:8501. The four story tokens and the whole research sample work with no key. Pasting any other pump.fun address does a live lookup using `HELIUS_API_KEY` from your `.env`. Each token has its own link (`?token=...`), so you can share a specific report.

## 2. Put it online (one-off, about 5 minutes)
1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub. Allow it to see your repositories when asked.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Fill in:
   - Repository: `sanjayashokbuilds/meme-hawkes`
   - Branch: `main`
   - Main file path: `app/streamlit_app.py`
   - App URL: choose something short, such as `meme-hawkes`
4. Open **Advanced settings**. Leave Python at the default, and paste this into **Secrets**, with your real key between the quotes:
   ```
   HELIUS_API_KEY = "your-key-here"
   ```
   The key is stored by Streamlit, never in the repo. Without it, the app still works for every sample token, and live lookups explain that they're switched off.
5. Click **Deploy**. The first build takes a few minutes.

After that, every push to `main` redeploys automatically. To change the key later: open the app's **Settings → Secrets** on share.streamlit.io.

## 3. Add the link everywhere
- The GitHub repo's **About** box (the cog on the repo page): paste the app URL as the website.
- The top of the README.
- Your GitHub profile README, as build #4.

## How the app protects your free API credits
- Live lookups are cached for 24 hours per token, so repeat visits cost nothing.
- Each browser session gets 5 live lookups.
- Each lookup reads at most 20,000 transactions.
- Sample tokens are precomputed (`data/processed/app_examples.json`) and cost nothing.

If the monthly credits run out, sample tokens keep working and live lookups show an error until the credits reset.

## Updating the precomputed examples
After re-pulling or re-analysing the sample: `python scripts/precompute_examples.py`, then push.

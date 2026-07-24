# Strava Activity Trends (Streamlit App)

A dashboard that pulls your Strava activities and shows trends over time:
distance, pace, and elevation gain, across all activity types, with rolling
averages and filters.

This guide covers the **no-install, browser-only path** (recommended if you
don't want to run anything on your machine), plus an optional local path if
you'd rather use the terminal.

---

## Option A: Browser-only, no installs

### 1. Create a Strava API app

1. Go to https://www.strava.com/settings/api
2. Fill in the form:
   - **Application Name**: anything, e.g. "My Trends Dashboard"
   - **Category**: pick anything (e.g. "Data Importer")
   - **Website**: can be anything, e.g. `http://localhost`
   - **Authorization Callback Domain**: `localhost`
3. Click **Create**. Copy your **Client ID** and **Client Secret**.

### 2. Get a refresh token, using just your browser

**a.** Build this URL, swapping in your Client ID, and paste it into your
browser's address bar:

```
https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=auto&scope=activity:read_all
```

**b.** Click **Authorize**. Your browser will try to redirect to `localhost`
and fail to load a page — that's expected, nothing is running there. Just
look at the address bar; it'll contain something like:

```
http://localhost/exchange_token?state=&code=abc123def456&scope=...
```

Copy the `code` value.

**c.** Exchange that code for a refresh token using a free in-browser REST
client, e.g. https://hoppscotch.io (no signup needed):
- Method: `POST`
- URL: `https://www.strava.com/oauth/token`
- Body (form or JSON): `client_id`, `client_secret`, `code` (from step b),
  `grant_type=authorization_code`
- Send it — the response includes a `refresh_token`. Save it somewhere safe.

### 3. Upload the code to GitHub

1. Create a new repo at https://github.com/new
2. Use **Add file → Upload files** and drag in `app.py`, `requirements.txt`,
   `README.md`, and `.gitignore` (you can skip `get_refresh_token.py` — it's
   only needed for the local option below).
3. Commit directly from the GitHub web UI.

### 4. Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **New app**.
3. Pick your repo, branch `main`, and set the main file path to `app.py`.
4. Click **Deploy**.

### 5. Add your Strava credentials as Cloud secrets

In the app's dashboard on Streamlit Cloud, go to **Settings → Secrets** and
paste:

```toml
[strava]
client_id = "12345"
client_secret = "your_client_secret"
refresh_token = "your_refresh_token"
```

Save — the app restarts and reads these automatically via `st.secrets`.
Nothing ever runs on your machine, and credentials never touch your repo.

**Gotcha to know about:** Strava sometimes issues a new refresh token when
it rotates. If the deployed app ever throws an auth error, repeat step 2 to
get a fresh code/token pair and update the Cloud secret.

---

## Option B: Local setup (if you'd rather use a terminal)

### 1. Create a Strava API app

Same as step 1 above.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get a refresh token with the helper script

```bash
python get_refresh_token.py
```

It asks for your Client ID/Secret, opens your browser to authorize, and
prints a refresh token — save it.

### 4. (Optional) Store credentials in secrets.toml

Create `.streamlit/secrets.toml` in this folder with the same `[strava]`
block shown above. Your `.gitignore` already excludes this file from git.

### 5. Run the app locally

```bash
streamlit run app.py
```

### 6. Push to GitHub

```bash
git init
git add .
git commit -m "Strava trends dashboard"
git remote add origin https://github.com/YOUR_USERNAME/strava-trends.git
git branch -M main
git push -u origin main
```

### 7. Deploy on Streamlit Community Cloud

Same as steps 4–5 in Option A.

## Notes

- The app uses Strava's `activity:read_all` scope, so it can see private
  activities too. If you'd rather it only see public ones, edit `SCOPE` in
  `get_refresh_token.py` to `"activity:read"` and re-authorize.
- Strava's API rate limits are generous for personal use (100 requests / 15
  min, 1000/day) — fine for this dashboard, but avoid hammering "refresh"
  repeatedly with very long lookback windows.
- Nothing here touches the internet except the Strava API — your credentials
  stay on your machine.

# Harman Kardon ONE — User Feedback Dashboard

A lightweight Flask web app that scrapes Google Play for user feedback on the Harman Kardon ONE app, classifies sentiment (pain points vs. gain points), and displays results in a clean dashboard.

Deployed on Render.com (free tier) with daily auto-refresh via cron job.

## Features

- **Google Play monitoring**: Multi-country review scraping (US, GB, DE, JP, CN)
- **Sentiment classification**: keyword-based pain/gain/neutral categorization
- **Live dashboard**: stats cards, 7-day trend chart, keyword frequency, filterable feedback list
- **Auto-deploy ready**: `render.yaml` included, one-click deploy via Render dashboard
- **Daily cron**: auto-scrape every morning at 08:00 UTC

## Project Structure

```
harman-feedback/
├── app.py                     # Flask app (routes + DB queries)
├── scraper/
│   ├── __init__.py            # run_all() entry point
│   └── googleplay_scraper.py  # Google Play reviews scraper
├── templates/
│   └── dashboard.html         # Single-page dashboard (HTML/CSS/JS)
├── requirements.txt
├── render.yaml                # Render deployment config
└── README.md
```

## Local Setup

### 1. Clone and virtual environment

```bash
cd harman-feedback
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Google Play App Package Name

The scraper tries `com.harman.kardon.one`. If this doesn't work:

1. Search "Harman Kardon ONE" on [Google Play](https://play.google.com)
2. Look at the URL: `https://play.google.com/store/apps/details?id=com.example.package`
3. Edit `scraper/googleplay_scraper.py` and update `APP_PACKAGE`

### 3. Initialize database and test

```bash
# Run scraper once to init DB and pull initial data
python -m scraper

# Start the dashboard
python app.py
```

Open [http://localhost:10000](http://localhost:10000) in your browser.

## Deploy to Render.com (Free Tier)

### Prerequisites

1. A GitHub/GitLab repo with this code pushed
2. A [Render.com](https://render.com) account (free plan)

### Steps

1. **Create a Web Service**
   - Go to Render Dashboard → **New** → **Web Service**
   - Connect your GitHub repo
   - Configure:
     - **Root Directory**: (leave blank, or `harman-feedback`)
     - **Runtime**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
     - **Plan**: `Free`
   - Add Environment Variables (under "Environment"):
     - `FLASK_ENV` = `production`
   - Click **Create Web Service**

2. **Create the Cron Job** (for daily auto-scrape)
   - Render Dashboard → **New** → **Cron Job**
   - **Name**: `daily-scrape`
   - **Schedule**: `0 8 * * *` (every day at 08:00 UTC)
   - **Region**: Oregon (same as web service)
   - **Command**: `python -m scraper`
   - **Plan**: `Free`
   - Click **Create Cron Job**

3. **Verify deployment**
   - Open your web service URL: `https://harman-feedback.onrender.com`
   - Click **"Scrape Now"** to pull initial data
   - Confirm data appears in the dashboard

## Render Free Tier Limitations

| Feature | Free Tier |
|---|---|
| Web service | Sleeps after 15 min inactivity, cold starts ~30s |
| Cron job | Max 1 execution/day |
| Disk | Ephemeral — DB resets on every deploy. **Fix**: migrate to Render PostgreSQL |
| Bandwidth | 100 GB/month |
| CPU | Shared, fair use |

### Fixing the SQLite persistence issue

Render's free filesystem is ephemeral. To persist data across deploys, switch to Render PostgreSQL:

```bash
# In Render dashboard: New → PostgreSQL
# Get the internal connection string
# Then update app.py to use psycopg2 instead of sqlite3
```

Or use [Turso](https://turso.tech) (free SQLite edge database):
```python
import turso
# turso libsql://your-db.turso.io - free tier up to 9GB
```

## Customization

### Change the app being monitored

Edit `scraper/googleplay_scraper.py` and update `APP_PACKAGE` to the correct package name.

### Improve sentiment classification

The current classifier uses simple keyword matching. To upgrade:
- Add a `.env` / env var `USE_OPENAI=true` + `OPENAI_API_KEY`
- Replace the `classify()` function with an OpenAI call:
```python
import openai

def classify(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"Classify as pain/gain/neutral: {text[:1000]}"}]
    )
    label = response.choices[0].message.content.strip().lower()
    if 'pain' in label: return 'pain'
    elif 'gain' in label: return 'gain'
    return 'neutral'
```

### Add App Store monitoring

No free App Store scraping API exists. Options:
1. **AppFollow** (paid API): `pip install appfollow` + API key
2. **GQCast** / **AppSic** (trial): limited free tier
3. **Manual CSV upload**: add an `/api/upload` route in `app.py` to accept CSV imports

### Add Reddit back (optional)

If you later get Reddit API access:
1. Uncomment `reddit_scraper.py` imports in `scraper/__init__.py`
2. Add `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` env vars
3. Update `render.yaml` with the env vars

## Troubleshooting

**"Google Play: Could not find app"**
→ The package name is wrong. Search manually on Google Play and check the `id=` param in the URL.

**"Database locked" errors**
→ Two processes are accessing `feedback.db` simultaneously. Use a file lock or switch to PostgreSQL.

**Cron job not running**
→ Render free cron only runs if the previous execution has completed. Long scrapes may miss schedules.

## License

MIT — free to use and modify.

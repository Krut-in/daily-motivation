# Daily Motivation

A cloud-scheduled daily motivational newsletter. Runs entirely on GitHub Actions, sends one themed email per day to krutin31@gmail.com at 8:05 AM EDT, archives the markdown back to this repo.

## Architecture

```
GitHub Actions cron (8:05 AM EDT)
         |
         v
  Python script (daily_motivation.py)
         |
   +-----+------+
   |            |
   v            v
Claude API   Gmail SMTP
(opus-4-7)   (smtp.gmail.com:587)
   |            |
   v            v
 Framing      Email -> krutin31@gmail.com
   |
   v
archive/YYYY-MM-DD-day-theme.md
   |
   v
 git commit + push back to this repo
```

No Mac dependency. Works regardless of laptop state.

## Repo layout

```
.
├── .github/workflows/daily.yml    # cron + setup + run + commit-archive
├── data/sources.json              # 251 motivation transcripts (pre-extracted from NotebookLM)
├── templates/
│   ├── letter.html                # Mon-Fri design (warm cream + serif)
│   └── card.html                  # Sat-Sun design (white card + system sans)
├── archive/                       # daily markdown files, committed by the workflow
├── daily_motivation.py            # main pipeline
├── requirements.txt
├── .gitignore
└── README.md
```

## Day-of-week theme map

| Day | Theme | Day color (accent) |
|---|---|---|
| Monday | Discipline | `#1E3A5F` deep slate blue |
| Tuesday | Focus | `#2D5A3D` forest green |
| Wednesday | Grind | `#8A4A1C` dark amber |
| Thursday | Belief | `#B8860B` warm gold |
| Friday | Outwork / Win | `#8B1538` crimson |
| Saturday | Identity | `#4B1E6A` royal purple |
| Sunday | Resilience | `#2C2C2C` charcoal |

## GitHub Secrets required

| Secret | Value |
|---|---|
| `GMAIL_USER` | krutin31@gmail.com |
| `GMAIL_APP_PASSWORD` | Gmail app password (16 chars, no spaces) |
| `ANTHROPIC_API_KEY` | API key from console.anthropic.com (starts with `sk-ant-api03-`) |

## Daylight saving

The cron line in `.github/workflows/daily.yml` is set to `5 12 * * *`, which is 8:05 AM EDT (UTC-4) March-November. When DST ends in November, edit it to `5 13 * * *` for 8:05 AM EST (UTC-5). Or leave it and accept the 1-hour drift in winter (delivery at 7:05 AM EST).

## Local testing

```bash
pip install -r requirements.txt
export GMAIL_USER=krutin31@gmail.com
export GMAIL_APP_PASSWORD=...
export ANTHROPIC_API_KEY=sk-ant-api03-...

# Compose without sending or archiving
python daily_motivation.py --dry-run

# Compose, send, and archive
python daily_motivation.py
```

## Refreshing the source corpus

`data/sources.json` is a static export of 251 motivation transcripts from your Weekly Motivation NotebookLM notebook. New sources you add to NotebookLM won't appear in emails until you re-export.

To refresh (run locally on your Mac with `nlm` CLI authenticated):

```bash
# from the repo root
python3 -c "
import json, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

NOTEBOOK_ID = '39807d62-2930-4dca-9460-27fcb493ba31'
ids = json.loads(subprocess.check_output(['nlm', 'list', 'sources', NOTEBOOK_ID, '--json']))

def fetch(s):
    r = subprocess.run(['nlm', 'source', 'content', s['id']], capture_output=True, text=True, timeout=30)
    return {'id': s['id'], 'title': s.get('title', ''), 'content': r.stdout.strip() if r.returncode == 0 else ''}

with ThreadPoolExecutor(max_workers=10) as ex:
    futures = {ex.submit(fetch, s): s for s in ids}
    sources = [f.result() for f in as_completed(futures)]

with open('data/sources.json', 'w') as f:
    json.dump({'notebook_id': NOTEBOOK_ID, 'sources': sources}, f, indent=2)

print(f'Refreshed {len(sources)} sources.')
"

git add data/sources.json
git commit -m "Refresh source corpus"
git push
```

## Cost

Per email: roughly $0.06 in Claude API tokens (Opus 4.7, ~5K input + 1.5K output). Monthly: about $1.85 at 30 emails. GitHub Actions free tier (2000 min/month for private repos) is more than enough.

## Pause or stop

In the GitHub repo: Settings > Actions > General > "Disable Actions" pauses everything immediately. Or disable just this workflow in the Actions tab.

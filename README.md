# Daily Motivation

A cloud-scheduled daily motivational newsletter. Runs entirely on GitHub Actions, sends one themed email per day to krutin31@gmail.com at 8:05 AM EDT, archives the markdown back to this repo.

**Zero LLM in the cron path.** Email content is pre-generated in 30-day batches by Claude Code (using your Max subscription) and read from `data/queue.json` at send time.

## Architecture

```
GitHub Actions cron (8:05 AM EDT, daily)
         |
         v
  Python script (daily_motivation.py)
         |
   reads data/queue.json[today_iso]
         |
         v
  renders templates/letter.html or card.html
         |
         v
  Gmail SMTP -> krutin31@gmail.com
         |
         v
  archive/YYYY-MM-DD-day-theme.md  -> git commit + push
```

No Mac dependency. No Anthropic API key. Works regardless of laptop state.

## Repo layout

```
.
├── .github/workflows/daily.yml    # cron + setup + run + commit-archive
├── data/
│   ├── queue.json                 # 30 days of pre-generated emails (refresh monthly)
│   └── sources.json               # 251 motivation transcripts (used for refreshing queue)
├── templates/
│   ├── letter.html                # Mon-Fri design (warm cream + serif)
│   └── card.html                  # Sat-Sun design (white card + system sans)
├── archive/                       # daily markdown files, committed by the workflow
├── daily_motivation.py            # main pipeline (stdlib only)
├── requirements.txt               # empty (stdlib only)
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

That's it. No `ANTHROPIC_API_KEY` because no LLM runs in the cron path.

## Refreshing the queue

The current queue covers May 9 to June 7, 2026 (30 days). When it's getting close to running out, refresh by opening any Claude Code chat and saying:

> "Refresh the motivation queue."

Claude Code will:
1. Read `data/sources.json` (251 motivation transcripts from your NotebookLM)
2. Pick themed sources for the next 30 days
3. Generate fresh framing for each day
4. Write a new `data/queue.json`
5. Commit and push to this repo

This uses your Claude Max subscription, so there's no marginal cost.

If you forget and the queue runs out, the workflow exits with a clear message ("No queue entry for {date}. Refresh by asking Claude Code...") and no email is sent that day. No silent failures.

## Daylight saving

The cron line in `.github/workflows/daily.yml` is set to `5 12 * * *`, which is 8:05 AM EDT (UTC-4) March-November. When DST ends in November, edit it to `5 13 * * *` for 8:05 AM EST (UTC-5). Or leave it and accept the 1-hour drift in winter (delivery at 7:05 AM EST).

## Local testing

```bash
export GMAIL_USER=krutin31@gmail.com
export GMAIL_APP_PASSWORD=...

# Compose without sending or archiving
python3 daily_motivation.py --dry-run

# Test a specific date in the queue
python3 daily_motivation.py --dry-run --force-date 2026-05-14

# Compose, send, and archive (uses today's date)
python3 daily_motivation.py
```

## Cost

GitHub Actions free tier (2,000 minutes/month for private repos) covers ~120,000 daily runs at 30 sec each. You'll use ~15 min/month. Zero ongoing API cost since no LLM in the cron path.

Refresh batches use Claude Max subscription, so $0 marginal cost.

## Pause or stop

In the GitHub repo: Settings > Actions > General > "Disable Actions" pauses everything immediately. Or disable just this workflow in the Actions tab.

To stop entirely: archive the repo or delete the workflow file.

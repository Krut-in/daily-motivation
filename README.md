# Daily Motivation

*A cloud-scheduled morning newsletter that doesn't depend on your laptop being awake.*

## The 7:55 AM problem

Most "scheduled task" tools assume your machine is on. The original local-Mac version of this project depended on `pmset` waking a lid-closed MacBook at 7:55 AM each morning. On battery, macOS only granted a 45-second DarkWake. By the time the dispatch landed, the host was asleep again, and the email never arrived.

The fix wasn't a smarter wake schedule. It was getting off the laptop entirely.

## The solution

Daily Motivation is a fully cloud-scheduled newsletter that arrives every morning at 8:05 AM. It runs on GitHub Actions and Gmail SMTP, with pre-generated content read from a static JSON queue checked into the repo.

The architectural move worth noting: **no LLM runs in the cron path.** Generation happens in advance using a separate manual trigger. Every cron tick reads the static file and dispatches the rendered template. Runtime stays under 10 seconds with Python stdlib only.

## Features

**Day-of-week theme rotation.** Each weekday carries a curated theme (Monday Discipline, Friday Outwork, etc.) with its own accent color in the email design. Saturday and Sunday use a softer card-style template. Monday through Friday use a contemplative serif "letter" layout.

**Two HTML templates, dark-mode native.** Both templates use table-based layout for cross-client compatibility (Outlook in particular), with inline CSS and `prefers-color-scheme: dark` media queries layered on top for automatic dark mode on iOS Mail and Apple Mail.

**Pre-generated content queue.** A single `data/queue.json` file holds 30 days of composed emails. Each entry carries a subject line and three quotes from a 251-source motivational corpus, plus original framing written in a specific voice with strict style constraints (no em dashes, no parallel-clause filler, second-person present tense).

**Self-archiving.** After each send, the workflow commits the daily markdown back to the repo under `archive/`. Over time the repo becomes a searchable history of every email sent.

**Milestone awareness.** The queue tags Day 7, Day 30, Day 100, and Day 365 as milestones. Those days carry a "Day N of practice" line in the masthead and an acknowledgment sentence in the opener framing.

**Graceful queue exhaustion.** When the queue runs out, the script exits cleanly with a "no entry for today" message and a one-line refresh instruction. Silent failures are designed out.

## Tech stack

- **Runtime:** Python 3.12, stdlib only (`smtplib`, `ssl`, `json`, `pathlib`)
- **Scheduling:** GitHub Actions cron in UTC, plus manual `workflow_dispatch` for testing
- **Delivery:** Gmail SMTP over STARTTLS on port 587, authenticated with a Gmail app password
- **Auth:** GitHub Secrets for credentials
- **Content generation (offline):** Claude API via Claude Code, batched into 30-day runs
- **Storage:** Plain JSON, git-versioned
- **Email design:** Hand-written HTML with table layout, inline CSS, dark-mode meta tags

No web framework or database. The only external services are GitHub and Gmail. Total monthly cost is $0.

## Setup

1. Fork or clone this repo.
2. Generate a Gmail app password at https://myaccount.google.com/apppasswords and copy the 16-character value.
3. Add two GitHub Secrets to the repo (Settings > Secrets and variables > Actions):
   - `GMAIL_USER`: your Gmail address (also the default recipient)
   - `GMAIL_APP_PASSWORD`: the password from step 2
4. Trigger the workflow once manually to verify:
   ```
   gh workflow run daily.yml
   ```
5. From here on, the workflow fires daily at 8:05 AM EDT (`5 12 * * *` UTC). Flip the cron line to `5 13 * * *` for EST in winter.

For local testing without sending:

```
python3 daily_motivation.py --dry-run
python3 daily_motivation.py --dry-run --force-date 2026-05-14
```

## Refreshing the queue

Open any Claude Code chat and say: **"refresh the motivation queue."** The model reads `sources.json`, generates the next 30 days of framing per the day-of-week theme map, and pushes a fresh `data/queue.json`. Uses your Claude subscription, no separate API key needed in the cron path.

## Roadmap

- **Web archive viewer.** A static GitHub Pages site that renders `archive/` markdown into a browseable history with theme filtering and full-text search.
- **Multiple recipients.** A configurable recipient list so the same email can fan out to friends or family without duplicating the queue.
- **Theme customization.** Per-recipient day-of-week mapping so different readers can pick different rotations.
- **Audio variant.** Generate a 60-second narrated version of each day's email via a TTS API, linked from the email body.
- **Refresh-from-CI.** Move the monthly queue refresh from a manual Claude Code chat into a `workflow_dispatch` job that calls the Claude API directly with a stored key.

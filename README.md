# Daily Motivation

*A small daily push from a curated playlist of motivational speeches, delivered to my inbox at 8 AM every morning.*

## The idea

Some mornings the inner voice that says "get moving" doesn't show up. I wanted a quiet daily push from speakers I'd already chosen (Eric Thomas, David Goggins, and others), arriving without me having to remember to look at it.

So I built a system that does it for me.

## What arrives each morning

A short email lands in my inbox around 8 AM. It carries a theme tied to the day of the week (Monday discipline, Friday outwork, etc.) and contains:

- **A hook quote** from a motivational speech in my collection
- **Two follow-on quotes** under "the method" and "the mindset" sections
- **A concrete action** for the day, framed in 2-3 sentences
- **A closing line** that ends with momentum

The design changes between weekdays (a serif "letter" style) and weekends (a softer card style). Milestone days like Day 7 and Day 30 carry a special note.

## How it works

```
Step 1   Keep 56 curated weekday-specific content records in a
         versioned content bank.

Step 2   Deterministically combine a hook, method, mindset, and action
         block for today's weekday.

Step 3   GitHub Actions retries through the morning. The first eligible
         run sends through Gmail and commits the archive to main.

Step 4   A read-only afternoon audit reports one failure if no valid
         archive was committed.
```

No AI runs at delivery time, no API key is required, and there is no queue to refresh. The content traversal is stable and versioned: individual blocks recur every 7-9 weeks, while complete four-block combinations take roughly 46-126 years to repeat, depending on the weekday pool size.

## Tech stack

Built with Python's standard library, GitHub Actions, and Gmail SMTP. The source corpus remains local and ignored; only the curated content bank is published. There is no web framework, database, paid runtime API, or third-party Python dependency.

## Setup

1. Fork or clone this repo.
2. Generate a Gmail app password at https://myaccount.google.com/apppasswords.
3. Add two GitHub Secrets: `GMAIL_USER` and `GMAIL_APP_PASSWORD`.
4. Run a safe preview:

   ```bash
   gh workflow run daily.yml -f mode=preview -f force_date=2026-07-12
   ```

Manual runs default to preview. A live recovery run always uses the actual ET date, keeps the time and archive guards enabled, and requires explicit confirmation:

```bash
gh workflow run daily.yml -f mode=live -f confirmation='SEND TODAY'
```

## Scheduling and failure alerts

The delivery workflow creates 21 opportunities between 3:30 and 8:30 AM in `America/New_York`. Runs before 7:30 AM exit successfully, and runs after a successful archive commit see that archive and skip. Delivery jobs always check out the current tip of `main`, so a queued retry cannot use a stale pre-archive snapshot.

Scheduled delivery failures are allowed to retry without producing a separate GitHub failure email each time. At 2:17 PM ET, `Daily Motivation Delivery Audit` checks for exactly one non-empty, structurally valid archive for the day. If all delivery attempts failed, that audit is the single authoritative workflow failure.

## Local verification

```bash
# Preview any date without credentials, SMTP, or archive writes
python3 daily_motivation.py --dry-run --force-date 2026-07-12

# Verify today's committed archive, or force a date for testing
python3 daily_motivation.py --verify-delivery
python3 daily_motivation.py --verify-delivery --force-date 2026-07-12

# Run the complete standard-library test suite
python3 -m unittest discover -s tests -v
```

`--force-date` is intentionally rejected for live delivery, and the former `--skip-guards` escape hatch has been removed.

## Content bank maintenance

`data/content_bank.json` is versioned and its record order is protected by a digest in `evergreen_content.py`. Reordering records changes the date-to-content mapping, so any future bank revision must deliberately bump the content-bank version and update its digest. The local `data/sources.json` transcript corpus stays ignored and must never be committed.

## Roadmap

- A web archive viewer for browsing past emails
- Multi-recipient support so the same email can fan out to friends or family
- A 60-second narrated audio version of each day's email

---

The result is an honest morning ritual that arrives whether or not I deserve it that day.

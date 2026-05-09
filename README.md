# Daily Motivation

*A small daily push from a curated playlist of motivational speeches, delivered to my inbox at 8 AM every morning.*

## The idea

Some mornings the inner voice that says "get moving" doesn't show up. I wanted a quiet daily push from speakers I'd already chosen (Eric Thomas, David Goggins, and others), arriving without me having to remember to look at it.

So I built a system that does it for me.

## What arrives each morning

A short email lands in my inbox at 8:05 AM. It carries a theme tied to the day of the week (Monday discipline, Friday outwork, etc.) and contains:

- **A hook quote** from a motivational speech in my collection
- **Two follow-on quotes** under "the method" and "the mindset" sections
- **A concrete action** for the day, framed in 2-3 sentences
- **A closing line** that ends with momentum

The design changes between weekdays (a serif "letter" style) and weekends (a softer card style). Milestone days like Day 7 and Day 30 carry a special note.

## How it works

```
Step 1   Curate motivational speeches as a YouTube playlist, then
         import it into Google NotebookLM for transcript extraction.

Step 2   Use Claude Code to compose 30 days of email framing in
         advance, written in a specific voice.

Step 3   GitHub Actions runs daily at 8:05 AM, picks today's email
         from the saved batch, and sends it via Gmail.
```

Notably, no AI runs at delivery time. The 30 daily emails are composed in advance, and the morning job just picks the right one and sends. The system runs in about 10 seconds per day at zero cost.

## Tech stack

Built with Python's standard library and GitHub Actions for the daily cron. The source corpus comes from Google NotebookLM, and monthly content batches use Claude. Delivery is via Gmail. The whole thing runs with no web framework or database.

## Setup

1. Fork or clone this repo.
2. Generate a Gmail app password at https://myaccount.google.com/apppasswords.
3. Add two GitHub Secrets: `GMAIL_USER` and `GMAIL_APP_PASSWORD`.
4. Trigger once to verify: `gh workflow run daily.yml`.

Cron is `5 12 * * *` UTC (8:05 AM EDT). Flip to `5 13 * * *` for EST in winter.

## Roadmap

- A web archive viewer for browsing past emails
- Multi-recipient support so the same email can fan out to friends or family
- A 60-second narrated audio version of each day's email

---

The result is an honest morning ritual that arrives whether or not I deserve it that day.

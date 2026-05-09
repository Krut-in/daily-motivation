# Daily Motivation

*An automated morning newsletter built from a hand-curated YouTube playlist of motivational speeches, delivered every day at 8 AM regardless of what kind of week it's been.*

## Why this exists

Some days the inner voice that says "get moving" doesn't show up. The first version of this idea was a Notion page of motivational quotes I'd open every morning. That habit lasted about three weeks. Anything that requires me to remember to look at it on the worst Monday of my life doesn't survive.

What I needed was something that arrived without me asking. A small daily push from the speakers I'd already chosen, on the days I'd most want to skip them.

## Phase 1: Building the corpus with NotebookLM

The raw material was already there: a YouTube playlist I'd been curating for months called Weekly Motivation, with 251 motivational speeches from Eric Thomas, David Goggins, Les Brown, and others. The problem was that 251 videos is great for binge-listening and terrible for systematic use.

I imported the entire playlist into Google NotebookLM, which gave me a single queryable source of truth. Every video became a structured note with auto-extracted transcripts and cross-corpus AI search. From there I used the `nlm` CLI to programmatically pull all 251 transcripts into a single JSON file (`sources.json`, ~1.9 MB).

Now the corpus was structured. The next problem was delivery.

## Phase 2: First attempt at automation

The first delivery system ran locally on my MacBook Air. Each morning at 8 AM EDT, a scheduled task would read the corpus and ask Claude to compose framing in a specific INFJ-friendly voice. The result was rendered as HTML and sent via Gmail SMTP. I configured `pmset` to wake the laptop at 7:55 AM so the task would have a host.

It worked once. Then it stopped.

The failure was specific and instructive. On battery, macOS only grants a 45-second `DarkWake` for scheduled `pmset` events. By the time the local Claude session was supposed to fire, the host was already back asleep. The email never sent. The morning ritual broke.

## Phase 3: Going cloud-native

The fix wasn't a smarter wake schedule. It was getting off the laptop entirely.

Daily Motivation now runs as a GitHub Actions cron job. Every morning at 8:05 AM the workflow spins up an Ubuntu container, reads a static `queue.json`, renders the email, and sends it via Gmail SMTP. After the send, it commits the day's markdown back to the repo as a permanent archive. Total runtime per day is under 10 seconds.

The architectural decision worth flagging: **no LLM in the cron path.** Email content is pre-generated in 30-day batches via Claude (using a Max subscription) and committed to the repo as a static file. The cron job only renders and sends. This eliminates an entire failure category and removes API key management from the runtime, while keeping the monthly cost at exactly $0.

## How it works today

```
Monthly:  sources.json --> Claude Code --> queue.json (committed to repo)
                                                |
                                                v
Daily:    queue.json[today] --> GitHub Actions --> HTML email --> Inbox
                                                |
                                                v
                                      archive/YYYY-MM-DD.md
                                      auto-committed back
```

Each weekday carries its own theme and accent color. Mon-Fri uses a contemplative serif "letter" template. Sat-Sun uses a softer card layout. Day 7, 30, 100, and 365 are tagged as milestones with a "Day N of practice" line in the masthead.

## Tech stack

- **Python 3.12** stdlib only (`smtplib`, `ssl`, `json`, `pathlib`)
- **GitHub Actions** for cron and manual `workflow_dispatch`
- **Gmail SMTP** over STARTTLS with an app password
- **Claude API** via Claude Code for offline batch generation
- **Google NotebookLM** for corpus extraction (one-time setup)
- **HTML email** with table layout and inline CSS, dark-mode media queries layered on top

Two GitHub Secrets are the only runtime configuration. The pipeline has no external dependencies beyond Python's standard library and Gmail.

## Setup

1. Fork or clone this repo.
2. Generate a Gmail app password at https://myaccount.google.com/apppasswords.
3. Add two GitHub Secrets to the repo: `GMAIL_USER` and `GMAIL_APP_PASSWORD`.
4. Trigger the workflow once to verify:
   ```
   gh workflow run daily.yml
   ```

The cron line is `5 12 * * *` UTC (8:05 AM EDT). Flip to `5 13 * * *` for EST in winter.

## Roadmap

- **Web archive viewer:** A static GitHub Pages site that renders `archive/` markdown into a browseable history with theme filtering.
- **Multi-recipient support:** A configurable recipient list so the same email can fan out to friends or family.
- **Per-recipient theme customization:** Different readers get different day-of-week rotations.
- **TTS audio variant:** A 60-second narrated version of each day's email linked from the body.
- **Refresh-from-CI:** Move the monthly queue refresh from a manual Claude Code chat into a `workflow_dispatch` job.

---

The result is a quiet daily push that arrives whether or not I deserve it that morning. Some days I read it carefully. Some days I just notice the subject line. Either way, the loop holds, and the worst Mondays get their counter-weight delivered without me having to summon it.

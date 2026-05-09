#!/usr/bin/env python3
"""Daily Motivation Email pipeline.

Reads sources from data/sources.json, picks 3 themed sources by day-of-week,
calls Claude API for V3 framing, renders Letter (Mon-Fri) or Card (Sat-Sun)
HTML template, sends via Gmail SMTP, and archives markdown to archive/.

Required env vars:
- GMAIL_USER
- GMAIL_APP_PASSWORD
- ANTHROPIC_API_KEY
- TO_EMAIL (optional, defaults to GMAIL_USER)

Usage: python3 daily_motivation.py [--dry-run]
"""
import argparse
import json
import os
import random
import smtplib
import ssl
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "data" / "sources.json"
TEMPLATES_DIR = ROOT / "templates"
ARCHIVE_DIR = ROOT / "archive"
START_DATE = date(2026, 5, 8)
MILESTONES = {7, 30, 100, 365}

THEMES = {
    0: ("Monday",    "Discipline",      ["DISCIPLINE", "MENTAL TOUGHNESS", "MASTER YOUR MIND", "SELF DISCIPLINE", "SELF CONTROL"]),
    1: ("Tuesday",   "Focus",           ["FOCUS", "STAY LOCKED IN"]),
    2: ("Wednesday", "Grind",           ["GRIND", "WORK ETHIC", "WORK HARDER", "WORK HARD"]),
    3: ("Thursday",  "Belief",          ["BELIEVE", "I CAN", "CONFIDENCE"]),
    4: ("Friday",    "Outwork / Win",   ["OUTWORK", "WIN", "PROVE"]),
    5: ("Saturday",  "Identity",        ["BEAST", "SAVAGE", "MONSTER", "LION", "OBSESSION"]),
    6: ("Sunday",    "Resilience",      ["WHEN LIFE", "DON'T QUIT", "NEVER QUIT", "KEEP GOING", "HOPE"]),
}

COLORS = {
    "Monday":    ("#1E3A5F", "#E8EDF4"),
    "Tuesday":   ("#2D5A3D", "#E8F0EB"),
    "Wednesday": ("#8A4A1C", "#F4ECE3"),
    "Thursday":  ("#B8860B", "#F8F1DD"),
    "Friday":    ("#8B1538", "#F8E5EB"),
    "Saturday":  ("#4B1E6A", "#EDE5F2"),
    "Sunday":    ("#2C2C2C", "#EAEAEA"),
}

MILESTONE_PREFIXES = {
    7:   "Day 7. One full week of mornings shaped by intent.",
    30:  "Day 30. A month of practice has compounded into something.",
    100: "Day 100. The ritual has its own gravity now.",
    365: "Day 365. One full year of mornings. The discipline has become you.",
}


class Framing(BaseModel):
    """Generated framing content for the daily email."""
    subject: str = Field(description="Subject line in format: '{Day} Fuel · {Theme phrase}'")
    quote_1: str = Field(description="Sharpest 1-2 line excerpt from source 1, cleaned of transcript filler")
    quote_2: str = Field(description="Sharpest 1-2 line excerpt from source 2, cleaned of transcript filler")
    quote_3: str = Field(description="Sharpest 1-2 line excerpt from source 3, cleaned of transcript filler")
    opener_framing: str = Field(description="2-3 sentences setting today's lens (immediately after the hook quote)")
    method_framing: str = Field(description="2-3 sentences on practical application (after Quote 2)")
    mindset_framing: str = Field(description="2-3 sentences on inner game (after Quote 3)")
    action_call: str = Field(description="2-3 sentences picking ONE specific task lens for today")
    closing_punch: str = Field(description="1 sentence ending with momentum")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Compose but don't send or archive")
    args = parser.parse_args()

    today = date.today()
    weekday_idx = today.weekday()
    day_name, theme, keywords = THEMES[weekday_idx]
    is_weekend = day_name in ("Saturday", "Sunday")
    day_n = (today - START_DATE).days + 1
    is_milestone = day_n in MILESTONES

    formatted_date = today.strftime("%B %-d, %Y")
    iso_date = today.isoformat()
    day_color, day_color_tint = COLORS[day_name]

    print(f"Today:    {day_name} {iso_date}")
    print(f"Theme:    {theme}")
    print(f"Day:      {day_n}{' [MILESTONE]' if is_milestone else ''}")
    print(f"Template: {'Card (weekend)' if is_weekend else 'Letter (weekday)'}")
    print(f"Color:    {day_color}")

    data = json.loads(SOURCES_PATH.read_text())
    sources = data["sources"]
    matched = [
        s for s in sources
        if any(kw.lower() in s["title"].lower() for kw in keywords) and s.get("content")
    ]
    if len(matched) < 3:
        extras = [s for s in sources if s not in matched and s.get("content")]
        matched.extend(random.sample(extras, 3 - len(matched)))
    picks = random.sample(matched, 3)

    print("Sources:")
    for p in picks:
        print(f"  - {p['title']}  ({p['id']})")

    print("Calling Claude API...")
    framing = generate_framing(picks, day_name, theme, is_milestone, day_n)
    print(f"Subject:  {framing.subject}")

    template_name = "card.html" if is_weekend else "letter.html"
    template = (TEMPLATES_DIR / template_name).read_text()

    masthead = build_masthead(day_name, formatted_date, day_n, is_milestone, is_weekend)
    source_titles = " · ".join(p["title"].split(" - ")[0].strip() for p in picks)
    theme_slug = theme.lower().replace(" / ", "-").replace(" ", "-")
    filename = f"{iso_date}-{day_name.lower()}-{theme_slug}.md"

    substitutions = {
        "{{SUBJECT}}":          framing.subject,
        "{{MASTHEAD}}":         masthead,
        "{{DAY_COLOR}}":        day_color,
        "{{DAY_COLOR_TINT}}":   day_color_tint,
        "{{QUOTE_1}}":          framing.quote_1,
        "{{QUOTE_2}}":          framing.quote_2,
        "{{QUOTE_3}}":          framing.quote_3,
        "{{OPENER_FRAMING}}":   framing.opener_framing,
        "{{METHOD_FRAMING}}":   framing.method_framing,
        "{{MINDSET_FRAMING}}":  framing.mindset_framing,
        "{{ACTION_CALL}}":      framing.action_call,
        "{{CLOSING_PUNCH}}":    framing.closing_punch,
        "{{SOURCE_TITLES}}":    source_titles,
        "{{FILENAME}}":         filename,
    }
    html = template
    for k, v in substitutions.items():
        html = html.replace(k, v)

    plain = build_plain(framing, source_titles, filename)
    md = build_markdown(framing, day_name, iso_date, theme, source_titles)

    if args.dry_run:
        print("\n=== DRY RUN ===")
        print("\n--- HTML head (first 600 chars) ---")
        print(html[:600])
        print("\n--- Plain body ---")
        print(plain)
        print("\n--- Archive markdown ---")
        print(md)
        return 0

    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to_addr = os.environ.get("TO_EMAIL", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = framing.subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    print("Sending via Gmail SMTP...")
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=ctx)
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
    print("  -> sent")

    ARCHIVE_DIR.mkdir(exist_ok=True)
    archive_path = ARCHIVE_DIR / filename
    archive_path.write_text(md)
    print(f"  -> archived {archive_path}")
    return 0


def generate_framing(picks, day_name, theme, is_milestone, day_n) -> Framing:
    client = anthropic.Anthropic()

    sources_text = "\n\n".join(
        f"## SOURCE {i+1}: {p['title']}\n\n{p['content'][:3000]}"
        for i, p in enumerate(picks)
    )
    milestone_note = ""
    if is_milestone:
        prefix = MILESTONE_PREFIXES.get(day_n, f"Day {day_n}.")
        milestone_note = (
            f"\n\nIMPORTANT: Today is Day {day_n} (a milestone). "
            f"Prepend opener_framing with this acknowledgment line: '{prefix}'"
        )

    prompt = f"""You are composing today's motivational email for an INFJ reader (Krutin Rathod).

Today: {day_name}
Theme: {theme}
Day-of-practice: {day_n}{' (MILESTONE)' if is_milestone else ''}

You have 3 source transcripts to draw from below. Your job:

1. Pick the SHARPEST 1-2 line excerpt from each source. Lightly clean (capitalize, punctuate, drop transcript filler like "ain't", "y'all", "fucking", "motherfucking"). Preserve the punch.
2. Write fresh framing for each section that fits today's theme.

STRICT STYLE RULES:
- Zero em dashes (use periods or commas)
- No three-parallel-clause structures (tricolons)
- No "not X, not Y" parallel negation
- Direct second-person "you", present tense
- Each framing section: 2-3 sentences max
- Avoid these words: delve, leverage, navigate, robust, seamless, unlock, unleash, harness, foster, bolster, ensure, embark, plethora, myriad, journey, transformative, empower, streamline, paradigm, ecosystem, holistic, synergy{milestone_note}

Subject line format: "{day_name} Fuel · <theme phrase>"
Examples: "Friday Fuel · Outwork everybody", "Saturday Fuel · Become the beast"

# Sources

{sources_text}
"""

    response = client.messages.parse(
        model="claude-opus-4-7",
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
        output_format=Framing,
    )
    return response.parsed_output


def build_masthead(day_name: str, formatted_date: str, day_n: int, is_milestone: bool, is_weekend: bool) -> str:
    if is_weekend:
        masthead = f"{day_name[:3].upper()} · {formatted_date.upper()}"
        if is_milestone:
            masthead += f" · DAY {day_n} OF PRACTICE"
    else:
        masthead = f"{day_name} · {formatted_date}"
        if is_milestone:
            masthead += f" · Day {day_n} of practice"
    return masthead


def build_plain(f: Framing, sources: str, filename: str) -> str:
    return (
        f'> "{f.quote_1}"\n\n'
        f'{f.opener_framing}\n\n'
        f'**The method.**\n\n'
        f'> "{f.quote_2}"\n\n'
        f'{f.method_framing}\n\n'
        f'**The mindset.**\n\n'
        f'> "{f.quote_3}"\n\n'
        f'{f.mindset_framing}\n\n'
        f'**Today\'s call.**\n\n'
        f'{f.action_call}\n\n'
        f'{f.closing_punch}\n\n'
        f'---\n\n'
        f'Sources: {sources} · Weekly Motivation\n'
        f'Archive: archive/{filename}\n'
    )


def build_markdown(f: Framing, day_name: str, iso_date: str, theme: str, sources: str) -> str:
    return (
        f'# {day_name} {iso_date} · {theme}\n\n'
        f'> "{f.quote_1}"\n\n'
        f'{f.opener_framing}\n\n'
        f'## The method\n\n'
        f'> "{f.quote_2}"\n\n'
        f'{f.method_framing}\n\n'
        f'## The mindset\n\n'
        f'> "{f.quote_3}"\n\n'
        f'{f.mindset_framing}\n\n'
        f'## Today\'s call\n\n'
        f'{f.action_call}\n\n'
        f'{f.closing_punch}\n\n'
        f'---\n\n'
        f'**Sources:** {sources} · Weekly Motivation notebook\n'
    )


if __name__ == "__main__":
    sys.exit(main())

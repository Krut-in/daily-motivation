#!/usr/bin/env python3
"""Daily Motivation Email pipeline (evergreen, deterministic content).

Composes a dated email from a versioned bank of curated content blocks, renders
the Letter (Mon-Fri) or Card (Sat-Sun) HTML template, sends via Gmail SMTP, and
archives markdown to archive/.

Required env vars:
- GMAIL_USER
- GMAIL_APP_PASSWORD
- TO_EMAIL (optional, defaults to GMAIL_USER)

Usage: python3 daily_motivation.py [--dry-run | --verify-delivery] [--force-date YYYY-MM-DD]

No AI API key or recurring content refresh is required.
"""
import argparse
import os
import smtplib
import ssl
import sys
from datetime import date, datetime, time as dt_time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

from evergreen_content import compose_entry

ROOT = Path(__file__).parent
TEMPLATES_DIR = ROOT / "templates"
ARCHIVE_DIR = ROOT / "archive"

ET = ZoneInfo("America/New_York")
WINDOW_START = dt_time(7, 30)  # 7:30 AM ET — earliest delivery time
LIVE_DELIVERY_START = date(2026, 7, 12)

DAY_COLORS = {
    "Monday":    ("#1E3A5F", "#E8EDF4"),
    "Tuesday":   ("#2D5A3D", "#E8F0EB"),
    "Wednesday": ("#8A4A1C", "#F4ECE3"),
    "Thursday":  ("#B8860B", "#F8F1DD"),
    "Friday":    ("#8B1538", "#F8E5EB"),
    "Saturday":  ("#4B1E6A", "#EDE5F2"),
    "Sunday":    ("#2C2C2C", "#EAEAEA"),
}


def main(
    argv: list[str] | None = None,
    *,
    now_et: datetime | None = None,
    archive_dir: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Compose but don't send or archive")
    mode.add_argument("--verify-delivery", action="store_true",
                      help="Verify that the required archive exists")
    parser.add_argument("--force-date", help="Use this ISO date instead of today (testing)")
    args = parser.parse_args(argv)

    if args.force_date and not (args.dry_run or args.verify_delivery):
        parser.error("--force-date requires --dry-run or --verify-delivery")

    now_et = now_et or datetime.now(ET)
    archive_dir = archive_dir or ARCHIVE_DIR
    try:
        target_date = date.fromisoformat(args.force_date) if args.force_date else now_et.date()
    except ValueError:
        parser.error("--force-date must use YYYY-MM-DD")
    today = target_date.isoformat()

    if args.verify_delivery:
        ok, message = verify_delivery(target_date, archive_dir=archive_dir)
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    if not args.dry_run and target_date < LIVE_DELIVERY_START:
        print(f"Live delivery starts {LIVE_DELIVERY_START.isoformat()}. Skipping {today}.")
        return 0

    # Guard 1: window check. GitHub Actions cron is delayed unpredictably, so
    # we fire many times per morning. Each early fire exits here until the ET
    # clock crosses 7:30 AM. The dry-run path skips this so previews still work.
    if not args.dry_run:
        if now_et.time() < WINDOW_START:
            print(f"ET time {now_et.strftime('%H:%M %Z')} is before delivery window "
                  f"({WINDOW_START.strftime('%H:%M')} ET). Skipping.")
            return 0

    # Guard 2: dedup. If today's archive markdown already exists in the repo
    # (committed by an earlier successful run today), exit silently.
    if not args.dry_run and archive_dir.exists():
        existing = sorted(archive_dir.glob(f"{today}-*.md"))
        if existing:
            print(f"Email for {today} already sent ({existing[0].name}). Skipping.")
            return 0

    entry = compose_entry(target_date)

    print(f"Today:    {entry['day_name']} {today}")
    print(f"Theme:    {entry['theme']}")
    print(f"Day:      {entry['day_n']}{' [MILESTONE]' if entry['is_milestone'] else ''}")
    print(f"Template: {'Card (weekend)' if entry['is_weekend'] else 'Letter (weekday)'}")
    print(f"Subject:  {entry['subject']}")

    filename = archive_filename(entry)
    html = render_html(entry, filename=filename)
    plain = build_plain(entry, filename)
    md = build_markdown(entry, today)

    if args.dry_run:
        print("\n=== DRY RUN ===")
        print("\n--- HTML (first 600 chars) ---")
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
    msg["Subject"] = entry["subject"]
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

    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / filename
    archive_path.write_text(md)
    print(f"  -> archived {archive_path}")
    return 0


def verify_delivery(target_date: date, archive_dir: Path = ARCHIVE_DIR) -> tuple[bool, str]:
    """Return whether a delivery archive is present for a required ET date."""
    if target_date < LIVE_DELIVERY_START:
        return True, f"Delivery is not required before {LIVE_DELIVERY_START.isoformat()}."

    matches = sorted(archive_dir.glob(f"{target_date.isoformat()}-*.md"))
    if not matches:
        return False, f"No delivery archive found for {target_date.isoformat()}."
    if len(matches) != 1:
        return False, (
            f"Expected exactly one delivery archive for {target_date.isoformat()}, "
            f"found {len(matches)}."
        )

    entry = compose_entry(target_date)
    archive_path = matches[0]
    expected_filename = archive_filename(entry)
    expected_content = build_markdown(entry, target_date.isoformat())
    content = archive_path.read_text(encoding="utf-8")
    if archive_path.name != expected_filename or content != expected_content:
        return False, f"Delivery archive is invalid: {archive_path.name}"

    return True, f"Delivery archive verified: {archive_path.name}"


def archive_filename(entry: dict) -> str:
    theme_slug = entry["theme"].lower().replace(" / ", "-").replace(" ", "-")
    return (
        f"{entry['iso_date']}-{entry['day_name'].lower()}-{theme_slug}.md"
    )


def render_html(
    entry: dict,
    *,
    filename: str | None = None,
    templates_dir: Path = TEMPLATES_DIR,
) -> str:
    """Render a complete weekday or weekend email without unresolved tokens."""
    template_name = "card.html" if entry["is_weekend"] else "letter.html"
    template = (templates_dir / template_name).read_text(encoding="utf-8")
    day_color, day_color_tint = DAY_COLORS[entry["day_name"]]
    substitutions = {
        "{{SUBJECT}}": entry["subject"],
        "{{MASTHEAD}}": build_masthead(entry),
        "{{DAY_COLOR}}": day_color,
        "{{DAY_COLOR_TINT}}": day_color_tint,
        "{{QUOTE_1}}": entry["quote_1"],
        "{{QUOTE_2}}": entry["quote_2"],
        "{{QUOTE_3}}": entry["quote_3"],
        "{{OPENER_FRAMING}}": entry["opener_framing"],
        "{{METHOD_FRAMING}}": entry["method_framing"],
        "{{MINDSET_FRAMING}}": entry["mindset_framing"],
        "{{ACTION_CALL}}": entry["action_call"],
        "{{CLOSING_PUNCH}}": entry["closing_punch"],
        "{{SOURCE_TITLES}}": entry["source_titles_joined"],
        "{{FILENAME}}": filename or archive_filename(entry),
    }
    html = template
    for token, value in substitutions.items():
        html = html.replace(token, value)
    if "{{" in html:
        raise RuntimeError(f"Unresolved template token in {template_name}")
    return html


def build_masthead(entry: dict) -> str:
    day_name = entry["day_name"]
    day_n = entry["day_n"]
    is_milestone = entry["is_milestone"]
    iso_date = entry["iso_date"]

    d = date.fromisoformat(iso_date)
    formatted = d.strftime("%B %-d, %Y")

    if entry["is_weekend"]:
        masthead = f"{day_name[:3].upper()} · {formatted.upper()}"
        if is_milestone:
            masthead += f" · DAY {day_n} OF PRACTICE"
    else:
        masthead = f"{day_name} · {formatted}"
        if is_milestone:
            masthead += f" · Day {day_n} of practice"
    return masthead


def build_plain(e: dict, filename: str) -> str:
    return (
        f'> "{e["quote_1"]}"\n\n'
        f'{e["opener_framing"]}\n\n'
        f'**The method.**\n\n'
        f'> "{e["quote_2"]}"\n\n'
        f'{e["method_framing"]}\n\n'
        f'**The mindset.**\n\n'
        f'> "{e["quote_3"]}"\n\n'
        f'{e["mindset_framing"]}\n\n'
        f'**Today\'s call.**\n\n'
        f'{e["action_call"]}\n\n'
        f'{e["closing_punch"]}\n\n'
        f'---\n\n'
        f'Sources: {e["source_titles_joined"]} · Weekly Motivation\n'
        f'Archive: archive/{filename}\n'
    )


def build_markdown(e: dict, today: str) -> str:
    return (
        f'# {e["day_name"]} {today} · {e["theme"]}\n\n'
        f'> "{e["quote_1"]}"\n\n'
        f'{e["opener_framing"]}\n\n'
        f'## The method\n\n'
        f'> "{e["quote_2"]}"\n\n'
        f'{e["method_framing"]}\n\n'
        f'## The mindset\n\n'
        f'> "{e["quote_3"]}"\n\n'
        f'{e["mindset_framing"]}\n\n'
        f'## Today\'s call\n\n'
        f'{e["action_call"]}\n\n'
        f'{e["closing_punch"]}\n\n'
        f'---\n\n'
        f'**Sources:** {e["source_titles_joined"]} · Weekly Motivation notebook\n'
    )


if __name__ == "__main__":
    sys.exit(main())

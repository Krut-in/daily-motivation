"""Deterministic, evergreen motivation-email composition.

The content bank is deliberately finite and versioned.  Composition combines
four atomic blocks from records for the target weekday; no network service,
clock, or random source participates in selection.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
CONTENT_BANK_PATH = ROOT / "data" / "content_bank.json"

START_DATE = date(2026, 5, 8)
CONTENT_BANK_VERSION = 1
MILESTONE_PREFIXES = {
    7: "Day 7. One full week of mornings shaped by intent.",
    30: "Day 30. A month of practice has compounded into something.",
    60: (
        "Day 60. The practice has lasted long enough to stop being an idea "
        "and start becoming a system."
    ),
    100: "Day 100. The ritual has its own gravity now.",
    365: "Day 365. One full year of mornings. The discipline has become you.",
}

WEEKDAY_THEMES = {
    "Monday": "Discipline",
    "Tuesday": "Focus",
    "Wednesday": "Grind",
    "Thursday": "Belief",
    "Friday": "Outwork / Win",
    "Saturday": "Identity",
    "Sunday": "Resilience",
}

EXPECTED_WEEKDAY_COUNTS = {
    "Monday": 7,
    "Tuesday": 8,
    "Wednesday": 8,
    "Thursday": 8,
    "Friday": 8,
    "Saturday": 8,
    "Sunday": 9,
}

EXPECTED_EXCLUDED_ORIGIN_DATES = (
    "2026-05-14",
    "2026-06-06",
    "2026-07-03",
    "2026-07-06",
)

# Changing record order changes the date-to-content mapping.  A bank update
# must therefore bump CONTENT_BANK_VERSION and intentionally replace this
# digest; editing only the JSON cannot silently remap future emails.
EXPECTED_RECORD_ORDER_SHA256 = (
    "51430ff2de26091ff83d82759538d610ff79474b13b5f7877e145a4790cff70a"
)
EXPECTED_CONTENT_BANK_SHA256 = (
    "4da9c5144678f909c615ba283bd4bb766c004d62580827cb156136b318c4232e"
)

_TOP_LEVEL_KEYS = {
    "version",
    "practice_epoch",
    "source_snapshots",
    "excluded_origin_dates",
    "records",
}
_RECORD_KEYS = {
    "id",
    "origin_date",
    "weekday",
    "theme",
    "hook",
    "method",
    "mindset",
    "action",
}
_BLOCK_KEYS = {
    "hook": {"subject_suffix", "quote", "framing", "source_title", "closing_punch"},
    "method": {"quote", "framing", "source_title"},
    "mindset": {"quote", "framing", "source_title"},
    "action": {"action_call"},
}


def compose_entry(target_date: date) -> dict[str, Any]:
    """Compose the renderer-compatible entry for ``target_date``.

    Dates before the practice epoch are invalid.  A ``datetime`` is rejected
    even though it subclasses ``date`` so callers must make timezone/date
    selection explicit before crossing this pure interface.
    """

    if isinstance(target_date, datetime) or not isinstance(target_date, date):
        raise TypeError("target_date must be a datetime.date")
    if target_date < START_DATE:
        raise ValueError(
            f"target_date {target_date.isoformat()} predates practice epoch "
            f"{START_DATE.isoformat()}"
        )

    day_name = target_date.strftime("%A")
    records = _RECORDS_BY_WEEKDAY[day_name]
    size = len(records)
    week_index = (target_date - START_DATE).days // 7
    period = size**4
    step = 1 + 2 * size + 3 * size**2 + 4 * size**3
    state = week_index * step % period

    indices = tuple((state // size**power) % size for power in range(4))
    hook = records[indices[0]]["hook"]
    method = records[indices[1]]["method"]
    mindset = records[indices[2]]["mindset"]
    action = records[indices[3]]["action"]

    day_n = (target_date - START_DATE).days + 1
    milestone_prefix = MILESTONE_PREFIXES.get(day_n)
    subject_prefix = f"{day_name} Fuel · "
    opener_framing = hook["framing"]
    if milestone_prefix is not None:
        subject_prefix += f"Day {day_n} · "
        opener_framing = f"{milestone_prefix} {opener_framing}"

    source_titles = _dedupe_preserving_order(
        (hook["source_title"], method["source_title"], mindset["source_title"])
    )

    return {
        "iso_date": target_date.isoformat(),
        "day_name": day_name,
        "theme": WEEKDAY_THEMES[day_name],
        "is_weekend": day_name in {"Saturday", "Sunday"},
        "is_milestone": milestone_prefix is not None,
        "day_n": day_n,
        "subject": f'{subject_prefix}{hook["subject_suffix"]}',
        "quote_1": hook["quote"],
        "quote_2": method["quote"],
        "quote_3": mindset["quote"],
        "opener_framing": opener_framing,
        "method_framing": method["framing"],
        "mindset_framing": mindset["framing"],
        "action_call": action["action_call"],
        "closing_punch": hook["closing_punch"],
        "source_titles_joined": " · ".join(source_titles),
    }


def _dedupe_preserving_order(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _load_content_bank() -> dict[str, list[dict[str, Any]]]:
    try:
        bank = json.loads(CONTENT_BANK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load content bank: {exc}") from exc

    if set(bank) != _TOP_LEVEL_KEYS:
        raise RuntimeError("Content bank has an unexpected top-level schema")
    if bank["version"] != CONTENT_BANK_VERSION:
        raise RuntimeError(
            f'Unsupported content bank version {bank["version"]!r}; '
            f"expected {CONTENT_BANK_VERSION}"
        )
    if bank["practice_epoch"] != START_DATE.isoformat():
        raise RuntimeError("Content bank practice epoch does not match START_DATE")
    if tuple(bank["excluded_origin_dates"]) != EXPECTED_EXCLUDED_ORIGIN_DATES:
        raise RuntimeError("Content bank exclusion list changed unexpectedly")

    canonical_bank = json.dumps(
        bank,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if hashlib.sha256(canonical_bank).hexdigest() != EXPECTED_CONTENT_BANK_SHA256:
        raise RuntimeError(
            "Content bank changed without a versioned canonical-digest update"
        )

    records = bank["records"]
    if not isinstance(records, list) or len(records) != 56:
        raise RuntimeError("Content bank must contain exactly 56 records")

    record_ids: list[str] = []
    origin_dates: list[str] = []
    grouped = {weekday: [] for weekday in WEEKDAY_THEMES}

    for record in records:
        if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
            raise RuntimeError("Content bank record has an unexpected schema")

        record_id = record["id"]
        origin_date = record["origin_date"]
        weekday = record["weekday"]
        theme = record["theme"]
        if not all(
            isinstance(value, str) and value
            for value in (record_id, origin_date, weekday, theme)
        ):
            raise RuntimeError("Content bank record metadata must be non-empty strings")
        try:
            parsed_origin = date.fromisoformat(origin_date)
        except ValueError as exc:
            raise RuntimeError(f"Invalid content origin date {origin_date!r}") from exc
        if record_id != origin_date:
            raise RuntimeError("Content record ID must equal its stable origin date")
        if weekday not in WEEKDAY_THEMES:
            raise RuntimeError(f"Unknown content weekday {weekday!r}")
        if parsed_origin.strftime("%A") != weekday:
            raise RuntimeError(f"Origin date {origin_date} is not a {weekday}")
        if WEEKDAY_THEMES[weekday] != theme:
            raise RuntimeError(f"Unexpected theme {theme!r} for {weekday}")

        for block_name, expected_keys in _BLOCK_KEYS.items():
            block = record[block_name]
            if not isinstance(block, dict) or set(block) != expected_keys:
                raise RuntimeError(
                    f"Content record {record_id} has an invalid {block_name} block"
                )
            if not all(isinstance(value, str) and value for value in block.values()):
                raise RuntimeError(
                    f"Content record {record_id} has an empty {block_name} field"
                )

        record_ids.append(record_id)
        origin_dates.append(origin_date)
        grouped[weekday].append(record)

    if len(set(record_ids)) != len(record_ids):
        raise RuntimeError("Content bank record IDs must be unique")
    if len(set(origin_dates)) != len(origin_dates):
        raise RuntimeError("Content bank origin dates must be unique")
    if Counter(record["weekday"] for record in records) != Counter(EXPECTED_WEEKDAY_COUNTS):
        raise RuntimeError("Content bank weekday counts changed unexpectedly")

    order_digest = hashlib.sha256("|".join(record_ids).encode("utf-8")).hexdigest()
    if order_digest != EXPECTED_RECORD_ORDER_SHA256:
        raise RuntimeError(
            "Content bank record order changed without a versioned code update"
        )

    return grouped


_RECORDS_BY_WEEKDAY = _load_content_bank()


__all__ = [
    "CONTENT_BANK_VERSION",
    "EXPECTED_CONTENT_BANK_SHA256",
    "MILESTONE_PREFIXES",
    "START_DATE",
    "compose_entry",
]

import hashlib
import json
import unittest
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import evergreen_content

from evergreen_content import (
    CONTENT_BANK_VERSION,
    MILESTONE_PREFIXES,
    START_DATE,
    compose_entry,
)


ROOT = Path(__file__).parents[1]
CONTENT_BANK_PATH = ROOT / "data" / "content_bank.json"

EXPECTED_WEEKDAY_COUNTS = {
    "Monday": 7,
    "Tuesday": 8,
    "Wednesday": 8,
    "Thursday": 8,
    "Friday": 8,
    "Saturday": 8,
    "Sunday": 9,
}
EXPECTED_THEMES = {
    "Monday": "Discipline",
    "Tuesday": "Focus",
    "Wednesday": "Grind",
    "Thursday": "Belief",
    "Friday": "Outwork / Win",
    "Saturday": "Identity",
    "Sunday": "Resilience",
}
EXCLUDED_ORIGIN_DATES = {
    "2026-05-14",
    "2026-06-06",
    "2026-07-03",
    "2026-07-06",
}


class ContentBankMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = json.loads(CONTENT_BANK_PATH.read_text(encoding="utf-8"))
        cls.records = cls.bank["records"]

    def test_migration_retains_exactly_56_evergreen_records(self):
        self.assertEqual(self.bank["version"], CONTENT_BANK_VERSION)
        self.assertEqual(self.bank["practice_epoch"], "2026-05-08")
        self.assertEqual(
            self.bank["source_snapshots"],
            ["4dd1641:data/queue.json", "2635457:data/queue.json"],
        )
        self.assertEqual(
            self.bank["excluded_origin_dates"],
            ["2026-05-14", "2026-06-06", "2026-07-03", "2026-07-06"],
        )
        self.assertEqual(len(self.records), 56)
        self.assertEqual(
            Counter(record["weekday"] for record in self.records),
            Counter(EXPECTED_WEEKDAY_COUNTS),
        )
        origin_dates = [record["origin_date"] for record in self.records]
        self.assertTrue(EXCLUDED_ORIGIN_DATES.isdisjoint(origin_dates))
        self.assertEqual(origin_dates, sorted(origin_dates))

    def test_records_have_unique_stable_ids_and_atomic_block_schema(self):
        expected_record_keys = {
            "id",
            "origin_date",
            "weekday",
            "theme",
            "hook",
            "method",
            "mindset",
            "action",
        }
        expected_block_keys = {
            "hook": {
                "subject_suffix",
                "quote",
                "framing",
                "source_title",
                "closing_punch",
            },
            "method": {"quote", "framing", "source_title"},
            "mindset": {"quote", "framing", "source_title"},
            "action": {"action_call"},
        }

        ids = []
        for record in self.records:
            with self.subTest(record=record["id"]):
                self.assertEqual(set(record), expected_record_keys)
                self.assertEqual(record["id"], record["origin_date"])
                self.assertEqual(
                    date.fromisoformat(record["origin_date"]).strftime("%A"),
                    record["weekday"],
                )
                self.assertEqual(record["theme"], EXPECTED_THEMES[record["weekday"]])
                for block_name, expected_keys in expected_block_keys.items():
                    block = record[block_name]
                    self.assertEqual(set(block), expected_keys)
                    self.assertTrue(
                        all(isinstance(value, str) and value for value in block.values())
                    )
                ids.append(record["id"])

        self.assertEqual(len(ids), len(set(ids)))

    def test_quotes_keep_their_historical_source_attribution(self):
        by_id = {record["id"]: record for record in self.records}

        first_snapshot_record = by_id["2026-05-09"]
        self.assertEqual(
            (
                first_snapshot_record["hook"]["quote"],
                first_snapshot_record["hook"]["source_title"],
            ),
            (
                "Do something that sucks every single day of your life. "
                "That's how you grow.",
                "BECOME A SAVAGE",
            ),
        )
        second_snapshot_record = by_id["2026-06-11"]
        self.assertEqual(
            (
                second_snapshot_record["mindset"]["quote"],
                second_snapshot_record["mindset"]["source_title"],
            ),
            (
                "Before the result changes, the sentence you repeat to "
                "yourself has to change.",
                "I CAN DO THIS",
            ),
        )

    def test_complete_migrated_bank_digest_is_frozen(self):
        canonical_bank = json.dumps(
            self.bank,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        self.assertEqual(
            hashlib.sha256(canonical_bank).hexdigest(),
            evergreen_content.EXPECTED_CONTENT_BANK_SHA256,
        )


class ComposeEntryTests(unittest.TestCase):
    def test_practice_epoch_composes_day_one_for_renderer(self):
        entry = compose_entry(date(2026, 5, 8))

        self.assertEqual(entry["iso_date"], "2026-05-08")
        self.assertEqual(entry["day_name"], "Friday")
        self.assertEqual(entry["theme"], "Outwork / Win")
        self.assertEqual(entry["day_n"], 1)
        self.assertFalse(entry["is_weekend"])
        self.assertFalse(entry["is_milestone"])
        self.assertEqual(
            set(entry),
            {
                "iso_date",
                "day_name",
                "theme",
                "is_weekend",
                "is_milestone",
                "day_n",
                "subject",
                "quote_1",
                "quote_2",
                "quote_3",
                "opener_framing",
                "method_framing",
                "mindset_framing",
                "action_call",
                "closing_punch",
                "source_titles_joined",
            },
        )
        self.assertEqual(entry["subject"], "Friday Fuel · The price either way")

    def test_dates_before_epoch_and_ambiguous_input_types_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "predates practice epoch"):
            compose_entry(date(2026, 5, 7))
        with self.assertRaisesRegex(TypeError, "datetime.date"):
            compose_entry(datetime(2026, 5, 8, 8, 0))
        with self.assertRaisesRegex(TypeError, "datetime.date"):
            compose_entry("2026-05-08")

    def test_july_12_resumes_naturally_as_sunday_day_66(self):
        entry = compose_entry(date(2026, 7, 12))

        self.assertEqual(entry["iso_date"], "2026-07-12")
        self.assertEqual(entry["day_name"], "Sunday")
        self.assertEqual(entry["theme"], "Resilience")
        self.assertEqual(entry["day_n"], 66)
        self.assertTrue(entry["is_weekend"])
        self.assertFalse(entry["is_milestone"])
        self.assertEqual(entry["subject"], "Sunday Fuel · Tough times don't stay")
        self.assertEqual(
            entry["quote_1"],
            "Tough times have not come to stay. They have come to pass.",
        )
        self.assertEqual(
            entry["quote_2"],
            "The moment of extreme adversity is the best moment for audacity.",
        )
        self.assertEqual(
            entry["quote_3"],
            "Your character is put to the test when your back is against the wall.",
        )
        self.assertEqual(
            entry["source_titles_joined"],
            "I WILL NEVER QUIT · I MUST KEEP GOING · DON'T QUIT",
        )

    def test_day_number_counts_calendar_days_even_when_delivery_is_missed(self):
        self.assertEqual(compose_entry(date(2026, 7, 10))["day_n"], 64)
        self.assertEqual(compose_entry(date(2026, 7, 11))["day_n"], 65)
        self.assertEqual(compose_entry(date(2026, 7, 12))["day_n"], 66)

    def test_milestones_decorate_selected_evergreen_content(self):
        milestone_dates = {
            7: date(2026, 5, 14),
            30: date(2026, 6, 6),
            60: date(2026, 7, 6),
            100: date(2026, 8, 15),
            365: date(2027, 5, 7),
        }
        expected_suffixes = {
            7: "The other voice",
            30: "Private reps count twice",
            60: "Nothing changes if nothing changes",
            100: "Keep faith with yourself",
            365: "Finish like it counts",
        }

        for day_n, target_date in milestone_dates.items():
            with self.subTest(day_n=day_n):
                entry = compose_entry(target_date)
                self.assertTrue(entry["is_milestone"])
                self.assertEqual(entry["day_n"], day_n)
                self.assertEqual(
                    entry["subject"],
                    f"{entry['day_name']} Fuel · Day {day_n} · "
                    f"{expected_suffixes[day_n]}",
                )
                self.assertTrue(
                    entry["opener_framing"].startswith(
                        f"{MILESTONE_PREFIXES[day_n]} "
                    )
                )

        self.assertEqual(
            compose_entry(date(2026, 6, 6))["closing_punch"],
            "Identity is built in rooms with no applause.",
        )

    def test_source_titles_are_deduplicated_in_stable_order(self):
        entry = compose_entry(date(2026, 5, 15))

        self.assertEqual(
            entry["source_titles_joined"],
            "I WILL WIN · PROVE EVERYBODY WRONG",
        )

    def test_composition_is_deterministic_for_far_future_and_calendar_boundaries(self):
        far_future = date(2125, 12, 31)
        self.assertEqual(compose_entry(far_future), compose_entry(far_future))
        self.assertEqual(compose_entry(far_future)["day_n"], 36_397)

        boundary_days = {
            date(2028, 2, 28): 662,
            date(2028, 2, 29): 663,
            date(2028, 3, 1): 664,
            date(2027, 3, 13): 310,
            date(2027, 3, 14): 311,
            date(2027, 11, 7): 549,
            date(2027, 11, 8): 550,
        }
        for target_date, expected_day_n in boundary_days.items():
            with self.subTest(target_date=target_date):
                self.assertEqual(compose_entry(target_date)["day_n"], expected_day_n)

    def test_every_renderer_field_is_populated_without_placeholders(self):
        for offset in range(7):
            entry = compose_entry(START_DATE + timedelta(days=offset))
            with self.subTest(day=entry["day_name"]):
                for key, value in entry.items():
                    if isinstance(value, str):
                        self.assertTrue(value)
                        self.assertNotIn("{{", value)

    def test_affine_rotation_visits_all_29442_combinations_once(self):
        first_dates = {
            "Monday": date(2026, 5, 11),
            "Tuesday": date(2026, 5, 12),
            "Wednesday": date(2026, 5, 13),
            "Thursday": date(2026, 5, 14),
            "Friday": date(2026, 5, 8),
            "Saturday": date(2026, 5, 9),
            "Sunday": date(2026, 5, 10),
        }
        total_states = 0

        for weekday, size in EXPECTED_WEEKDAY_COUNTS.items():
            period = size**4
            entries = [
                compose_entry(first_dates[weekday] + timedelta(weeks=week_index))
                for week_index in range(period)
            ]
            signatures = [
                (
                    entry["quote_1"],
                    entry["quote_2"],
                    entry["quote_3"],
                    entry["action_call"],
                )
                for entry in entries
            ]

            with self.subTest(weekday=weekday):
                self.assertEqual(len(set(signatures)), period)
                for position in range(4):
                    usage = Counter(signature[position] for signature in signatures)
                    self.assertEqual(len(usage), size)
                    self.assertEqual(set(usage.values()), {size**3})
                    for week_index in range(period):
                        self.assertNotEqual(
                            signatures[week_index][position],
                            signatures[(week_index + 1) % period][position],
                        )
            total_states += period

        self.assertEqual(total_states, 29_442)


if __name__ == "__main__":
    unittest.main()

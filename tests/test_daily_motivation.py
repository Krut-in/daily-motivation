import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import daily_motivation


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "daily_motivation.py"
CONFIRM_LIVE_SCRIPT = ROOT / "scripts" / "confirm_live_send.sh"


class RecordingSmtp:
    messages: list[tuple[str, list[str], str]] = []

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def starttls(self, *, context) -> None:
        self.tls_context = context

    def login(self, user: str, password: str) -> None:
        self.credentials = (user, password)

    def sendmail(self, sender: str, recipients: list[str], message: str) -> None:
        self.messages.append((sender, recipients, message))


class FailingSmtp(RecordingSmtp):
    def sendmail(self, sender: str, recipients: list[str], message: str) -> None:
        raise RuntimeError("SMTP rejected the message")


class DailyMotivationCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_force_date_is_rejected_for_live_delivery(self) -> None:
        result = self.run_cli("--force-date", "2026-07-12")

        self.assertEqual(result.returncode, 2)
        self.assertIn("--force-date requires --dry-run or --verify-delivery", result.stderr)

    def test_skip_guards_option_is_not_available(self) -> None:
        result = self.run_cli("--dry-run", "--force-date", "2026-07-11", "--skip-guards")

        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --skip-guards", result.stderr)

    def test_manual_live_confirmation_rejects_any_other_value(self) -> None:
        result = subprocess.run(
            ["bash", str(CONFIRM_LIVE_SCRIPT)],
            cwd=ROOT,
            env={"CONFIRMATION": "send today"},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly: SEND TODAY", result.stderr)

    def test_manual_live_confirmation_accepts_exact_phrase(self) -> None:
        result = subprocess.run(
            ["bash", str(CONFIRM_LIVE_SCRIPT)],
            cwd=ROOT,
            env={"CONFIRMATION": "SEND TODAY"},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("confirmed", result.stdout.lower())

    def test_verification_fails_when_required_archive_is_missing(self) -> None:
        result = self.run_cli("--verify-delivery", "--force-date", "2026-07-12")

        self.assertEqual(result.returncode, 1)
        self.assertIn("No delivery archive found for 2026-07-12", result.stderr)

    def test_verification_skips_the_intentionally_unsent_july_11(self) -> None:
        result = self.run_cli("--verify-delivery", "--force-date", "2026-07-11")

        self.assertEqual(result.returncode, 0)
        self.assertIn("Delivery is not required before 2026-07-12", result.stdout)

    def test_dry_run_renders_july_11_without_credentials_or_archive(self) -> None:
        result = self.run_cli("--dry-run", "--force-date", "2026-07-11")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Today:    Saturday 2026-07-11", result.stdout)
        self.assertIn("=== DRY RUN ===", result.stdout)
        self.assertNotIn("{{", result.stdout)

    def test_verification_rejects_a_corrupt_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            (archive_dir / "2026-07-12-sunday-resilience.md").write_text("not an email\n")

            ok, message = daily_motivation.verify_delivery(
                date(2026, 7, 12), archive_dir=archive_dir
            )

        self.assertFalse(ok)
        self.assertIn("invalid", message.lower())

    def test_verification_rejects_an_archive_with_the_wrong_heading(self) -> None:
        markdown = (
            "# Monday 2026-07-12 · Discipline\n\n"
            "## The method\n\nMethod\n\n"
            "## The mindset\n\nMindset\n\n"
            "## Today's call\n\nAction\n\n"
            "**Sources:** Example\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            (archive_dir / "2026-07-12-sunday-resilience.md").write_text(markdown)

            ok, message = daily_motivation.verify_delivery(
                date(2026, 7, 12), archive_dir=archive_dir
            )

        self.assertFalse(ok)
        self.assertIn("invalid", message.lower())

    def test_verification_rejects_empty_sections_in_an_expected_archive(self) -> None:
        target_date = date(2026, 7, 12)
        entry = daily_motivation.compose_entry(target_date)
        markdown = (
            "# Sunday 2026-07-12 · Resilience\n\n"
            "## The method\n\n"
            "## The mindset\n\n"
            "## Today's call\n\n"
            "**Sources:**\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            (archive_dir / daily_motivation.archive_filename(entry)).write_text(markdown)

            ok, message = daily_motivation.verify_delivery(
                target_date, archive_dir=archive_dir
            )

        self.assertFalse(ok)
        self.assertIn("invalid", message.lower())

    def test_verification_accepts_one_complete_archive(self) -> None:
        target_date = date(2026, 7, 12)
        entry = daily_motivation.compose_entry(target_date)
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            archive_path = archive_dir / daily_motivation.archive_filename(entry)
            archive_path.write_text(
                daily_motivation.build_markdown(entry, target_date.isoformat())
            )

            ok, message = daily_motivation.verify_delivery(
                target_date, archive_dir=archive_dir
            )

        self.assertTrue(ok)
        self.assertIn("verified", message.lower())

    def test_verification_rejects_duplicate_archives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            for suffix in ("one", "two"):
                (archive_dir / f"2026-07-12-{suffix}.md").write_text("duplicate\n")

            ok, message = daily_motivation.verify_delivery(
                date(2026, 7, 12), archive_dir=archive_dir
            )

        self.assertFalse(ok)
        self.assertIn("found 2", message)

    def test_live_delivery_skips_the_intentionally_unsent_july_11(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            with (
                patch.object(
                    daily_motivation.smtplib,
                    "SMTP",
                    side_effect=AssertionError("SMTP must not be contacted"),
                ),
                redirect_stdout(output),
            ):
                result = daily_motivation.main(
                    [],
                    now_et=datetime(2026, 7, 11, 8, 0, tzinfo=daily_motivation.ET),
                    archive_dir=Path(temporary_directory),
                )

        self.assertEqual(result, 0)
        self.assertIn("Live delivery starts 2026-07-12", output.getvalue())

    def test_live_delivery_waits_until_730_et(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            with (
                patch.object(
                    daily_motivation.smtplib,
                    "SMTP",
                    side_effect=AssertionError("SMTP must not be contacted"),
                ),
                redirect_stdout(output),
            ):
                result = daily_motivation.main(
                    [],
                    now_et=datetime(2026, 7, 12, 7, 29, tzinfo=daily_motivation.ET),
                    archive_dir=Path(temporary_directory),
                )

        self.assertEqual(result, 0)
        self.assertIn("before delivery window", output.getvalue())

    def test_successful_live_delivery_sends_and_archives_once(self) -> None:
        RecordingSmtp.messages.clear()
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            with (
                patch.object(daily_motivation.smtplib, "SMTP", RecordingSmtp),
                patch.dict(
                    daily_motivation.os.environ,
                    {"GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "secret"},
                    clear=True,
                ),
                redirect_stdout(StringIO()),
            ):
                result = daily_motivation.main(
                    [],
                    now_et=datetime(2026, 7, 12, 8, 0, tzinfo=daily_motivation.ET),
                    archive_dir=archive_dir,
                )
            archives = list(archive_dir.glob("2026-07-12-*.md"))
            archive_content = archives[0].read_text() if archives else ""

        self.assertEqual(result, 0)
        self.assertEqual(len(RecordingSmtp.messages), 1)
        self.assertEqual(len(archives), 1)
        self.assertIn("# Sunday 2026-07-12 · Resilience", archive_content)

    def test_failed_smtp_delivery_does_not_create_an_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            with (
                patch.object(daily_motivation.smtplib, "SMTP", FailingSmtp),
                patch.dict(
                    daily_motivation.os.environ,
                    {"GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "secret"},
                    clear=True,
                ),
                redirect_stdout(StringIO()),
                self.assertRaisesRegex(RuntimeError, "SMTP rejected"),
            ):
                daily_motivation.main(
                    [],
                    now_et=datetime(2026, 7, 12, 8, 0, tzinfo=daily_motivation.ET),
                    archive_dir=archive_dir,
                )

            self.assertEqual(list(archive_dir.glob("2026-07-12-*.md")), [])

    def test_existing_archive_prevents_duplicate_smtp_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_dir = Path(temporary_directory)
            archive_path = archive_dir / "2026-07-12-sunday-resilience.md"
            archive_path.write_text("already sent\n")
            output = StringIO()
            with (
                patch.object(
                    daily_motivation.smtplib,
                    "SMTP",
                    side_effect=AssertionError("SMTP must not be contacted"),
                ),
                redirect_stdout(output),
            ):
                result = daily_motivation.main(
                    [],
                    now_et=datetime(2026, 7, 12, 8, 0, tzinfo=daily_motivation.ET),
                    archive_dir=archive_dir,
                )

        self.assertEqual(result, 0)
        self.assertIn("already sent", output.getvalue())

    def test_weekday_and_weekend_html_render_without_placeholders(self) -> None:
        for target_date in (date(2026, 7, 12), date(2026, 7, 13)):
            entry = daily_motivation.compose_entry(target_date)

            html = daily_motivation.render_html(entry)

            with self.subTest(target_date=target_date):
                self.assertIn(entry["subject"], html)
                self.assertNotIn("{{", html)


if __name__ == "__main__":
    unittest.main()

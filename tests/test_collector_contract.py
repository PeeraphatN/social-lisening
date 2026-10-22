"""Black-box tests for the approved Facebook collector public contract."""

import json
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from facebook_collector import CollectionUnavailable
from facebook_collector.__main__ import main


REPO_ROOT = Path(__file__).resolve().parents[1]


class CollectorCliContractTests(unittest.TestCase):
    def test_cli_exists_and_rejects_conflicting_input_modes(self):
        """The CLI requires exactly one input mode."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_file = root / "urls.txt"
            input_file.write_text(
                "https://www.facebook.com/synthetic/posts/123\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "facebook_collector",
                    "collect",
                    "--url",
                    "https://www.facebook.com/synthetic/posts/456",
                    "--input-file",
                    str(input_file),
                    "--output-dir",
                    str(root / "output"),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

        diagnostic = completed.stdout + completed.stderr
        self.assertNotIn(
            "No module named facebook_collector",
            diagnostic,
            "the contracted public CLI must exist",
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_valid_collect_without_the_pinned_dependency_reports_install_action(self):
        """A valid command without Playwright must fail before creating output."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_dir = root / "output"
            stderr = io.StringIO()
            with patch(
                "facebook_collector.collector._launch_browser",
                side_effect=CollectionUnavailable("install playwright"),
            ), redirect_stderr(stderr):
                exit_code = main([
                    "collect", "--url", "https://www.facebook.com/share/p/19TTvcsmZ8/",
                    "--output-dir", str(output_dir),
                ])
            self.assertFalse(output_dir.exists())
        self.assertEqual(exit_code, 1)
        self.assertIn("install playwright", stderr.getvalue().lower())

    def test_utf8_input_file_ignores_blank_lines_and_preserves_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_file = root / "urls.txt"
            input_file.write_text("not a URL\n\nอีก URL ที่ไม่ถูกต้อง\n", encoding="utf-8")
            output_dir = root / "output"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "facebook_collector",
                    "collect",
                    "--input-file",
                    str(input_file),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run_directory = next((output_dir / "runs").iterdir())
            results = json.loads((run_directory / "results.json").read_text(encoding="utf-8"))

        self.assertEqual(
            [outcome["input_url"] for outcome in results["outcomes"]],
            ["not a URL", "อีก URL ที่ไม่ถูกต้อง"],
        )

    def test_repeated_url_values_preserve_input_order(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "facebook_collector",
                    "collect",
                    "--url",
                    "first invalid URL",
                    "--url",
                    "second invalid URL",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run_directory = next((output_dir / "runs").iterdir())
            results = json.loads((run_directory / "results.json").read_text(encoding="utf-8"))

        self.assertEqual(
            [outcome["input_url"] for outcome in results["outcomes"]],
            ["first invalid URL", "second invalid URL"],
        )

    def test_more_than_ten_unique_urls_exits_two_without_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            command = [sys.executable, "-m", "facebook_collector", "collect"]
            for index in range(11):
                command.extend(("--url", f"invalid URL {index}"))
            command.extend(("--output-dir", str(output_dir)))

            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertFalse(output_dir.exists())

    def test_invalid_input_writes_a_trustworthy_result_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "facebook_collector",
                    "collect",
                    "--url",
                    "not a URL",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            run_directories = list((output_dir / "runs").iterdir())
            self.assertEqual(len(run_directories), 1)
            results = json.loads(
                (run_directories[0] / "results.json").read_text(encoding="utf-8")
            )

        self.assertEqual(results["outcomes"][0]["status"], "invalid_input")
        self.assertEqual(results["outcomes"][0]["reason"], "malformed_url")


if __name__ == "__main__":
    unittest.main()

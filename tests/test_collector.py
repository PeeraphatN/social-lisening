import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import call, patch

from facebook_collector import CollectionUnavailable, collect_posts
from facebook_collector.__main__ import main
from facebook_collector.model import BatchValidationError
from facebook_collector.offline import build_synthetic_outcome


VALID_URL = "https://www.facebook.com/share/p/19TTvcsmZ8/"
SYNTHETIC_URL = "https://www.facebook.com/900000007654321/posts/900000001234567/"
OFFLINE_FIXTURE = Path(__file__).parent / "e2e" / "fixtures" / "single-collected.json"
IDENTITY_UNVERIFIED_URL = "https://www.facebook.com/900000007654321/posts/900000001234568/"
BLOCKED_URL = "https://www.facebook.com/900000007654321/posts/900000001234569/"
RETRY_URL = "https://www.facebook.com/900000007654321/posts/900000001234570/"
HTTP_URL = "https://www.facebook.com/900000007654321/posts/900000001234571/"
PHOTO_URL = "https://www.facebook.com/photo/?fbid=1649985453249994"
GROUP_LISTING_URL = "https://www.facebook.com/groups/100/?multi_permalinks=200"
GROUP_EXPLICIT_URL = "https://www.facebook.com/groups/100/posts/200/"


class CollectorPublicCoreTests(unittest.TestCase):
    def mixed_fixture(self, directory: str) -> Path:
        fixture = json.loads(OFFLINE_FIXTURE.read_text(encoding="utf-8"))
        fixture["synthetic_outcomes"] = [
            {
                "submitted_url": IDENTITY_UNVERIFIED_URL,
                "status": "identity_unverified",
            },
            {"submitted_url": BLOCKED_URL, "status": "blocked"},
        ]
        path = Path(directory) / "mixed-capture.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        return path

    def synthetic_fixture(self, directory: str, url: str, **outcome: object) -> Path:
        fixture = json.loads(OFFLINE_FIXTURE.read_text(encoding="utf-8"))
        fixture["synthetic_outcomes"] = [{"submitted_url": url, **outcome}]
        path = Path(directory) / "synthetic-capture.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        return path

    def test_offline_public_api_retries_only_retriable_failures_with_bounded_waits(self):
        cases = (
            ("transport_timeout", {"status": "timeout"}),
            ("http_408", {"status": "http", "http_status": 408}),
            ("http_504", {"status": "http", "http_status": 504}),
        )
        for name, synthetic_outcome in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                fixture = self.synthetic_fixture(directory, RETRY_URL, **synthetic_outcome)
                with patch.dict(
                    os.environ,
                    {
                        "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                        "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                    },
                ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
                    "socket.socket.connect", side_effect=AssertionError("network attempted")
                ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")), patch(
                    "facebook_collector.collector.build_synthetic_outcome",
                    wraps=build_synthetic_outcome,
                ) as attempt, patch("facebook_collector.model.time.sleep") as sleep:
                    results = collect_posts([RETRY_URL, SYNTHETIC_URL], Path(directory) / "output")

                self.assertEqual(attempt.call_count, 4)
                self.assertEqual(
                    attempt.call_args_list,
                    [
                        call(RETRY_URL, synthetic_outcome, attempt_timeout_seconds=30),
                        call(RETRY_URL, synthetic_outcome, attempt_timeout_seconds=30),
                        call(RETRY_URL, synthetic_outcome, attempt_timeout_seconds=30),
                        call(RETRY_URL, synthetic_outcome, attempt_timeout_seconds=30),
                    ],
                )
                self.assertEqual(sleep.call_args_list, [call(2), call(4), call(8)])
                self.assertEqual(
                    [(outcome["status"], outcome["reason"]) for outcome in results["outcomes"]],
                    [("timeout", "transport_timeout"), ("collected", None)],
                )
                self.assertFalse(results["outcomes"][0]["latest_updated"])

    def test_offline_public_api_classifies_http_and_block_walls_without_retry(self):
        cases = (
            ({"status": "http", "http_status": 401}, "blocked", "blocked", True),
            ({"status": "http", "http_status": 403}, "blocked", "blocked", True),
            ({"status": "http", "http_status": 429}, "blocked", "blocked", True),
            ({"status": "challenge"}, "blocked", "blocked", True),
            ({"status": "login_wall"}, "blocked", "blocked", True),
            ({"status": "http", "http_status": 404}, "error", "post_unavailable", False),
            ({"status": "http", "http_status": 410}, "error", "post_unavailable", False),
            ({"status": "http", "http_status": 500}, "error", "facebook_server_error", False),
            ({"status": "http", "http_status": 503}, "error", "facebook_server_error", False),
            ({"status": "http", "http_status": 505}, "error", "facebook_server_error", False),
            ({"status": "http", "http_status": 418}, "error", "http_error", False),
        )
        for synthetic_outcome, status, reason, stops in cases:
            with self.subTest(synthetic_outcome=synthetic_outcome), tempfile.TemporaryDirectory() as directory:
                fixture = self.synthetic_fixture(directory, HTTP_URL, **synthetic_outcome)
                with patch.dict(
                    os.environ,
                    {
                        "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                        "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                    },
                ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
                    "socket.socket.connect", side_effect=AssertionError("network attempted")
                ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")), patch(
                    "facebook_collector.model.time.sleep"
                ) as sleep:
                    results = collect_posts([HTTP_URL, SYNTHETIC_URL], Path(directory) / "output")

                sleep.assert_not_called()
                self.assertEqual(results["outcomes"][0]["status"], status)
                self.assertEqual(results["outcomes"][0]["reason"], reason)
                self.assertFalse(results["outcomes"][0]["latest_updated"])
                self.assertEqual(results["run_status"], "stopped" if stops else "completed")
                self.assertEqual(results["stop_reason"], "blocked" if stops else None)
                self.assertEqual(
                    results["outcomes"][1]["status"], "not_attempted" if stops else "collected"
                )

    def test_offline_public_core_collects_mixed_batch_in_order_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.mixed_fixture(directory)
            with patch.dict(
                os.environ,
                {
                    "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                    "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                },
            ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
                "socket.socket.connect", side_effect=AssertionError("network attempted")
            ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")), patch(
                "time.sleep"
            ) as sleep:
                results = collect_posts(
                    [SYNTHETIC_URL, "not a URL", IDENTITY_UNVERIFIED_URL, SYNTHETIC_URL],
                    Path(directory) / "output",
                )

        sleep.assert_not_called()

        self.assertEqual(results["run_status"], "completed")
        self.assertIsNone(results["stop_reason"])
        self.assertEqual(
            [(outcome["input_index"], outcome["status"], outcome["reason"])
            for outcome in results["outcomes"]
            ],
            [
                (0, "collected", None),
                (1, "invalid_input", "malformed_url"),
                (2, "error", "identity_unverified"),
                (3, "collected", None),
            ],
        )
        self.assertEqual(results["outcomes"][3]["duplicate_of"], 0)
        self.assertFalse(results["outcomes"][3]["latest_updated"])

    def test_offline_public_core_stops_after_synthetic_block(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.mixed_fixture(directory)
            with patch.dict(
                os.environ,
                {
                    "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                    "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                },
            ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
                "socket.socket.connect", side_effect=AssertionError("network attempted")
            ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")):
                results = collect_posts(
                    [SYNTHETIC_URL, BLOCKED_URL, IDENTITY_UNVERIFIED_URL],
                    Path(directory) / "output",
                )

        self.assertEqual(results["run_status"], "stopped")
        self.assertEqual(results["stop_reason"], "blocked")
        self.assertEqual(
            [(outcome["status"], outcome["reason"]) for outcome in results["outcomes"]],
            [("collected", None), ("blocked", "blocked"), ("not_attempted", "blocked")],
        )
        self.assertIsNone(results["outcomes"][2]["attempted_at"])
        self.assertIsNone(results["outcomes"][2]["post_identity"])

    def test_cli_delegates_the_offline_seam_to_the_public_core(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(OFFLINE_FIXTURE),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
        ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
            "socket.socket.connect", side_effect=AssertionError("network attempted")
        ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")), patch(
            "facebook_collector.collect_posts", wraps=collect_posts
        ) as collect:
            output_dir = Path(directory) / "output"

            exit_code = main(
                ["collect", "--url", SYNTHETIC_URL, "--output-dir", str(output_dir)]
            )

            self.assertEqual(exit_code, 0)
            collect.assert_called_once_with([SYNTHETIC_URL], output_dir, log=False)

    def test_offline_cli_accepts_repeated_urls_and_utf8_input_file_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.mixed_fixture(directory)
            input_file = Path(directory) / "urls.txt"
            input_file.write_text(
                f"\n{SYNTHETIC_URL}\n\nnot a URL\n{IDENTITY_UNVERIFIED_URL}\n{SYNTHETIC_URL}\n",
                encoding="utf-8",
            )
            cases = [
                ["collect", "--input-file", str(input_file)],
                [
                    "collect",
                    "--url",
                    SYNTHETIC_URL,
                    "--url",
                    "not a URL",
                    "--url",
                    IDENTITY_UNVERIFIED_URL,
                    "--url",
                    SYNTHETIC_URL,
                ],
            ]
            expected_inputs = [SYNTHETIC_URL, "not a URL", IDENTITY_UNVERIFIED_URL, SYNTHETIC_URL]
            for index, arguments in enumerate(cases):
                with self.subTest(arguments=arguments), patch.dict(
                    os.environ,
                    {
                        "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                        "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                    },
                ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
                    "socket.socket.connect", side_effect=AssertionError("network attempted")
                ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")), patch(
                    "facebook_collector.collect_posts", wraps=collect_posts
                ) as collect:
                    output_dir = Path(directory) / f"output-{index}"
                    exit_code = main([*arguments, "--output-dir", str(output_dir)])

                    self.assertEqual(exit_code, 0)
                    collect.assert_called_once_with(expected_inputs, output_dir, log=False)
                    run_directory = next((output_dir / "runs").iterdir())
                    written = json.loads((run_directory / "results.json").read_text(encoding="utf-8"))
                    self.assertEqual(
                        [outcome["status"] for outcome in written["outcomes"]],
                        ["collected", "invalid_input", "error", "collected"],
                    )
                    self.assertEqual(written["outcomes"][-1]["duplicate_of"], 0)

    def test_non_offline_cli_keeps_input_file_behavior_for_future_slices(self):
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "urls.txt"
            input_file.write_text(SYNTHETIC_URL + "\n\n", encoding="utf-8")
            output_dir = Path(directory) / "output"

            with patch.dict(os.environ, {}, clear=True), patch(
                "facebook_collector.collect_posts", return_value={}
            ) as collect:
                exit_code = main(
                    [
                        "collect",
                        "--input-file",
                        str(input_file),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            collect.assert_called_once_with([SYNTHETIC_URL], output_dir, log=False)

    def test_supported_offline_capture_uses_public_core_and_returns_canonical_artifacts(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(OFFLINE_FIXTURE),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
        ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
            "socket.socket.connect", side_effect=AssertionError("network attempted")
        ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")):
            output_dir = Path(directory) / "output"

            results = collect_posts([SYNTHETIC_URL], output_dir)

            run_directory = output_dir / "runs" / results["run_id"]
            written = json.loads((run_directory / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(results, written)
            self.assertEqual(results["schema_version"], "1")
            self.assertEqual(results["outcomes"][0]["status"], "collected")
            self.assertTrue(results["outcomes"][0]["latest_updated"])
            self.assertTrue((run_directory / "posts.csv").exists())
            self.assertTrue((output_dir / "posts-latest.csv").exists())

    def test_offline_public_api_rejects_over_limit_before_loading_fixture_or_artifacts(self):
        inputs = [f"https://www.facebook.com/900000007654321/posts/90000000123{index:02d}/" for index in range(11)]
        with patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(OFFLINE_FIXTURE),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
        ), tempfile.TemporaryDirectory() as directory, patch(
            "facebook_collector.collector.load_offline_capture",
            side_effect=AssertionError("fixture loading attempted"),
        ):
            output_dir = Path(directory) / "output"

            with self.assertRaises(BatchValidationError):
                collect_posts(inputs, output_dir)

            self.assertFalse(output_dir.exists())

    def test_invalid_input_writes_and_returns_one_trustworthy_null_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"

            results = collect_posts(["not a URL"], output_dir)

            written = json.loads(
                (output_dir / "runs" / results["run_id"] / "results.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(results, written)
            self.assertEqual(results["run_status"], "completed")
            self.assertIsNone(results["stop_reason"])
            self.assertEqual(
                results["outcomes"][0],
                {
                    "input_index": 0,
                    "duplicate_of": None,
                    "input_url": "not a URL",
                    "resolved_url": None,
                    "post_identity": None,
                    "attempted_at": None,
                    "collected_at": None,
                    "status": "invalid_input",
                    "reason": "malformed_url",
                    "text": {"value": None, "status": "missing", "source": None},
                    "counters": {
                        name: {
                            "value": None,
                            "raw": None,
                            "quality": "missing",
                            "source": None,
                        }
                        for name in ("reaction", "comment", "share")
                    },
                    "latest_updated": False,
                },
            )

    def test_exact_duplicate_invalid_input_keeps_two_linked_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            results = collect_posts(["not a URL", "not a URL"], Path(directory))

        self.assertEqual(len(results["outcomes"]), 2)
        self.assertIsNone(results["outcomes"][0]["duplicate_of"])
        self.assertEqual(results["outcomes"][1]["duplicate_of"], 0)

    def test_pfbid_live_path_reuses_one_browser_and_the_serial_retry_owner(self):
        class Browser:
            def __init__(self): self.closed = False
            def close(self): self.closed = True
        class Runtime:
            def __init__(self): self.stopped = False
            def stop(self): self.stopped = True

        browser, runtime = Browser(), Runtime()
        url = "https://www.facebook.com/acme/posts/pfbidABC123"
        attempts = []
        def live(input_url, *, attempt_timeout_seconds, browser):
            attempts.append((input_url, attempt_timeout_seconds, browser))
            result = build_synthetic_outcome(input_url, {"status": "timeout"}, attempt_timeout_seconds=30)
            return result

        with tempfile.TemporaryDirectory() as directory, patch(
            "facebook_collector.collector._launch_browser", return_value=(browser, runtime)
        ), patch("facebook_collector.playwright_adapter.collect_live_one", side_effect=live), patch(
            "facebook_collector.model.time.sleep"
        ) as sleep:
            results = collect_posts([url], Path(directory), log=True)

        self.assertEqual([timeout for _, timeout, _ in attempts], [30, 30, 30, 30])
        self.assertTrue(all(item[2] is browser for item in attempts))
        self.assertEqual(sleep.call_args_list, [call(2), call(4), call(8)])
        self.assertEqual(results["outcomes"][0]["status"], "timeout")
        self.assertTrue(browser.closed)
        self.assertTrue(runtime.stopped)

    def test_photo_live_path_uses_the_existing_public_flow_once(self):
        class Response:
            status = 200
        class Page:
            url = PHOTO_URL
            def goto(self, url, *, timeout, wait_until): return Response()
            def content(self):
                return '''<article role="article"><a href="https://www.facebook.com/photo/?fbid=1649985453249994">permalink</a>
                <div data-ad-rendering-role="story_message">Photo target</div>
                <div data-counter="reaction">12</div><div data-counter="comment">3 comments</div>
                <div data-counter="share">0 shares</div></article>'''
        class Context:
            def new_page(self): return Page()
            def close(self): pass
        class Browser:
            def __init__(self): self.contexts = 0; self.closed = False
            def new_context(self): self.contexts += 1; return Context()
            def close(self): self.closed = True
        class Runtime:
            def __init__(self): self.stopped = False
            def stop(self): self.stopped = True

        browser, runtime = Browser(), Runtime()
        with tempfile.TemporaryDirectory() as directory, patch(
            "facebook_collector.collector._launch_browser", return_value=(browser, runtime)
        ), patch("socket.create_connection", side_effect=AssertionError("network attempted")), patch(
            "socket.socket.connect", side_effect=AssertionError("network attempted")
        ), patch("subprocess.Popen", side_effect=AssertionError("browser launch attempted")):
            results = collect_posts([PHOTO_URL], Path(directory) / "output")

        self.assertEqual(results["outcomes"][0]["status"], "collected")
        self.assertEqual(results["outcomes"][0]["post_identity"], {"kind": "photo", "photo_id": "1649985453249994"})
        self.assertEqual(browser.contexts, 1)
        self.assertTrue(browser.closed)
        self.assertTrue(runtime.stopped)

    def test_group_listing_public_flow_writes_explicit_target_identity_offline(self):
        class Page:
            url = GROUP_EXPLICIT_URL
            def goto(self, url, *, timeout, wait_until):
                self.requested, self.timeout, self.wait_until = url, timeout, wait_until
                return type("Response", (), {"status": 200})()
            def content(self):
                return '''<article role="article"><a href="/groups/100/posts/200/">target</a>
                <div data-ad-rendering-role="story_message">Group target</div>
                <div data-counter="reaction">0</div><div data-counter="comment">0</div>
                <div data-counter="share">0</div></article>'''
        class Context:
            def new_page(self): return page
            def close(self): calls.append("context.close")
        class Browser:
            def new_context(self): calls.append("context"); return Context()
            def close(self): calls.append("browser.close")
        class Runtime:
            def stop(self): calls.append("runtime.stop")

        page, calls = Page(), []
        with tempfile.TemporaryDirectory() as directory, patch.object(
            socket, "create_connection", side_effect=AssertionError("network attempted")
        ), patch.object(socket.socket, "connect", side_effect=AssertionError("network attempted")), patch.object(
            subprocess, "Popen", side_effect=AssertionError("browser launch attempted")
        ), patch(
            "facebook_collector.collector._launch_browser", return_value=(Browser(), Runtime())
        ):
            results = collect_posts([GROUP_LISTING_URL], Path(directory) / "output")

        outcome = results["outcomes"][0]
        self.assertEqual(outcome["status"], "collected")
        self.assertEqual(outcome["resolved_url"], GROUP_EXPLICIT_URL)
        self.assertEqual(outcome["post_identity"], {"kind": "group", "group_id": "100", "post_id": "200"})
        self.assertEqual(page.requested, GROUP_LISTING_URL)
        self.assertEqual(calls, ["context", "context.close", "browser.close", "runtime.stop"])

    def test_empty_or_over_limit_batch_rejects_before_output(self):
        cases = [[], [f"https://invalid/{index}" for index in range(11)]]
        for inputs in cases:
            with self.subTest(size=len(inputs)), tempfile.TemporaryDirectory() as directory:
                output_dir = Path(directory) / "output"
                with self.assertRaises(BatchValidationError):
                    collect_posts(inputs, output_dir)
                self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()

# Offline collect workflow E2E test

`test_collect_workflow.py` is an approved internal-seam E2E contract test for the public command:

```bash
python -m unittest tests.e2e.test_collect_workflow -v
```

This GREEN test runs one executable offline collector case with one synthetic
fixture. It is an implementation proof, not an acceptance-matrix-row promotion, and
does not make the seam user-facing. Run it separately from the default unit modules:

```bash
python -m unittest tests.test_collection_model tests.test_collector_contract tests.test_offline_capture -v
python -m unittest tests.e2e.test_collect_workflow -v
```

The test uses an approved, internal test-only seam: set
`FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE` to a synthetic observed-capture JSON file
and set `FACEBOOK_COLLECTOR_NETWORK_DISABLED=1`. Both are required; when active,
the collector must not launch a browser or make a network request. The fixture is
not an expected `results.json` document: it uses the approved
`offline-observed-capture-v1` schema with one `observed_capture` containing submitted
and resolved URLs, validated identity, canonical UTC RFC3339 `captured_at`, candidate
text/source, and reaction/comment/share observed value/raw/quality/source evidence.
Both fixture URLs are independently restricted to
`https://www.facebook.com/<numeric-owner>/posts/<numeric-post>/` (optional trailing
slash), with no credentials or custom port.

This first slice accepts exactly one `--url`, which must exactly match the fixture's
`submitted_url`. Repeated `--url`, `--input-file`, public exhaustive URL support,
browser transport, and live transport remain pending and fail closed. The expected `results.json` envelope is
`schema_version="1"` (a string), a `run_id` matching the run directory,
`run_status="completed"`, `stop_reason=null`, and one outcome using the approved
per-outcome fields. The test checks the exact v1 CSV header and semantic UTF-8
content. Focused storage tests cover canonical identity keys, malformed-latest
preservation, atomic replacement, and write-failure cleanup.

No live traffic is allowed. The test also points both HTTP proxy environment variables
at `http://127.0.0.1:9`, clears `NO_PROXY`, and sets the network-disabled switch so a
missing implementation cannot silently turn this test into a live Facebook request.

The successful case writes `results.json`, `posts.csv`, and `posts-latest.csv`. It
does not test cross-run latest replacement, so it does not complete the latest-store
acceptance work.

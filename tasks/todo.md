# Facebook post collector v1 — tasks

## Final review follow-up

- [x] Route every admitted family through the pre-follow redirect gate.
- [x] Bound redirects with a monotonic 30-second attempt deadline and ten-hop cap.
- [x] Replace raw-page phrase block detection with structural login/challenge detection.
- [x] Run offline verification: 80 top-level tests, 4 E2E tests, and compileall.
- [ ] Keep PR draft and #20 open: bounded live acceptance is inconclusive and still pending.

- [x] **SDD: persist and freeze the approved contract**
  - Acceptance: `docs/specs/facebook-post-collector-v1.md` fixes URL/redirect,
    batch/dedupe, retry/HTTP, null-envelope/text-missing, logging, artifact,
    return-value, exit-code, and pacing policy.
  - Verify: review the approved spec and the 65-case synthetic matrix.
  - Files: `docs/specs/facebook-post-collector-v1.md`,
    `docs/testing/facebook-post-contract-cases.md`

- [x] **TDD GREEN: restricted one-URL offline proof**
  - Acceptance: with both internal environment variables, exactly one matching
    fixture URL is collected without browser/network and exports its current
    `results.json`, `posts.csv`, and `posts-latest.csv` artifacts.
  - Verify: `python -m unittest discover -s tests/e2e -p 'test*.py'`
  - Files: existing offline seam, fixture, and E2E test

- [x] **TDD GREEN: public CLI and core**
  - Acceptance: the public API and thin CLI write and return the complete
    envelope, UTC fields, fixed null envelopes, `run_id`, repeated/input-file
    batches, and trustworthy artifacts for the offline seam; unsupported live
    collection fails closed when its dependency is unavailable.
  - Verify: `python -m unittest discover -s tests -p 'test*.py'`
  - Files: `facebook_collector/`, `tests/test_collector.py`,
    `tests/test_collector_contract.py`

- [x] **TDD GREEN: URL admission and redirect safety**
  - Acceptance: exact P01–P05 routes, eight invalid-input reasons, and
    per-item unsafe redirects are covered offline; unsafe redirects continue
    and log only when enabled.
  - Verify: `python -m unittest tests.test_url_validation tests.test_playwright_adapter tests.test_collector -v`
  - Dependencies: policy freeze

- [x] **TDD GREEN: serial batch and stopping**
  - Acceptance: repeated URLs/input files/blank lines, the 10-unique limit,
    serial scheduling, fetch-once duplicate outcomes with `duplicate_of`,
    identity-unverified continuation, and block-only stopping pass offline.
  - Verify: `python -m unittest tests.test_collection_model tests.test_collector tests.test_collector_contract -v`
  - Dependencies: public core

- [x] **TDD GREEN: retry and HTTP mapping**
  - Acceptance: timeout/408/504 have four attempts with 2/4/8-second waits;
    terminal timeout continues, other HTTP mapping does not retry, and blocks
    do not retry.
  - Verify: `python -m unittest tests.test_collector -v`
  - Dependencies: batch

- [x] **TDD GREEN: structured logging**
  - Acceptance: logging is default-off; `--log` creates versioned bounded JSONL
    without sensitive/raw content and does not alter results.
  - Verify: `python -m unittest tests.test_logging -v`
  - Dependencies: retry

- [x] **TDD GREEN: artifacts and latest**
  - Acceptance: canonical versioned JSON/CSV, exact CSV header, conditional
    event file, atomic validated-identity latest replacement, restart behavior,
    UTF-8, and offline exit-code behavior pass.
  - Verify: `python -m unittest tests.test_storage tests.e2e.test_latest_restart_workflow tests.e2e.test_collect_workflow -v`
  - Dependencies: logging

- [ ] **Live acceptance last**
  - Acceptance: separately record the bounded anonymous Playwright/Chromium
    acceptance only after the offline suite and source freeze. Keep the PR as
    draft and #20 open until that evidence is complete.
  - Verify: offline tests pass first; no live invocation is part of this task.
  - Dependencies: artifacts and latest

The current implementation is the approved v1 contract with offline-verified
public API/CLI, URL and redirect validation, serial batch/retry behavior,
logging, artifact/latest storage, and anonymous Playwright behavior covered by
fake-browser tests. Automated verification makes no Facebook network request.
Bounded live acceptance remains inconclusive, so this checklist does not claim
release readiness or live proof until #20 is resolved.

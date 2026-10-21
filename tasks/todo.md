# Facebook post collector v1 — tasks

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
  - Verify: `python -m unittest tests.e2e.test_collect_workflow -v`
  - Files: existing offline seam, fixture, and E2E test

- [x] **TDD GREEN: CLI shell fails closed outside the restricted seam**
  - Acceptance: the public CLI exists, rejects conflicting input modes, and does
    not report success for a normal unimplemented collection command.
  - Verify: `python -m unittest tests.test_collector_contract -v`
  - Files: `facebook_collector/__main__.py`, `tests/test_collector_contract.py`

- [ ] **TDD: URL admission first**
  - Acceptance: exact P01–P05 routes, eight invalid-input reasons, and
    per-item unsafe redirects are RED then GREEN with no network; unsafe redirects
    continue and log only when enabled.
  - Progress: accepted forms, seven pre-request reasons, and redirect mapping to the
    eighth reason are GREEN in `tests.test_url_validation`; public run/log integration remains.
  - Verify: `python -m unittest tests.test_url_validation -v`.
  - Dependencies: policy freeze

- [ ] **TDD: public core second**
  - Acceptance: `collect_posts(urls, output_dir, *, log=False)` and its thin CLI
    wrapper produce the complete envelope, UTC fields, fixed null envelopes,
    `run_id`, and an ordinary return dict equal to `results.json`.
  - Progress: the public function and thin CLI now write/return trustworthy artifacts for
    invalid-only batches; supported URLs still fail closed before live collection.
  - Verify: `python -m unittest tests.test_collector tests.test_collector_contract -v`.
  - Dependencies: URL admission

- [ ] **TDD: batch third**
  - Acceptance: repeated URLs/input files/blank lines, 10-unique limit, serial
    scheduling, fetch-once duplicate outcomes with `duplicate_of`,
    identity-unverified continuation, and block-only stopping pass.
  - Progress: the serial model has 10-unique rejection, exact duplicate linking,
    identity-unverified continuation, block-only stopping, and complete pending envelopes;
    supported-URL batch transport integration remains.
  - Verify: `python -m unittest tests.test_collection_model -v`.
  - Dependencies: public core

- [ ] **TDD: retry fourth**
  - Acceptance: timeout/408/504 have four attempts with 2/4/8-second waits;
    terminal timeout continues, other HTTP mapping does not retry, and blocks do
    not retry.
  - Verify: deterministic synthetic transport tests.
  - Dependencies: batch

- [ ] **TDD: logging fifth**
  - Acceptance: logging is default-off; `--log` creates versioned bounded JSONL
    without sensitive/raw content and does not alter results.
  - Verify: focused logging tests.
  - Dependencies: retry

- [ ] **TDD: artifacts and latest sixth**
  - Acceptance: canonical versioned JSON/CSV, exact CSV header, conditional event
    file, atomic validated-identity latest replacement, restart behavior, UTF-8,
    and exit code behavior pass.
  - Progress: the isolated storage writer has canonical result returns, the exact
    route-specific CSV schema, atomic latest replacement/preservation, empty latest output,
    and write-failure cleanup; public-core/restart/log integration remains.
  - Verify: `python -m unittest tests.test_storage -v`.
  - Dependencies: logging

- [ ] **Live adapter last**
  - Acceptance: anonymous serial Playwright/Chromium transport and rendered-DOM
    extraction satisfy the completed offline contract; bounded live acceptance is
    recorded only after source/code freeze.
  - Verify: offline suite first, then separately recorded bounded acceptance.
  - Dependencies: artifacts and latest

The current implementation is not the target collector: it is the checked
one-URL internal offline slice above. No broader task is marked complete until
its code and black-box tests exist.

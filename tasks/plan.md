# Implementation Plan: Facebook post collector v1

## Overview

ยกระดับ logic ที่พิสูจน์แล้วจาก experiment เป็น local collector บน branch
`feat/facebook-collector-post` โดย public CLI ไม่พึ่ง baseline/reference และทดสอบผ่าน
synthetic offline seam ก่อน bounded live acceptance

## Final review status

- [x] Final review findings fixed with deterministic RED-to-GREEN fake-browser tests:
  every admitted family uses the pre-follow redirect gate; a 30-second monotonic
  attempt deadline and ten-hop cap bound redirects; and block detection requires
  structured login/challenge evidence rather than article text.
- [x] Offline verification: 80 top-level tests, 4 E2E tests, and compileall pass.
- [ ] Bounded live acceptance remains inconclusive; keep the PR draft and #20 open.

## Architecture decisions

- Python plus anonymous headless Playwright/Chromium is the approved v1 transport;
  one browser per invocation and serial URL processing.
- The approved public contract is
  `docs/specs/facebook-post-collector-v1.md`; policy freeze is complete.
- Persist canonical `results.json`, versioned flattened CSV, optional event JSONL,
  and identity-keyed latest CSV using atomic replacement.
- The approved internal offline seam is deterministic test infrastructure only; it
  disables browser/network when active and is not a user-facing interface.

## Strict dependency order

`URL admission → public core → batch → retry → logging → artifacts → live adapter`

Each slice starts with focused RED black-box/offline tests and turns GREEN before
the next slice starts. The existing one-URL offline proof stays as a regression
test; it does not mark any broader target slice complete.

## Phases

### Phase 0: Contract freeze and existing proof

- [x] Record the approved v1 source-of-truth contract.
- [x] Freeze URL, redirect, duplicate, timeout, null-envelope, text-missing,
  HTTP, logging, artifact, return-value, and pacing policies.
- [x] Keep the one-fixture, one-matching-URL internal offline E2E proof GREEN;
  it makes no browser or live request and exports its current three artifacts.

**Checkpoint:** policy is no longer an implementation blocker; the restricted
offline slice remains the only implemented collection flow.

### Phase 1: URL admission (TDD)

- [x] Write RED tests for the five tested `www.facebook.com` HTTPS URL forms,
  permitted query/trailing-slash forms, and the eight invalid-input reasons.
- [x] Implement transport-free URL admission for scheme, host, credentials, port,
  route, and query checks.
- [ ] Write and pass RED/green tests for redirect revalidation: unsafe redirect
  is `invalid_input/unsafe_redirect`, is logged only when enabled, and continues.

**Checkpoint:** accepted URLs and every rejection reason are deterministic,
synthetic, and transport-free.

### Phase 2: Public core (TDD)

- [ ] Add `collect_posts(urls, output_dir, *, log=False)` and keep the CLI a thin
  wrapper with matching semantics.
- [ ] Produce the complete per-input envelope, UTC timestamps, explicit statuses,
  fixed null envelopes, and `run_id`.
- [ ] Return the ordinary dict identical to canonical `results.json`; do not add a
  custom result class.

**Checkpoint:** one synthetic attempted input has the target public result shape,
without claiming batch, retry, logging, or full artifacts complete.

### Phase 3: Batch (TDD)

- [ ] Add repeated `--url`, UTF-8 input files, ignored blank lines, at most ten
  unique URL strings, and exit-2 pre-network validation.
- [ ] Add serial anonymous scheduling and exact-string dedupe: fetch once while a
  duplicate outcome points to the first input with zero-based `duplicate_of`.
- [ ] Add identity-unverified continuation and block-only stopping with complete
  later `not_attempted/blocked` envelopes.

**Checkpoint:** synthetic mixed batches preserve ordered outcomes and stopping
semantics without any concurrency or persistent cache.

### Phase 4: Retry (TDD)

- [ ] Add 30-second attempts for transport timeout/HTTP 408/504 only: four total
  attempts with 2/4/8-second waits.
- [ ] Add non-retry HTTP mapping, timeout continuation, and blocked/no-retry
  behavior.
- [ ] Assert there is no fixed inter-URL delay or evasive retry behavior.

**Checkpoint:** every retry and HTTP outcome is deterministic under synthetic
transport.

### Phase 5: Logging (TDD)

- [ ] Keep logging off by default; create `events.jsonl` only for `--log`.
- [ ] Emit versioned, bounded structured events for acceptance, rejection, retry,
  duplicate, timeout, and applicable HTTP status/attempt.
- [ ] Assert logs never contain body, HTML, screenshot, cookie, or credential and
  cannot change result semantics.

**Checkpoint:** optional diagnostics are structured and privacy-safe.

### Phase 6: Artifacts and latest store (TDD)

- [ ] Write canonical `results.json`, exact-header versioned `posts.csv`, and
  `posts-latest.csv`; add conditional `events.jsonl` from Phase 5.
- [ ] Implement validated-identity latest replacement, successful-null handling,
  preview/missing/failure preservation, validation of existing CSV, and atomic
  replacement.
- [ ] Test restart behavior, UTF-8 Thai/emoji, exit codes, and no default
  HTML/screenshot artifacts.

**Checkpoint:** trustworthy completed/stopped runs write the specified artifacts;
the return dict equals `results.json`.

### Phase 7: Live adapter and bounded acceptance

- [ ] Add anonymous Playwright/Chromium transport behind the completed offline
  contract, one browser per invocation and serial work.
- [ ] Connect validated rendered-DOM extraction only after synthetic offline
  contract tests pass.
- [ ] After source/code freeze, run and record bounded live acceptance separately
  from the offline automated suite.

**Checkpoint:** live transport cannot weaken the frozen public contract or the
offline test boundary.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Experiment harness/sample assumptions leak into production | Port only needed shared logic; tests use synthetic URLs and identities. |
| Tests request Facebook unintentionally | Offline seam plus network denial in test harness. |
| Partial results merge stale latest values | Whole-record replacement tests include successful nulls. |
| Counter values have the wrong scope | Foreign post/comment/menu regression cases. |
| Public contract drifts | Contract-case IDs lead every TDD slice; change the spec only with approval. |

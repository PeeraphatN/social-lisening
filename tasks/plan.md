# Implementation Plan: Close Facebook Counter Accuracy

## Goal

Close #6 and unblock #2 as quickly as possible. Run target-scope implementation and accuracy tooling preparation in parallel, then collect final evidence once against the merged code hash.

## Decisions

- Fail closed: a body counter is usable only when it belongs to one uniquely identified target-post container. No unique target means `null` unless identity-scoped embedded evidence supplies the value.
- Do not run final accuracy collection while extraction code is changing. Preparation can run in parallel; final live evidence must use one merged code hash.
- Keep anonymous access, serialize Facebook requests, and stop on 403/429/CAPTCHA/challenge.
- Keep raw HTML, body text, and screenshots under ignored `experiments/facebook_posts/runs/`.

## Dependency graph

```text
Freeze scope/reference contracts
├── Lane A: target-scoped body extraction ─┐
└── Lane B: accuracy scorer + manifest ────┤
                                           └── merge + 50-test regression checkpoint
                                               └── one final serialized live run
                                                   └── score results + close #6/#2
```

## Parallel wave

### Lane A — Target-scoped body counters

**Owner:** implementation worker in its own worktree

**Tasks:**

1. Inspect saved P01–P10 DOM snapshots read-only and identify the smallest stable target-post container tied to the selected story message/URL.
2. Add failing tests for unrelated counters, duplicate target candidates, ambiguous containers, non-numeric IDs, and raw/count contradictions.
3. Change browser inspection to pass only uniquely scoped target text to counter parsing. Preserve identity-scoped JSON fallback and body precedence inside the scoped container.
4. Fail closed when the target container is missing or ambiguous.

**Likely files:**

- `experiments/facebook_posts/inspect_browser.py`
- `experiments/facebook_posts/probe_post.py`
- `experiments/facebook_posts/test_probe_post.py`
- one focused target-scope test file if needed

**Acceptance:**

- An unrelated post's larger counter cannot become the target value.
- Zero remains zero only with explicit target evidence.
- Missing/ambiguous scope returns `null`, not a page-wide value.
- Existing 50 tests and new focused tests pass.

### Lane B — Accuracy scoring and reference preparation

**Owner:** evidence worker in a separate worktree

**Tasks:**

1. Define a reference manifest with sample, metric, value, exact/approximate, surface, observation time, and evidence path.
2. Add a scorer that reads inspection JSON plus the manifest and reports total/readable/null/unverified per metric.
3. Compute signed and absolute error only for comparable exact pairs; compute percentage error only when reference is non-zero. Never convert missing to zero.
4. Replay existing snapshots to prove report behavior without making Facebook requests.

**Likely files:**

- new `experiments/facebook_posts/analyze_counter_accuracy.py`
- new focused scorer tests
- local reference/evidence files under ignored `runs/`

**Acceptance:**

- Exact, approximate, zero, missing, and unverified values are reported separately.
- Reference zero uses absolute error and no percentage division.
- The scorer is deterministic and covered by offline tests.
- Lane B does not edit `probe_post.py` or `inspect_browser.py`, avoiding merge conflicts with Lane A.

## Merge checkpoint (done 18 ต.ค. 2026)

1. Merge Lane A and Lane B.
2. Run `python -m unittest discover -s experiments/facebook_posts -p 'test_*.py'`.
3. Run `git diff --check`.
4. Freeze SHA-256 for collector files before live collection.

Do not continue if target scoping is ambiguous on the saved snapshots. In that case, retain `null` and document the unsupported layout rather than broadening selectors.

## Final evidence run — sequential

1. Run P01–P10 once through one anonymous browser queue with at least 20 seconds between URLs.
2. Capture target-scoped rendered counters and screenshots from the same page session as each snapshot.
3. Stop on 403/429, CAPTCHA/challenge, unexpected HTTP status, source-hash change, or request failure.
4. Run the scorer and manually verify every exact pair used in the accuracy calculation.

**Acceptance:**

- Every result records input/resolved URL, UTC time, source hash, raw/parsed values, source, and evidence.
- No value from an unrelated post is accepted.
- Coverage and accuracy are reported separately.
- Every accuracy claim identifies the surface and observation time.

## Closeout

1. Update #6 with per-metric coverage/error, unsupported layouts, and tolerance decision.
2. Close #6 only if its remaining checklist is satisfied.
3. Update #2 checklist; close it only after timeout/error preservation, deduplication, P05 preview behavior, tests, and review are verified.

## Timing

- Contract/setup: 15 minutes
- Parallel Lane A and Lane B: 60–90 minutes if saved DOM has a stable target container
- Merge/checkpoint: 20 minutes
- Final serialized run and manual checks: 30–45 minutes
- Issue closeout: 15 minutes

Fast path: about 2–3 hours. If Facebook DOM has no stable unique target container, stop after the 90-minute scope investigation and keep unsupported values as `null`; forcing a selector would delay closure and reduce correctness.

## Risks

| Risk | Mitigation |
| --- | --- |
| DOM selector works only for one layout | Require saved P01–P10 coverage and fail closed per unsupported layout |
| Parallel live runs trigger rate limits or compare different versions | Only the coordinator performs one final serialized run after merge |
| Accuracy scorer validates parser against itself | Reference manifest records independently observed rendered value/screenshot |
| Workers cannot see ignored snapshots in their worktrees | Give read-only absolute paths to the coordinator workspace; never commit raw evidence |

## Proposed follow-up: persistent repeat baseline

### Problem

`run_repeats.py` requires `runs/references.json`, but `runs/` is intentionally ignored and can be cleaned after a live experiment. The runner then cannot resume even though the source and prior issue notes remain.

### Decision to confirm

Track a small `experiments/facebook_posts/repeat-baseline.json` outside `runs/`. It contains only sample ID, public URL, publisher, review time, and a **normalized text SHA-256**—never raw post text, HTML, screenshots, counters, or run output. Raw evidence remains ignored under `runs/`.

### Tasks

1. **Hash-only repeat comparison** — Change `run_repeats.py` to compare normalized text hashes, preserving whitespace-insensitive matching and `content_edited`; add focused tests for matching, changed text, and invalid manifests.
2. **Tracked baseline and migration** — Add the five reviewed P01–P05 metadata/hash records; provide a one-shot local converter from an old ignored reference file, so recovery does not require retyping posts.
3. **Artifact policy** — Document what is tracked, what remains local, and the actionable recovery procedure; reject a missing or malformed baseline before any Facebook request.

### Acceptance

- A fresh clone can start the repeat run without any ignored prerequisite.
- A full-text change still produces `content_edited`; whitespace-only changes still match.
- No raw Facebook post content or other live evidence is committed.

### Cross-worktree handoff

There are two levels of data sharing:

1. **Default / safe:** the tracked hash-only baseline is available in every worktree after checkout. Agents receive the baseline version and commit SHA, not raw post text.
2. **Explicit / evidence:** when a task genuinely needs raw text, HTML, screenshots, or inspection JSON, create a portable evidence bundle at a path outside the worktree and send the bundle path plus its SHA-256 to the receiving agent. Do not paste large evidence into prompts.

Add a small export/import tool or command with these rules:

- export a manifest containing schema version, source session/commit, relative artifact names, sizes, and SHA-256 hashes;
- optionally include selected ignored evidence files, never the whole `runs/` directory by default;
- import validates the manifest, hashes, file names, and path traversal before copying into the receiver's ignored `runs/` area;
- reject stale/mismatched bundles instead of silently mixing evidence from different source hashes;
- record provenance (`bundle_id`, creator, created time, source commit, source hash) in the receiving run;
- use an explicit opt-in for raw Facebook content because it may contain personal data.

The agent handoff contract should name either the tracked baseline commit or the external bundle absolute path and checksum. This makes the data reproducible across worktrees without pretending that ignored files are shared.

### Cross-worktree acceptance

- A fresh worktree can use the tracked baseline immediately.
- A receiving agent can import a selected evidence bundle and reproduce the sender's offline result.
- Wrong, incomplete, stale, or path-traversal bundles fail before analysis.
- The default handoff contains hashes/metadata only; raw evidence is transferred only by explicit request.

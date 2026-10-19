# Close Facebook Counter Accuracy

## Setup (done)

- [x] Freeze target-scope and reference contracts
- [x] Record current collector hashes and baseline test result

## Parallel lane A — target scope (done)

- [x] Inspect saved P01–P10 target containers
- [x] Add red tests for unrelated and ambiguous body counters
- [x] Implement unique target-container extraction
- [x] Run focused tests and full offline suite

## Parallel lane B — accuracy (done)

- [x] Define timestamped reference manifest
- [x] Add deterministic accuracy scorer and tests
- [x] Replay existing snapshots without live requests
- [x] Produce draft per-metric report

## Merge checkpoint (done)

- [x] Merge both lanes without broadening target identity rules
- [x] Run full tests and `git diff --check`
- [x] Freeze final collector hashes

## Final evidence (done) and closeout

- [x] Collect P01–P10 once through one serialized anonymous queue
- [x] Build same-session references for 28 body-visible metrics; exclude P03/share and P10/comment fallback-only values
- [x] Score: 25 exact pairs with zero error; 3 approximate intervals compatible; 2 metrics have no body reference
- [x] Update and close #6/#8 with tested scope and limitations
- [ ] #2 remains open for separate result-aggregation, timeout/error, and merge-review criteria

## Persistent repeat baseline (proposed)

- [ ] Approve tracked hash-only P01–P05 baseline; raw post text remains under ignored `runs/`
- [ ] Make repeat comparison use normalized text hashes and validate its manifest before requests
- [ ] Add migration from legacy ignored `runs/references.json`
- [ ] Document artifact retention/recovery and run the full offline suite
- [ ] Define portable cross-worktree handoff format (manifest, source commit/hash, artifact hashes)
- [ ] Add explicit export/import for selected ignored evidence; validate hashes and reject path traversal/stale source
- [ ] Update agent dispatch instructions to pass tracked baseline ref or external bundle path + SHA-256
- [ ] Test fresh worktree baseline use and offline replay after evidence-bundle import

## Coverage recovery (new scope)

See `tasks/coverage-first-plan.md`.

- [x] Find projection bug: global regex counted Share number before `ถูกใจ` action as an extra Reaction
- [x] Confirm P02/P05 body-row ordering from local saved snapshots; no Facebook requests
- [x] Rebuild offline P01–P10 value/evidence table from post-level engagement rows, not global regex
- [x] Amend #8 scope decision to trust validated requested/resolved identity + unique post-level engagement row
- [x] Add failing tests for route alias, metric association, comments/replies, and unrelated/duplicate rows
- [x] Implement body extraction from unique story engagement row; keep page-wide scans and ambiguous rows rejected
- [x] Replay saved snapshots offline: candidate coverage 30/30 (P07 Reaction/Share remain approximate); old 28/30 projection discarded
- [x] Re-score corrected 28-row same-session manifest; keep two fallback-only metrics out of accuracy pairs
- [x] Freeze source hashes, then run sequential anonymous P01–P10 live validation (second pass after fixing same-value duplicate controls); 10/10 HTTP 200, no challenge, 30/30 readable

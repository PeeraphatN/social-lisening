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
- [ ] Score (done) and manually verify comparable exact pairs (ผู้ใช้ยืนยัน references 21 รายการ)
- [ ] Update #6; close เมื่อ references ผ่านและ tolerance ตัดสิน
- [ ] Verify remaining #2 release criteria and update its status

## Coverage recovery (new scope)

See `tasks/coverage-first-plan.md`.

- [x] Find projection bug: global regex counted Share number before `ถูกใจ` action as an extra Reaction
- [x] Confirm P02/P05 body-row ordering from local saved snapshots; no Facebook requests
- [ ] Rebuild offline P01–P10 value/evidence table from rendered article DOM, not global regex
- [ ] Amend #8 scope decision to trust validated selected-post identity + unique target article/engagement row
- [ ] Add failing tests for route alias, metric association, comments/replies, and unrelated/duplicate articles
- [ ] Implement minimal body extraction relaxation and preserve scope/verification evidence
- [ ] Replay snapshots and review per-metric coverage with user
- [ ] Re-score only after references are corrected and confirmed
- [ ] Run suite; then one frozen-hash sequential live run if offline criteria pass

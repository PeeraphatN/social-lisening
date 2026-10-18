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

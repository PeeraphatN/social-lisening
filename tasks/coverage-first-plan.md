# Facebook counter coverage recovery

## Goal

Improve readable Reaction/Comment/Share coverage while retaining the already validated requested/resolved post identity chain. Do not treat page-wide digit matches as counter evidence.

## Findings that change the plan

- The previous coordinator projection of 28/30 was invalid: it globally regex-matched body text without preserving metric-to-label association.
- P02 body row is `ความรู้สึกทั้งหมด / 1.1 พัน / 374 / 353 / ถูกใจ / แสดงความคิดเห็น`; P05 is `ความรู้สึกทั้งหมด / 395 / 77 / 79 / ถูกใจ / แสดงความคิดเห็น / แชร์`. The user confirms first count is Reaction and the last numeric count is Share, not conflicting reactions.
- The accidental extra Reaction candidates came from `DISPLAY_LABELS[reaction]` matching `{count} ถูกใจ`: the Share number immediately precedes the `ถูกใจ` action button in flattened body text.
- Saved DOM shows the engagement row is inside the rendered post article; counters include bare-number buttons, and the current `probe_post.py` refuses the row because a header permalink cannot be matched to resolved route aliases/`rdid` URLs.

## Decisions

- Trust the existing validated requested/resolved identity chain and selected post message; do not require a separate header permalink to re-prove the same post.
- Relax body extraction only within the unique selected target post engagement row, anchored to its post-level reaction summary and the already selected target message/identity. Do not require a `role=article` wrapper or header permalink when those are absent/non-canonical. Continue excluding comment/reply controls, menus, recommendations, and neighboring posts.
- Preserve `null` when there is no unique selected article or the metric cannot be distinguished; never infer metrics from unscoped page-wide text.
- Do not use coordinator-generated references until metric association is independently checked from saved browser evidence. Coverage and accuracy remain separate. Final review uses only body-visible labels; fallback-only metrics are left without an accuracy reference.
- Keep anonymous-only, sequential live validation, stop conditions, and local ignored raw evidence.

## Work order

1. Rebuild an offline P01–P10 evidence table from the saved DOM and body snapshots. Bind each visible counter to its metric using its rendered engagement-row structure/accessible label, not flattened text regex. Mark layouts/metrics whose association still requires human review.
2. Amend Issue #8 to replace route-header uniqueness with the existing selected-post identity chain plus unique post-level engagement row; retain no-page-wide-scan and unrelated-post exclusions.
3. TDD: add failing synthetic browser-inspection tests for route aliases with one validated selected article, adjacent share count followed by Like action, comments/replies containing numbers, and unrelated/duplicate articles. Then implement only the smallest selector/parser change.
4. Replay saved snapshots offline and report per-metric coverage + evidence; do not use the prior 28/30 projection or old reference manifest.
5. Review saved screenshots/body text, build a same-session reference manifest from 28 body-visible metrics, and score exact/approximate pairs. Keep P03 Share and P10 Comment out of accuracy pairs because they are fallback-only.
6. Run full offline suite, freeze hashes, and complete sequential anonymous P01–P10 live validation with ≥20 seconds between URLs.
7. Update and close #6/#8 with tested coverage/accuracy and limitations; leave #2 open until its separate release criteria are verified.

## Acceptance

- No page-wide body text can become a counter.
- A unique already-identified target post engagement row can supply its rendered counters even when a `role=article` wrapper is absent or its header permalink is not a canonical match.
- Neighboring articles, comments, replies, and action labels do not cross-contaminate metrics.
- Every non-null counter includes source, raw text, scope and verification status; zeros require explicit evidence.
- Tests prove both higher coverage on supported layouts and fail-closed behavior for ambiguity.

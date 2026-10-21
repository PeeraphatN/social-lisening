# Facebook post collector v1

Issue: [#9](https://github.com/PeeraphatN/social-lisening/issues/9)
Status: **Approved target contract**

## Status and scope

This document is the v1 source of truth. It specifies approved public behavior, including live behavior that is not yet implemented.

The current implementation is an internal offline-only first slice: its single synthetic E2E case supports exactly one matching numeric post URL and one synthetic capture with identity kind post. It does not yet implement live transport, the complete URL allowlist, batch behavior, retries, logging, or all target artifact rules below. Do not describe target v1 behavior as implemented.

The collector accepts public Facebook post URLs without login and emits text, aggregate reactions, comments, shares, URLs, timestamps, validated identity, and evidence statuses. It distinguishes unreadable (null) from proven zero, does not need publisher/reference text/baseline input, and never assigns nearby post, comment, reply, or menu counters to the target.

## Runtime and public interfaces

Python plus anonymous headless Playwright/Chromium is approved because the experiment proof used rendered DOM; this is the v1 exception to stdlib-first. Use one browser per invocation and process URLs serially. Do not add a fixed delay between URLs: normal page work supplies the pacing, while the approved 2/4/8-second waits still apply to timeout retries. Do not use login, cookies, persistent profiles, proxies, or HTML/screenshot output by default.

    collect_posts(urls, output_dir, *, log=False)

The Python function is synchronous. Every trustworthy completed or stopped run writes the approved artifacts and returns an ordinary dict identical to the `results.json` document; the envelope includes `run_id`, so callers can locate `output/runs/<run_id>`. Do not add a custom result class. A fatal failure may occur before a trustworthy artifact exists.

The CLI is a thin wrapper with the same behavior:

    python -m facebook_collector collect --url URL [--url URL ...] --output-dir OUTPUT_DIR [--log]
    python -m facebook_collector collect --input-file URLS.txt --output-dir OUTPUT_DIR [--log]

Choose one input mode. The input file is UTF-8, one URL per line; blank lines are ignored. Internally v1 has only collect_one plus a serial scheduler seam: no asyncio.Lock, speculative async API, concurrency option, factory/interface, or parallel work. A future measured experiment may use a bounded asyncio.Semaphore starting at capacity 1; it is not promised here. Upstream handles cross-process and cross-run scheduling.

## URL admission and redirects

Accept only exact tested P01–P05 public URL families on https://www.facebook.com, with no credentials and no custom port:

| Tested form | Exact accepted route |
| --- | --- |
| share | /share/p/&lt;alnum-token&gt;/ |
| photo | /photo/?fbid=&lt;numeric&gt;, optionally followed by one set=a.&lt;numeric&gt; |
| page post | /&lt;ASCII slug&gt;/posts/pfbid&lt;alnum&gt;, where the slug uses letters, digits, dot, underscore, or hyphen |
| group listing permalink | /groups/&lt;numeric-group-id&gt;/?multi_permalinks=&lt;numeric-post-id&gt;, optionally followed by hoisted_section_header_type=recently_seen |
| explicit group post | /groups/&lt;group-id&gt;/posts/&lt;numeric-post-id&gt;/, with optional trailing slash where the tested route permits it |

Profile/page landing and search URLs, every unlisted route, repeated identity parameter, fragment, and unlisted query reject. Query parameter order may vary, but each approved parameter appears at most once. Redirect targets are revalidated against this same set before follow. invalid_input has exactly one of eight reasons: malformed_url, https_required, unsupported_host, credentials_forbidden, custom_port_forbidden, unsupported_route, unsupported_query, or unsafe_redirect.

An unsafe redirect is not followed, affects only that item, logs rejection when logging is enabled, continues the batch, and has latest_updated=false.

## Batch, retry, and stopping

At most 10 unique URL strings are accepted per invocation. A larger batch exits 2 before network. Exact duplicate strings fetch once but retain one ordered outcome per input. A duplicate reuses the first result, has zero-based duplicate_of pointing to the first input, latest_updated=false, and a deduplicated log event. Different invocations fetch again: no persistent cache, cooldown, or cross-run dedupe exists. Distinct URLs unify only after validated identity proves they are the same target.

Each URL has a 30-second timeout per attempt: initial attempt plus up to three retries, with waits of 2, 4, and 8 seconds. Retry only transport timeout and HTTP 408/504. The final timeout is status=timeout, is logged, does not update latest, and continues the batch; it has no stop_reason. Invalid input, unsafe redirect, block/challenge, identity mismatch, and all other HTTP failures do not retry.

| HTTP/result | Required behavior |
| --- | --- |
| 200 with extractable target | extract |
| 3xx | validate redirect before follow |
| 401, 403, 429 | blocked; stop batch |
| 404, 410 | error, post_unavailable; continue |
| 408, 504 | apply retry policy, then timeout; continue |
| 500–503, 505+ | error, facebook_server_error; continue without retry |
| all other HTTP errors | error, http_error; continue without retry |
| 200 challenge/login wall | blocked; stop batch |

An actual block, challenge, or login wall stops without retry. The blocking outcome is blocked; subsequent inputs use the complete null envelope with status=not_attempted and reason=blocked. Preserve earlier outcomes, set run_status=stopped, and set stop_reason=blocked.

identity_unverified means target evidence cannot prove the requested target. It is status=error, reason=identity_unverified, has no retry or latest update, is logged, continues the batch, and has no stop_reason. Untrusted identity, text, counters, and collected_at are discarded rather than exported as target data.

## Identity and outcome envelope

No forced normalization is applied to proven identities:

| Family | Identity shape |
| --- | --- |
| post | { "kind": "post", "post_id": "…", "owner_id": "…" } |
| photo | { "kind": "photo", "photo_id": "…" } |
| pfbid | { "kind": "pfbid", "route": "…" } |
| group | { "kind": "group", "group_id": "…", "post_id": "…" } |
| share | resolve, then use destination identity |

Every input has the same outcome fields:

    {
      "input_index": 0,
      "input_url": "https://www.facebook.com/...",
      "resolved_url": "https://www.facebook.com/...",
      "post_identity": { "kind": "post", "post_id": "…", "owner_id": "…" },
      "attempted_at": "2026-10-20T08:00:00Z",
      "collected_at": "2026-10-20T08:00:12Z",
      "status": "collected",
      "reason": null,
      "text": { "value": "…", "status": "candidate_text_unverified", "source": "rendered_dom_story_message" },
      "counters": {
        "reaction": { "value": 1200, "raw": "1.2K", "quality": "approximate", "source": "target_engagement_row" },
        "comment": { "value": 25, "raw": "25", "quality": "exact", "source": "target_engagement_row" },
        "share": { "value": 0, "raw": null, "quality": "exact", "source": "identity_scoped_zero" }
      },
      "duplicate_of": null,
      "latest_updated": true
    }

| Status | Contract |
| --- | --- |
| collected | validated identity, candidate text, and three exact/approximate counters |
| partial | validated identity with preview/missing text or a missing/unverified counter |
| invalid_input | rejected by input or redirect validation; unsafe_redirect may be discovered after the initial request |
| blocked | block/challenge/login wall; stops batch |
| timeout | final retriable timeout; does not update latest |
| error | request/extraction failure; reason is present |
| not_attempted | batch stopped before this input |

Timestamps are UTC RFC 3339. collected_at is capture time, not publication time. reaction is aggregate reactions; comment is the displayed post counter, not comment-text count or reply-scope proof. Text status is candidate_text_unverified, preview_only, or missing; metric quality is exact, approximate, unverified, or missing. unverified and missing metrics have value=null; zero needs target-scoped evidence. Compact counts are approximate and keep raw; source is extensible diagnostic vocabulary.

Failures keep the complete envelope. Invalid input before network has attempted_at, resolved_url, post_identity, and collected_at all null. Unsafe redirect has attempted_at but null capture fields. not_attempted has null timestamps and capture fields. Their text is {"value":null,"status":"missing","source":null}; every metric is {"value":null,"raw":null,"quality":"missing","source":null}; and latest_updated=false.

Missing or ambiguous target text is partial: text is null/missing, evidenced counters remain, latest is not updated, and text_missing is logged. Do not add a textless status until a proven case exists.

## Artifacts and latest store

    output/
      runs/<run_id>/results.json
      runs/<run_id>/posts.csv
      runs/<run_id>/events.jsonl       # only with --log
      posts-latest.csv

results.json is canonical and contains schema_version="1", run_id, run_status, stop_reason, and ordered outcomes. posts.csv and posts-latest.csv use this exact header:

    schema_version,input_index,duplicate_of,input_url,resolved_url,identity_kind,identity_post_id,identity_owner_id,identity_photo_id,identity_group_id,identity_route,attempted_at,collected_at,status,reason,text_value,text_status,text_source,reaction_value,reaction_raw,reaction_quality,reaction_source,comment_value,comment_raw,comment_quality,comment_source,share_value,share_raw,share_quality,share_source,latest_updated

Populate only identity columns that apply to its kind. JSON null maps to an empty CSV cell, with status/quality columns preserving meaning. Artifacts are UTF-8 and preserve Thai/emoji. run_status is completed except a block, which uses stopped.

Latest uses validated identity, not text, sample ID, or input URL. An eligible capture atomically replaces the whole record, including successful null field values; do not merge old metric values. A validated candidate_text_unverified capture is eligible even if counters are null. preview_only, missing text, and all failures do not overwrite an earlier latest record. There is no snapshot history.

Internal latest keys serialize route-specific identities as canonical compact sorted JSON. Validate the existing header and every row before replacement; malformed data leaves the existing file unchanged. Write temporary UTF-8 CSV in the destination directory, then use os.replace for atomic replacement.

## Logging

--log is optional and off by default; it establishes the convention for future features. When enabled write output/runs/<run_id>/events.jsonl. Each event has event_version="1", UTC time, feature, event (accepted, rejected, retry, or equivalent), status/reason, URL family, and input/index where applicable; include HTTP status and attempt where applicable. Never log body, HTML, screenshot, cookie, or credential. Console stays quiet except important errors. Result semantics never depend on logging.

## Exit codes and compatibility

Exit 0 when a trustworthy run artifact is written, even with mixed outcomes or a stopped/blocked run. Exit 1 for fatal runtime/read/write/internal failure with no trustworthy result. Exit 2 for CLI usage, input-mode, or batch-limit error before network.

The package uses SemVer; existing consumers pin >=1,<2. Within v1, paths and signatures stay stable and fields are never removed, renamed, or redefined; additions are optional only. JSON and both CSV files have schema_version="1"; events have event_version="1". A breaking v2 must write posts-latest-v2.csv, not overwrite v1 latest. Migration tooling waits until v2.

## Current implemented internal offline seam

This is an internal test seam, not a public fixture interface. It activates only when both process variables are set:

    FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE=<path>
    FACEBOOK_COLLECTOR_NETWORK_DISABLED=1

When active, it reads the capture and makes no browser launch or network request. Missing either setting, or a value other than 1 for FACEBOOK_COLLECTOR_NETWORK_DISABLED, leaves the seam inactive; the current slice fails closed rather than falling back to live transport.

The fixture has fixture_schema="offline-observed-capture-v1" and exactly one observed_capture. Its submitted and resolved URLs are independently validated only as https://www.facebook.com/&lt;numeric-owner&gt;/posts/&lt;numeric-post&gt;/ (final slash optional), with no credentials/custom port. It requires post identity and canonical UTC RFC 3339 captured_at. The current offline public invocation accepts exactly one --url, exactly equal to that fixture's submitted_url. Repeated --url, input files, browser/live transport, and the rest of target v1 remain unimplemented in this slice.

## Verification and contract completion

Automated tests use black-box public-CLI contract tests, focused model/latest tests, and synthetic offline integration captures. They never contact Facebook, use ignored raw evidence, or use experiment internals as an oracle. Bounded live acceptance occurs only after source freeze.

The target v1 contract has no remaining product-policy questions. Implementation discoveries that would change this contract require approval before the spec is changed.

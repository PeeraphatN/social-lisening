# Facebook post collector v1 — black-box contract cases

Issue reference: `PeeraphatN/social-lisening#9`
Status: the implemented collector is GREEN through offline public, focused, fake-browser,
and E2E tests. The 65-row matrix remains the approved target contract; its executable
evidence is offline only. See [`docs/specs/facebook-post-collector-v1.md`](../specs/facebook-post-collector-v1.md).

## Scope and execution boundary

Every capture, identity, URL, and text in a test is synthetic. No case requests
Facebook or any other live service. Tests use the documented public `collect_posts()`
and CLI surfaces with the approved internal offline capture-injection seam; they do
not import collector internals, use raw evidence, or require publisher/reference-text
baseline input. Explicit socket and process tripwires fail a test if it attempts a
network connection or browser launch; they do not provide live or browser coverage.

The suite uses deterministic fixtures and fake browsers, including redirect routing,
attempt-wide deadline/hop-cap, and structured login/challenge tests. It never sends a
live Facebook request; bounded live acceptance is documented separately and remains inconclusive.

### Automation levels

| Level | Meaning |
| --- | --- |
| Executable now | A current black-box public-CLI test runs locally. |
| Awaiting implementation | Implement as a black-box synthetic/offline test after its contract slice exists. |
| Review-only | Inspect public output files; do not claim collector behavior passed. |

## Approved public interface and batch inputs

| ID | Contract rule | Synthetic input / precondition | Expected public output | Automation level |
| --- | --- | --- | --- | --- |
| FPC-CLI-001 | Single input uses `python -m facebook_collector collect --url URL --output-dir DIR`. | One supported URL and an empty output directory. | One ordered outcome is written; its status follows the synthetic capture. | Executable now |
| FPC-CLI-002 | Repeated `--url` values are accepted. | Two distinct supported URLs. | One ordered outcome per supplied input unless a block stops the batch. | Awaiting implementation |
| FPC-CLI-003 | `--input-file` is UTF-8, one URL per line. | Two supported URLs in `urls.txt`. | One ordered outcome per nonblank line. | Awaiting implementation |
| FPC-CLI-004 | Blank input-file lines are ignored. | Valid URLs separated by blank lines. | No outcome for a blank line. | Awaiting implementation |
| FPC-CLI-005 | Exactly one input mode is required. | Supply both `--url` and `--input-file`. | Reject before fetch with exit 2. | Awaiting implementation |
| FPC-CLI-006 | Publisher, reference text, and a baseline are unnecessary. | Supported synthetic input without those files or arguments. | Processing is not blocked for their absence. | Awaiting implementation |
| FPC-CLI-007 | An invocation accepts at most 10 unique URL strings. | Eleven distinct URL strings. | Exit 2 before network or artifacts. | Awaiting implementation |
| FPC-CLI-008 | Process exits distinguish trustworthy, fatal, and pre-network failures. | Synthetic completed/stopped run, fatal write/runtime failure, and usage/batch-limit failure. | Respectively exit 0 with a trustworthy artifact, exit 1 without one, and exit 2 before network. | Awaiting implementation |

## URL admission and redirect safety

The tested forms mean only these `https://www.facebook.com` routes, without credentials
or an explicit port: `/share/p/<alnum-token>/`; `/photo/?fbid=<numeric>` with at
most one optional `set=a.<numeric>`; `/<ASCII-slug>/posts/pfbid<alnum>`;
`/groups/<numeric-group-id>/?multi_permalinks=<numeric-post-id>` with at most one
optional `hoisted_section_header_type=recently_seen`; and
`/groups/<numeric-group-id>/posts/<numeric-post-id>` with its permitted optional
trailing slash. No fragment, repeated identity parameter, other query, or other
route is allowed.

| ID | Contract rule | Synthetic input / precondition | Expected public output | Automation level |
| --- | --- | --- | --- | --- |
| FPC-URL-001 | The tested share form is admitted. | Exact synthetic `/share/p/<alnum-token>/` URL resolves to identity `I-1`. | Preserve `input_url`; use the validated destination as `resolved_url` and identity. | Awaiting implementation |
| FPC-URL-002 | The tested photo form is admitted. | Exact synthetic photo URL with `fbid` and the approved optional `set`. | Target the validated photo identity only. | Awaiting implementation |
| FPC-URL-003 | The tested page-post form is admitted. | Exact synthetic `/<slug>/posts/pfbid<alnum>` URL. | Target the validated `pfbid` identity only. | Awaiting implementation |
| FPC-URL-004 | The tested group-listing permalink is admitted. | Exact synthetic group URL with `multi_permalinks` and the approved optional hoisted value. | Target the validated group/post identity only. | Awaiting implementation |
| FPC-URL-005 | The explicit group-post form is admitted. | Exact synthetic group-post URL with and without its permitted trailing slash. | Target the validated group/post identity only. | Awaiting implementation |
| FPC-URL-006 | Malformed input has a fixed reason. | Malformed URL string. | `status=invalid_input`, `reason=malformed_url`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-007 | HTTPS is required. | HTTP P01–P05-looking URL. | `invalid_input/https_required`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-008 | Only `www.facebook.com` is allowed. | HTTPS URL on another host. | `invalid_input/unsupported_host`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-009 | Credentials are forbidden. | P01–P05-looking URL with user-info. | `invalid_input/credentials_forbidden`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-010 | Explicit ports are forbidden, including `:443`. | Supported-looking URL with any explicit port. | `invalid_input/custom_port_forbidden`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-011 | Unlisted routes reject. | Profile landing, page landing, search, or another route outside the tested forms. | `invalid_input/unsupported_route`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-012 | Unlisted query parameters reject. | P01–P05 route with an unlisted query or a malformed P02/P04 query. | `invalid_input/unsupported_query`, no fetch, and the pre-network null envelope. | Awaiting implementation |
| FPC-URL-013 | Redirect targets are revalidated per item. | Eligible URL redirects to an unsafe host, scheme, credentials, port, route, or query. | Do not follow; current outcome is `invalid_input/unsafe_redirect` with `attempted_at` but null capture fields, `latest_updated=false`; log the rejection when enabled and continue the batch. | Awaiting implementation |

## Outcome, retry, and stopping semantics

| ID | Contract rule | Synthetic input / precondition | Expected public output | Automation level |
| --- | --- | --- | --- | --- |
| FPC-OUT-001 | Every outcome has the complete envelope. | Collected, invalid, unsafe-redirect, blocked, timeout, error, and not-attempted captures. | Each includes ordered index/input, URLs, identity, timestamps, status/reason, text, three counters, `duplicate_of`, and `latest_updated`. | Awaiting implementation |
| FPC-OUT-002 | `collected` needs validated identity, candidate text, and three exact/approximate counters. | Complete synthetic target `I-1`. | `status=collected`, non-null identity/capture time, and no claim of verified-complete text. | Awaiting implementation |
| FPC-OUT-003 | Preview-only text is partial. | Validated identity with `text.status=preview_only`. | `status=partial`; it does not overwrite latest. | Awaiting implementation |
| FPC-OUT-004 | Missing or ambiguous text is partial. | Validated identity with missing target text and otherwise evidenced data. | `status=partial`, null/missing text, `latest_updated=false`, and a `text_missing` log event when enabled. | Awaiting implementation |
| FPC-OUT-005 | Missing or unverified counters are partial. | Validated identity, candidate text, and a missing/unverified counter. | `status=partial`; affected metric has `value=null`. | Awaiting implementation |
| FPC-OUT-006 | Identity-unverified is an item error, not a stop. | Plausible nearby data cannot prove the requested identity, followed by a valid URL. | Current `status=error`, `reason=identity_unverified`, no retry/latest update; its untrusted data is null/discarded, is logged when enabled, and the later URL is attempted. | Awaiting implementation |
| FPC-OUT-007 | Only block/challenge/login-wall stops this batch path. | Successful URL, then a synthetic 401/403/429 or 200 challenge/login wall, then a valid URL. | Blocking current outcome is `blocked`; preserve prior outcomes; later outcome is the complete null `not_attempted/blocked` envelope; `run_status=stopped` and `stop_reason=blocked`. | Awaiting implementation |
| FPC-OUT-008 | Retriable failures receive exactly four attempts. | Timeout, HTTP 408, or HTTP 504 on all attempts. | 30-second attempt limit; initial attempt plus three retries after 2, 4, and 8 seconds; final `status=timeout` continues the batch and does not update latest. | Awaiting implementation |
| FPC-OUT-009 | Only timeout/408/504 retry. | 404, 410, 500–503, 505+, another HTTP error, invalid input, unsafe redirect, block, or identity-unverified. | No retry: 404/410 use `error/post_unavailable`; 500–503/505+ use `error/facebook_server_error`; other HTTP failures use `error/http_error`; all continue except block. | Awaiting implementation |
| FPC-OUT-010 | Attempt and capture timestamps are distinct UTC RFC 3339 values. | Complete synthetic capture with distinct attempt and capture moments. | `attempted_at` is UTC RFC 3339; `collected_at` is capture time and null when no capture exists. | Awaiting implementation |
| FPC-OUT-011 | Invalid, unsafe-redirect, and not-attempted envelopes are fixed. | Pre-network invalid input; unsafe redirect; later input after a block. | Invalid has null attempt/resolution/identity/capture fields; unsafe redirect has only `attempted_at`; not-attempted has null timestamps/capture fields; all use missing null text/metrics and `latest_updated=false`. | Awaiting implementation |
| FPC-OUT-012 | A run never substitutes prior latest values into a new outcome. | Partial/error-like capture follows a prior successful latest record. | The new outcome describes only the current capture/outcome. | Awaiting implementation |
| FPC-OUT-013 | An exact duplicate preserves a distinct ordered outcome. | Same URL occurs twice in one invocation. | Fetch once; second outcome reuses the first result, has zero-based `duplicate_of` for the first input, `latest_updated=false`, and a deduplicated log event when enabled. | Awaiting implementation |

## Text and metric representation

| ID | Contract rule | Synthetic input / precondition | Expected public output | Automation level |
| --- | --- | --- | --- | --- |
| FPC-DATA-001 | Candidate text is explicitly unverified. | Target-scoped Thai, emoji, line breaks, and URL text. | `text.status=candidate_text_unverified`; no verified-complete claim. | Awaiting implementation |
| FPC-DATA-002 | Exact metrics are nonnegative capture-specific integers. | Target-scoped reaction/comment/share evidence. | Each has integer `value`, `quality=exact`, appropriate `raw`, and diagnostic `source`. | Awaiting implementation |
| FPC-DATA-003 | Compact metrics are approximate and retain raw. | Compact display values. | Each affected metric has `quality=approximate` and its original `raw`. | Awaiting implementation |
| FPC-DATA-004 | Unverified/missing metrics are null; zero needs scope evidence. | One missing, one unverified, and one target-scoped zero. | First two are null with their qualities; only the evidenced metric is zero. | Awaiting implementation |
| FPC-DATA-005 | Reaction is aggregate reactions. | Multiple reaction types and a displayed total. | `counters.reaction` uses the target total, not only Like. | Awaiting implementation |
| FPC-DATA-006 | Comment is the displayed post counter. | Different post counter and synthetic comment/reply-text count. | `counters.comment` uses the displayed post counter. | Awaiting implementation |
| FPC-DATA-007 | Source vocabulary is extensible. | A synthetic source value outside examples. | Preserve it without a frozen enumeration. | Awaiting implementation |
| FPC-DATA-008 | Foreign numbers never become target counters. | Nearby post, comment/reply, menu, and year-like numbers. | Every output counter is target-scoped or null. | Awaiting implementation |

## Latest, artifacts, and return value

| ID | Contract rule | Synthetic input / precondition | Expected public output | Automation level |
| --- | --- | --- | --- | --- |
| FPC-LATEST-001 | Distinct URLs unify only after validated identity. | Two URLs resolve to `I-1`. | One latest record keyed by identity, not text or input URL. | Awaiting implementation |
| FPC-LATEST-002 | A latest-eligible observation replaces the whole record. | Existing `I-1`; later eligible capture changes values or contains successful nulls. | Text, counters, quality, and `collected_at` replace together; no stale value survives. | Awaiting implementation |
| FPC-LATEST-003 | Changed candidate text does not add a latest record. | Two successful `I-1` observations with different text. | One `I-1` latest record contains the newer observation. | Awaiting implementation |
| FPC-LATEST-004 | Latest persists across restarts without history. | Prior latest then a later successful new run. | One updated latest record and no snapshot history. | Awaiting implementation |
| FPC-LATEST-005 | Ineligible outcomes preserve prior latest. | Stored success followed by timeout, error, blocked, identity-unverified, preview-only, or missing text. | Prior record is unchanged; each outcome has `latest_updated=false`. | Awaiting implementation |
| FPC-LATEST-006 | Candidate text with null counters can be latest-eligible. | Validated candidate-text capture with a missing/unverified counter. | `status=partial`, `latest_updated=true`, and the complete latest record is replaced including nulls. | Awaiting implementation |
| FPC-LATEST-007 | Latest update is atomic and validates old data first. | Valid latest interrupted during replacement; malformed existing header/row. | Readers see old or new whole CSV only; malformed latest is left unchanged. | Awaiting implementation |
| FPC-LATEST-008 | Run artifacts use the approved layout. | Trustworthy synthetic completed or stopped run. | `output/runs/<run_id>/results.json`, `posts.csv`, and `output/posts-latest.csv`; `events.jsonl` only with `--log`. | Awaiting implementation |
| FPC-LATEST-009 | `results.json` is canonical and the function returns the same ordinary dict. | Call `collect_posts(urls, output_dir, log=...)`. | Return value equals `results.json` and includes `schema_version="1"`, `run_id`, `run_status`, `stop_reason`, and ordered outcomes; `run_id` locates `runs/<run_id>`. | Awaiting implementation |
| FPC-LATEST-010 | CSV schema is versioned and flattened. | Any synthetic run with applicable identity fields and nulls. | Both CSVs use `schema_version="1"` and the exact approved header; only applicable identity columns populate, and JSON null becomes an empty cell while status/quality retain meaning. | Awaiting implementation |
| FPC-LATEST-011 | Artifacts preserve UTF-8 Thai and emoji. | Thai/emoji text and line breaks. | JSON/CSV decode as UTF-8 and retain the characters. | Awaiting implementation |
| FPC-LATEST-012 | Required artifacts contain no default HTML/screenshots. | Successful synthetic run in an empty directory. | Only approved JSON/CSV artifacts, plus optional event JSONL; no HTML or screenshot output. | Awaiting implementation |
| FPC-LATEST-013 | `run_status` reflects stopping. | Completed mixed run and a blocked run. | Completed has `run_status=completed`; only a block has `run_status=stopped` with `stop_reason=blocked`. | Awaiting implementation |
| FPC-LATEST-014 | v1 compatibility preserves paths/signatures/meaning. | Additive v1 evolution and a hypothetical breaking v2. | Existing v1 fields remain; a v2 latest store uses `posts-latest-v2.csv`, not the v1 file. | Awaiting implementation |

## Queue, privacy, and logging

| ID | Contract rule | Synthetic input / precondition | Expected public output | Automation level |
| --- | --- | --- | --- | --- |
| FPC-RUN-001 | Queue processing is anonymous and serial. | Two synthetic URLs with request ordering/credential probes. | Process serially with no login, cookies, persistent profile, or proxy. | Awaiting implementation |
| FPC-RUN-002 | No fixed inter-URL delay exists. | Two normal successful synthetic URLs. | Normal page work supplies pacing; only retry waits occur. | Awaiting implementation |
| FPC-RUN-003 | Exact duplicates do not add a transport request. | Repeated synthetic URL. | One fetch plus the linked duplicate outcome from FPC-OUT-013. | Awaiting implementation |
| FPC-RUN-004 | Logging is default-off. | Successful synthetic run without `--log`. | No `events.jsonl`; result semantics are unchanged. | Awaiting implementation |
| FPC-RUN-005 | Enabled logging is structured and bounded. | `--log` run covering accepted, rejected, retry, and HTTP events. | `events.jsonl` entries have `event_version="1"`, UTC time, feature/event, status/reason, URL family, input/index, and applicable HTTP status/attempt; never body, HTML, screenshot, cookie, or credential. | Awaiting implementation |
| FPC-RUN-006 | Console remains quiet except important errors. | Successful and important-error synthetic runs. | Routine collection does not create noisy console output. | Awaiting implementation |
| FPC-RUN-007 | No evasion behavior accompanies blocks or retries. | Synthetic first request blocks; retriable timeout sequence. | No proxy/evasion path; block stops without retry and retriable waits follow FPC-OUT-008 only. | Awaiting implementation |
| FPC-RUN-008 | Public tests remain offline. | Full synthetic suite. | No live Facebook requests, ignored raw evidence, or experiment internals as an oracle. | Review-only |
| FPC-RUN-009 | Live acceptance is bounded and follows source freeze. | Frozen-source candidate after offline suite passes. | A separate anonymous bounded acceptance record; it does not broaden automated tests. | Review-only |

## Case count and current implementation status

| Category | Cases |
| --- | ---: |
| Public interface and batch inputs | 8 |
| URL admission and redirect safety | 13 |
| Outcome, retry, and stopping semantics | 13 |
| Text and metric representation | 8 |
| Latest, artifacts, and return value | 14 |
| Queue, privacy, and logging | 9 |
| **Total** | **65** |

- Top-level offline suite: **80** tests, including **23** Playwright-adapter fake-browser
  tests, all passing locally after the final redirect/block-detection review fixes.
- Executable CLI/public-core contract tests: **15** (**6** CLI contract + **9**
  public-core collector). They prove FPC-CLI-001's restricted one-fixture path through
  both `collect_posts()` and the CLI, plus conflict rejection, repeated-URL ordering,
  UTF-8 input-file blank-line handling, the pre-network 10-unique limit, invalid-only
  result artifacts/return values, and fail-closed supported URLs. Explicit socket and
  process tripwires prevent accidental network connections or browser launches; they
  do not claim live collection or browser support.
- Focused transport-free URL/model/storage tests: **22**. They cover pure admission,
  redirect reason mapping, queue/dedupe/null-envelope rules, and isolated target-schema
  persistence; broader rows stay awaiting public-flow integration.
- Executable E2E workflow tests: **4**, all passing offline.
- Executable collector integration tests: **1** — the separate one-URL offline
  E2E proof. It exports `results.json`, `posts.csv`, and `posts-latest.csv`, but
  does not promote broader matrix rows.
- Synthetic fixture files: **1**. Its internal fixture schema is
  `offline-observed-capture-v1`; it is not a user-facing interface.
- Live Facebook requests: **0**.

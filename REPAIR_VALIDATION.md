# Hourly scanner repair

## Verified historical cause

Retrieved the `scan` job logs for workflow runs #64–#68. All used commit
`a148e67795a552346ba4e9a4d888dd55acdd5bb8`. Compilation succeeded; unittest ran
57 tests and failed six; the scanner was skipped. State persistence succeeded.
These failures were reproduced locally before editing:

- `test_incomplete_security_is_wait` and `test_limited_checks_do_not_generate_buy`:
  the independent-audit early return discarded specific security diagnostics.
  Keep the fail-closed gate and include those diagnostics in the explanation.
- `test_verified_strong_candidate`: stale expectation that asserted booleans and
  a synthetic quote authorize BUY. Independent evidence audit intentionally never
  marks these claims trade-ready. Update regression to require WAIT.
- `test_missing_price`: stale NGN 50,000 allocation / NGN 5,000 risk expectation;
  implemented conservative defaults are 10% / 1% of NGN 200,000. Preserve defaults.
- `test_price_targets`: stale arbitrary USD 1.8/2.4/3 targets for a USD 2
  observation. Preserve removal of fabricated stops/targets and assert absence.
- `test_holder_concentration_descriptive`: stale expectation that holder metadata
  appears in security-failure reasons. Preserve its separation into holder details.

| Run | Run ID | Scan job ID |
| --- | --- | --- |
| 64 | 39875084221 | 120158620011 |
| 65 | 39900656165 | 120241230405 |
| 66 | 39935315633 | 120353306971 |
| 67 | 39973395818 | 120481652445 |
| 68 | 40008337027 | 120601911807 |

`0f3926a` introduced workflow failure reporting; `da48103` separated compilation
and tests and added a completion heartbeat. Preserve those capabilities, removing
`continue-on-error`, validating Telegram acknowledgment, retrying transient
failures, and sending completion only after state persistence succeeds.

## Operational behavior

- Python 3.11, entirely standard library; no pip dependencies required. Compilation
  covers every Python source and all tests. Offline PR CI now targets main and
  repair branches without exposing Telegram secrets to PR code.
- Schedule remains `7 * * * *` (hourly at minute 7 UTC, minute 7 WAT). GitHub may
  delay schedule events. Scheduled execution uses the default branch; repairs
  take effect there only after the PR is merged.
- Required secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, available only in
  trusted scanner steps. Missing credentials fail explicitly. No secret values,
  Telegram request URLs or remote response bodies are logged. Secret metadata
  API access is unavailable to the integration (HTTP 403); validation uses Actions.
- GeckoTerminal discovery, token relationships and pool data; GoPlus provider
  risk flags; DexScreener independent exact-pool price corroboration. Missing or
  malformed data never becomes fabricated evidence or permission to trade.
- Public GETs: per-host minimum 2.2 seconds, 20-second timeout, at most three
  attempts for 429/500/502/503/504 and transport failures. Retry-After is bounded
  to 60 seconds. Existing 8-second discovery and 4-second enrichment pacing stays.
- Telegram: 20-second timeout, three attempts at most, 429/5xx retries, permanent
  4xx fail immediately; `ok=true` plus `message_id` is required. Ambiguous network
  failures may cause duplicate messages; this is logged. Failure to send either
  a candidate or a workflow report fails the workflow.
- Completion summaries include actual observations, candidate count, alerts,
  timestamp, warnings and run link, including zero-candidate scans. Candidate
  research alerts remain separate. Coverage limitations are disclosed. Discovery
  outages fail instead of masquerading as an empty successful scan.
- State files use atomic local replacement. Only confirmed candidate deliveries
  enter reported history. Failed priority transitions retain the previous state
  so the next run retries them. Git persistence remains state-only, non-force,
  rebase/retry on concurrent push; conflicts fail visibly. Artifacts retain state
  and scan summary for seven days, including failed runs.
- Workflow order: compile → tests → secret-presence check → scan → persist state →
  Telegram completion. Failure reporting follows these stages, with outcomes and
  a diagnostic run link. Job budget 20 minutes; scanner budget 15 minutes leaves
  room for reporting after timeout. Runner outages/cancellation cannot guarantee
  delivery. No exchange integrations, trade execution, or balance mutations.

## Validation

Local: `python -m compileall -q *.py tests`; full unittest discovery passes
78 tests, including transport retry bounds, pacing, malformed responses, secret
redaction, empty scans, outages, atomic state, and failed-transition recovery.
Live GitHub Actions and Telegram validation will be recorded in the PR.

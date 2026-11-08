# Recovery execution evidence, 8 November 2026

## Outcome and limits

This is an implemented engineering increment, not a claim that the full recovery directive is complete. The repository has working discovery, reversal research, evidence gates and prospective paper monitoring. Authentic investment admission and validated historical strategy performance remain blocked.

## Verified baseline

- Inspected production source at `683cb3c2ca1e0ecb9e44f737fc191d8da851e97d` through the connected GitHub account. The command-line clone lacked authentication; source was retrieved through the connector. Original binary evidence required explicit base64 retrieval; the large JSON fixture required blob retrieval.
- Both requested commits are ancestors of main: `f9d8adb7309ec44a61fc98d4613a42688a71d23e` and `59bb64dc0d3efae76a2809cca4218ea6d6231a6e`. The compare API reported main two commits ahead of the first, zero behind.
- The independent regression workflow exists and runs compilation, the tests directory, and the separately discovered root classification suite without the scanner cadence guard.
- Final local verification: compilation passed; 712 tests in `tests/` passed; all 8 root classification tests passed. Early fixture-retrieval errors were environmental and resolved without weakening tests.

## Implemented changes

1. Integrated bounded ATL provider research into the hourly workflow before the slower DEX scanner. Uses two free CoinGecko market-catalog requests, with high-cap first-page coverage and a durable rotating tail-page cursor.
2. Corrected the ATL mid-cap floor from the draft's $100M to $200M; $1B remains mid-cap and values above $1B are high-cap. FDV is never substituted for circulating capitalization.
3. Requires fresh timestamps and consistent price times circulating supply before retaining provider cap observations. Provider estimates remain explicitly unverified. No contract identity is inferred from a ticker.
4. Rejects malformed, empty, stale, inconsistent and failed provider responses. Failed collections return a nonzero exit, retain diagnostics and preserve the previous rotation cursor.
5. Integrated ATL outcomes into pipeline health and retained coverage reports. The existing daily digest includes ATL coverage and provider gaps. No new token-specific ATL messages are enabled.
6. Fixed a production-confirmed health defect: a successful multichain process could contain provider failures while overall research health said COMPLETED. It now reports DEGRADED data health. Data degradation alone does not invent a scanner crash or cause repeated failure notifications.
7. Added durable ATL cursor publication to the existing conflict-aware state publisher. Source and adverse evidence histories remain preserved.
8. Extended the workflow job timeout to 35 minutes: bounded stage maxima total 30 minutes before setup, state publication and artifact upload.
9. Retained the draft ATL/recovery/event-state primitives and deterministic tests. Those pure helpers do not authenticate inputs, authorize investments or establish a production alert path.

10. Hardened general, diagnostic, authenticated multipart and ATL event-state Telegram receipt checks. Each requires a positive integer message ID and the expected destination chat. Wrong/missing destinations, boolean/string/negative IDs and channel-name collisions fail closed without advancing delivery state.
11. Connected the existing independent Telegram diagnostic workflow to relevant main-source changes and retained its credential-free receipt report. This permits actual transport verification without waiting for a qualifying investment signal.

Implementation: [PR #81](https://github.com/madukscoll-web/crypto-oracle-x100/pull/81).

Receipt hardening: [PR #82](https://github.com/madukscoll-web/crypto-oracle-x100/pull/82).

## Live provider probe

At `2026-11-07T23:55:21.476723+00:00` the free CoinGecko collector received both requested pages, 200 market records, 160 fresh internally consistent provider-cap observations and 16 provider-reported near-low candidates. One circulating-cap observation failed validation. There were zero independently validated lifetime baselines, zero authenticated assets and zero ATL token alerts. The probe did not contact Telegram or execute orders.

A provider ATL field is discovery evidence. It does not by itself prove complete, comparable lifetime history, contract authenticity, security, circulation or executable entry. The implementation deliberately does not manufacture those findings.

## Production baseline findings

[Scanner run 42424910360](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42424910360) completed its process stages successfully. Its actual live scanner output, distinguished from mocked unit-test log lines, showed:

- 305 discovery observations, 46 qualifying unique pools and 10 assessed candidates.
- Four AVOID/HIGH CONCERN outcomes and six WAIT/VERIFY outcomes; zero research WATCH messages.
- Repeated GeckoTerminal HTTP 429 responses.
- Multichain audit: 141 unique tokens, 12 selected, 129 deferred and ten discovery failures; launchpad origin verified count zero.
- Reversal research: six selected pairs, twelve timeframe assessments, four technical watches; zero deliveries because one adverse finding, one unchanged setup and two weak-volume/invalid-boundary suppressions.
- Prospective strategy runner: twelve rows and 102 paper accounts, explicitly not a validated strategy.
- Historical validation and authenticated admission both BLOCKED.

A successful workflow is therefore not proof of a qualified BUY candidate, complete provider coverage or verified investment performance. Telegram acceptance strings inside mocked unit-test logs are not production delivery evidence.

## Workflow and dependency inventory

Eleven workflow definitions were inspected. The scanner has hourly cron `7 * * * *`, trusted companion completion recovery and main-source push/manual triggers. Gate catalog discovery already runs daily at `17 2 * * *`, so the older scheduling PR was not required to establish a daily scan. Independent multichain discovery runs every six hours at minute 37. The Telegram diagnostic runs daily at 18:35 UTC and now on relevant notification-source changes. These are GitHub cron requests, not a guaranteed exact wall-clock execution time.

Two regression workflows cover pushes/PRs; focused-token review and Gate live probes have source-specific/manual triggers; independent research and Stonk smoke are manual; notification/provenance checks have PR/manual triggers. All have contents read permission except the scanner, which needs contents write to publish its serialized state. The production Python workflows use Python 3.11. No new third-party runtime package or paid dependency was introduced.

## Existing PR reconciliation

Reviewed open PR metadata and changed-file lists for #4, #15, #45, #46, #48, #50, #55, #58 and #80. All branch heads diverge from current main. No old PR was blindly merged.

| PR | Verified disposition |
| --- | --- |
| #4 | Main already has global discovery, exact identity, evidence and Gate modules. Thirty-nine changed blobs match current main exactly; other files differ or are absent. This does not mean every historic change is incorporated. |
| #15 | Current Gate discovery workflow exists, but its blob differs from this proposal. |
| #45 | The two proposed LINK/AKE dossier paths are absent from current main. They were not converted to approved review records. |
| #46 | Main has authenticated admission, trust, preflight and sequential simulation modules with newer differing blobs. No reviewer keys, signatures or approval records were fabricated. |
| #48 | Main has newer research eligibility/delivery tests and paths; the old scanner diff was not merged. |
| #50 | Six changed blobs match main exactly, including reversal backtest/gate modules and tests; other files differ or are absent. |
| #55 | Current scanner rotates watchlist revisits by oldest observation; the proposed priority ordering is not incorporated verbatim. |
| #58 | Main has newer `technical_watch.py` and production reversal integration. The seven original proposed file paths are not identical to current main. |
| #80 | Reused and corrected selected new modules. Its stale workflow/Telegram changes were not merged. Lifetime baseline verification and token alert integration remain incomplete. |

Open issues #6, #11, #14, #39, #47, #49, #57, #60 and #63 were inspected. They are not closed by this increment.

## Genuine remaining dependencies

| Capability | Evidence-backed blocker | Concrete recovery requirement |
| --- | --- | --- |
| Authenticated BUY admission | `admission_trust.json` has no reviewers, sources or routers; no signed exact-asset admission bundles exist | Enroll real independent reviewers using their public keys, independent source organizations and reviewed router identities; supply genuine current evidence-bound attestations. Never share private signing keys. |
| Gate investment candidates | `gate_token_reviews.json` has an empty tokens map | Populate only authentic named-human-reviewed records meeting the existing freshness, identity and evidence schema. |
| ATL opportunity alerts | No validated lifetime baseline, exact-contract/security join or eligible delivery integration | Obtain comparable historical coverage and independent corroboration, retain provenance, join exact asset identity and security evidence, then test the trusted classification and deduplicated transport path. |
| Verified security/tokenomics | LP control, adjusted beneficial ownership, unlocks, circulating supply and executable sellability remain missing, conflicting or unsupported for candidates | Collect actual exact-chain evidence or retain WAIT/VERIFY/rejection. Engineering cannot honestly turn missing evidence into approval. |
| Historical strategy claims | `historical_cohort.json` contains zero records | Build a representative point-in-time cohort including failures and contemporaneous liquidity, costs and feature availability, then run walk-forward/out-of-sample evaluation. |
| Discovery completeness | Public-provider rate limits and bounded assessment budgets remain | Continue provider pacing/fallback and supported-chain evidence work; report actual observed coverage, not a complete-market claim. |
| Remaining product work | Draft review ordering, full classification taxonomy, trusted ATL transport and some requested reversal metrics are still incomplete | Implement and verify those separately without describing this increment as full project completion. |

The local runtime has no Telegram credentials or executable-entry configuration. GitHub production has its own secret bindings; local absence must not be represented as production secret absence. No paid service was purchased, no private key was accessed and no trade was placed.

## Deployment verification

- PR #81 merged as `295ef42c801f0300d8414302502afd3059a5f0f1` after remote regression and public-adapter checks succeeded. [PR-head regression run](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42427761824); [PR-head adapter checks](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42427761906).
- The deployed hourly workflow [run 42427894851](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42427894851) compiled and passed its unit tests, refreshed production state and completed the new ATL stage successfully at `2026-11-08T00:02:18Z`. The full workflow subsequently completed successfully. Its final health report correctly recorded DEGRADED provider coverage while every process stage succeeded; authenticated admission and historical validation remained BLOCKED.
- PR #82 merged as `c5e5cbf6c08d863239727c2001651bb375478fac` after [remote regression](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42428174291) and both public-adapter checks succeeded.
- The independent deployed [Telegram check 42428254728](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42428254728) succeeded. Its actual non-test log reports `configured=true`, `bot_authenticated=true`, `chat_accessible=true`, `delivery_confirmed=true`, `status=DELIVERY_CONFIRMED` at `2026-11-08T00:06:46.787916+00:00`. This establishes Bot API acceptance for the configured destination, not that a person read the message.
- The credential-free receipt artifact is `telegram-delivery-42428254728`, artifact ID `13596680739`, digest `sha256:b19e9c6a3386e12d44381ec8564497d1e9a984e098b337cc2fd56196cc80093b`, retained for seven days.
- Production scan 42427894851 assessed ten of 51 qualifying unique pools from 305 observations. Five were AVOID/HIGH CONCERN and five WAIT/VERIFY; all ten were ineligible for individual messages. Reversal research had three technical watches, all suppressed for an adverse finding, unchanged conditions or weak-volume/invalid-boundary evidence. Zero new opportunity notifications from those paths is an evidence outcome, not a transport failure.
- The deployed ATL probe at `2026-11-08T00:02:16.482090+00:00` received 200 records, retained 160 fresh internally consistent provider-cap observations and identified sixteen provider-reported near-low candidates. It validated zero lifetime baselines and sent zero ATL alerts.
- Actual state publication succeeded at `2026-11-08T00:16:40.303429+00:00`, creating commit `81907a444d58a6f894c312955ee4f51a229efc33`. It preserved the later receipt-hardening source commit as its parent, demonstrating that publication did not revert newer code.
- `atl_research_state.json` was read back from main with `{"version":1,"cursor":2}`, blob `4aa25e51516d1b19b1398cf6fa1bf12b5cb71071`. This is actual persisted state, not only a local write.
- The scan artifact is `scan-diagnostics-42427894851`, artifact ID `13596249706`, digest `sha256:83b4e071fcf98d79dc3d52309cb34fcbe54921f3d9b53142cc847911f4436155`, retained for seven days.
- The next scanner run on receipt-hardening source, [42428254760](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42428254760), has started and passed its ATL stage; its full scan is still in progress at this checkpoint. No outcome is claimed for that unfinished run. GitHub continues that actual execution independently of the chat session.

The entire bot is not declared complete. Missing evidence and the remaining implementation work above remain outstanding.

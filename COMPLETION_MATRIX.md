# Completion evidence matrix — 31 October 2026

**Overall: PARTIALLY VERIFIED. The complete investment-research mission is not yet complete.**

Baseline main was `b7f2a63a2b49b4e19269c9011d0bc5245f011c19` (merged PR #30).
The actual PR collection through #30, Issue #6, prior production diagnostics and
current workflows were reviewed. Number gaps in the collection are issues, not
invented pull requests. Open PRs #4 and #15 are not treated as merged features.
New evidence: `validation/completion-live-2026-10-31.json.gz`. Synthetic tests are
explicitly not historical or live provider evidence.

| # | Directive requirement | Status | Reproducible evidence and remaining limitation |
|---|---|---|---|
| 1 | Current main, Issue #6, PRs through #30 and diagnostics audit | PARTIAL | GitHub source/history inspected; primary discovery, evidence, notification and ledger paths reviewed. Not a comprehensive independent contract/security audit of every dependency. PR #30's Stonk integration preserved. |
| 2 | Authenticated, attributed launchpad discovery and origin | PARTIAL | Official pump IDL/create instructions/events implemented over HTTPS mainnet RPC; bounded live probe returned valid RPC responses with zero creates. Five real LetsBONK API rows independently corroborated against finalized Raydium-owned pool platform/mint bytes; no token-suffix inference. Stonk is provider-attested and can be empty. Four.meme docs HTTP 403, official usable API/schema/program mapping not established. This is source authentication and narrow origin evidence, not an independent security audit. |
| 3 | Eight-network reliability, bounds, concurrency, retries, health, dedup/rotation | PARTIAL | Live probe observed all eight networks. At most three independent provider groups, serial paced calls within a provider, per-provider time/request budgets, Retry-After respected. All new-pool chains visited before trending; durable cursor changes fetch start, least-recently-selected identities prioritized. Two trending requests exhausted budget in probe; continuous provider availability is not guaranteed. Persistent state stored by hourly workflow; post-deployment confirmation required. |
| 4 | Winners and comparable failed-launch historical reconstruction | BLOCKED | Empty `historical_cohort.json` is explicit, not fabricated data. Real launch-era SHIB and Chainlink history endpoints returned HTTP 401. A separate non-production descriptive study now verifies 75 public Binance Vision archives for BNB/SHIB/old LUNA, with explicit chart-only limitations and no production-model use. Representative failure-inclusive cohort, point-in-time holders/supply/unlocks and executable entry/exit depth/costs remain absent. Current charts cannot reconstruct these facts. |
| 5 | Separate ranking, walk-forward and holdout validation | PARTIAL | `research_validation.py` implements separately versioned meme and utility fixed heuristics; provenance/time checks, asset overlap rejection, purged matured training windows, final temporal holdout, per-type metrics and execution-cost/depth checks. Real dataset absent: report BLOCKED. Synthetic tests verify mechanics only; no predictive validation, calibration or 100x claim. |
| 6 | Full security, controls, owners, tokenomics, backing, market/execution evidence | BLOCKED | Existing bounded evidence collectors preserved. Complete beneficial ownership, LP controls, supply/vesting/bridge-reserve proof and funded two-way executable quotes are not established. Narrow chain observations cannot fill these gaps. Original independent BUY audit remains fail-closed. No issuer review or credential forged. |
| 7 | Five canonical outcomes | PARTIAL | `canonical_outcomes.py` emits the common policy in scanner and discovery artifacts. REJECT differs from INSUFFICIENT EVIDENCE; existing preliminary/candle watches remain RESEARCH WATCH when critical gaps exist. ENTRY WATCH requires a complete original audit with no critical gaps; VERIFIED BUY reuses original authorization. Those positive evidence paths remain unavailable with current missing verification, not manufactured. No caller label/boolean authorizes BUY. |
| 8 | Rejection suppression, internal records and Telegram | PARTIAL | Existing default-deny send paths preserved; canonical records remain in diagnostics. Actual baseline production Telegram delivery verified previously. New commit's live delivery and suppression require post-merge logs/artifact inspection. No live test token or recommendation sent merely for testing. |
| 9 | Immutable timestamped forward performance, costs, false positives, model history | PARTIAL | New append-only hash-linked JSONL records model hash/parameters and contemporaneous observations; corrupt chains reject writes. Legacy entry imports marked LEGACY_UNKNOWN without invented historical features/model predictions. Original timestamps retained. Sampled drawdowns/horizons remain operational. Without authenticated historical/live execution costs and mature labelled outcomes, liquidity-adjusted returns and false positives stay null. Hash links detect altered content; they are not external immutable storage or protection from full-history replacement. |
| 10 | Compile, regression, adversarial, integration and production checks | PARTIAL | Compilation plus 465 tests passed locally. Live API/RPC probes and rejected/unknown decision tests retained. CI and post-deployment results are recorded in the final execution report, not presumed from local success. |
| 11 | PR, successful required checks, merge and production verification | PARTIAL | Changes prepared for reviewable commits; merge/deployment must follow successful checks. Final report supersedes this as-of-commit status only when real evidence exists. |
| 12 | Evidence-linked final matrix with unresolved dependencies | COMPLETE | This matrix identifies each requirement as COMPLETE/PARTIAL/BLOCKED/FAILED and links source/probe files. No unresolved requirement is described as complete. |

## Provider provenance

- Pump IDL/program docs: https://github.com/pump-fun/pump-public-docs . Only GET/RPC
  read methods are used. `CreateEvent` decoding is scoped to Pump program log
  execution; unrelated program logs and failed/mismatched transactions cannot
  attribute origin. Top-level create mint identity must be a signer. RPC JSON
  parsing supports returned transaction version 1; zero sampled creates is not
  proof that no tokens launched.
- LetsBONK URL and platform ID are from Raydium's official
  `raydium-sdk-V2-demo/src/launchpad/url.ts`, `mintListApi.ts` and
  `createBonkMintApi.ts`. Pool layout offsets follow
  `raydium-sdk-V2/src/raydium/launchpad/layout.ts`; program ID follows
  `src/common/programId.ts`. Exact platform/mint at a finalized RPC slot is a
  narrow origin corroboration independent of API assertions, not an audit.
- Access was intermittent: the first LetsBONK request returned 403; a later
  bounded probe returned five records and matching chain data. Both outcomes
  are retained. No restriction bypass or undocumented endpoint was used.
- Four.meme documentation access failed. No replacement API or contract address
  was guessed. StonkFun origin cannot be independently established without a
  documented program/creation proof.

## Required external inputs

1. Permitted Four.meme documentation/API access and independently documented
   deployment/creation identity; equivalent Stonk origin evidence.
2. A representative launch cohort including delisted/failed launches and
   time-stamped historical execution, holders, supply, vesting and available-at
   feature archives. CoinGecko historical access alone would not establish all
   these facts or eliminate survivorship bias.
3. Reviewed source/authority/custody/beneficial-owner/bridge-backing records and
   authenticated quote access, public taker, funding/size and risk constraints.
   No private keys are needed or accepted by this research system.
4. Prospective observations across the requested holding periods. Future
   90-day/year outcomes cannot be produced immediately.

## Reproduction

```sh
python -m compileall -q *.py tests
python -m unittest discover -s tests -v
python multichain_live_research.py --limit 16 --include-profiles --include-stonk --include-launchpads --state work/discovery-state.json --output work/discovery-report.json
python research_validation.py --dataset historical_cohort.json --output work/historical-validation.json
```

The last command reports BLOCKED for the real empty cohort. A successful workflow
step running that command means the status was recorded, not that a model passed.

No trading, signing, wallet secrets, automatic approval or weakened BUY gate has
been introduced. Existing Telegram secrets and hourly schedule are unchanged.


Cross-source regression correction: a secondary source's exact-asset adverse
finding previously could be omitted when a clean market row represented the
asset. A reproducing test failed (INSUFFICIENT EVIDENCE instead of REJECT).
Discovery now aggregates adverse reasons across all rows, persists exclusions by
canonical asset identity, and reapplies them after restart. No automatic clearance
is inferred from a missing adverse feed. This fixes reporting/persistence, without
relaxing any BUY gate. The final 455-test suite includes this regression.


Production run 41192027394 failed before completion: Solana `onchain.raw` is an
RPC trace list, while the shared candidate blocker assumed an EVM results object.
The exact AttributeError was reproduced in two regressions. The correction leaves
Solana LP control coverage unknown, preserves adverse vetoes before schema handling,
and records safe frame locations without credentials. No successful deployment of
that earlier run is claimed. Final production status is reported only after the
corrected source has actually run.


Forward-ledger revisit correction: an end-to-end scanner regression with empty
discovery feeds and a refreshed tracked pool reproduced missing forward events.
Capture now receives the actual assessed `selected` set, including tracked-pool
revisits, instead of only fresh discovery candidates. The original entry and the
new accepted price both reach the ledger. All 465 tests pass after this correction.

Historical descriptive context (not a model validation cohort):
`research/nonproduction/historical-context.json` and `archive-manifest.json`
contain real, checksum-verified venue candle observations. BNB's retained
2017-11 to 2021-11 daily-close path has a 430.39x maximum chart multiple from the
first retained close, with an 80.02% sampled close drawdown. SHIB's retained
2021-05 to 2022-05 path has only 2.28x maximum daily-close multiple from the first
retained close; earlier widely quoted multiples cannot be assumed executable at
this venue/time. Old LUNA's retained path ends before Terra 2.0 ticker reuse and
shows a 99.9997% sampled close drawdown. These are USDT-denominated hypothetical
chart statistics, NOT executed returns, exact launch prices or independent token
identity/holder/tokenomics reconstruction. This convenience sample is not a
matched launch cohort and cannot validate predictive models. Dataset attribution
and CC BY-NC-SA 4.0 restrictions are scoped in that separate non-production folder.


Ledger bootstrap correction: all retained legacy signals are imported once into
the hash-linked log even when a run has no corresponding discovery/refresh item.
Their original entry timestamp/price and unknown model lineage are preserved;
no new price, historical feature, verified security claim or model prediction is
invented. A regression checks empty-current-discovery import and repeat deduplication.


Production publication race: run 41193887310 successfully scanned, classified,
created legacy ledger events, and ran all discovery/history steps, but correctly
refused a rebase conflict in research_discovery_state.json/watchlist_state.json.
Queued runs had pinned source snapshots with older state than the current branch.
No successful full deployment or completion message is claimed for that run.
`workflow_state.py` now refreshes state independently of tested source, compares
baseline blobs before publication, and creates a state-only commit on the latest
branch tree. It never rebases mutable JSON or replaces source code. Real local
Git tests cover queued snapshots, concurrent code commits, concurrent state veto,
ledger/signal-history rewrite rejection, and idempotent publication recovery.
All 465 tests pass. Actual final GitHub publication and Telegram completion remain
mandatory post-merge checks, not inferred from these tests.


The 10 legacy signal events produced by the failed-publication run were recovered
byte-for-byte from artifact 13040565101. Their hash chain validates, and every
original entry timestamp/price/token matches current main's retained signal
history. `validation/ledger-recovery-2026-10-31.json` records provenance and hashes.
No historical model prediction was synthesized; original import timestamps and
LEGACY_UNKNOWN flags are unchanged. New publication logic protects this ledger
prefix on every future update.

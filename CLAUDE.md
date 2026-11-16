# CLAUDE.md — standing instructions and project state

Read this first. It is written for any Claude session, including scheduled runs that
start with no memory of earlier conversations. Keep it accurate: update it in the same
PR as any change that makes a statement here untrue.

## What this is
A **research-only** crypto monitoring bot (`madukscoll-web/crypto-oracle-x100`). GitHub Actions
scans new DEX pools, bullish reversals and all-time lows, and sends classified messages to a
Telegram chat. Nothing here is investment advice, and **profitability is NOT ESTABLISHED**.

## Non-negotiable rules
1. **Trading stays disabled.** No orders, no funded execution. `buy_authorized` and
   `orders_allowed` stay false until the owner gives explicit written approval.
2. **BUY admission is fail-closed** (`authenticated_admission.py`, `gate_token_reviews.json`
   has no approved records). Never loosen a gate, threshold or freshness rule to produce
   more alerts. Fewer, honest alerts beat more, unsupported ones.
3. **Never request, print, log or commit secrets.** Keys live in GitHub Actions secrets
   only. If a key ever appears in chat, a PR or git history, tell the owner to revoke it.
4. **Branch + PR for every change. Never merge to main, and never force-push main, unless
   the owner explicitly says to merge.** Squash merges break stacked PRs; rebase with
   `git rebase --onto origin/main <old-base> <branch>` and force-push with a lease.
5. **No profitability or "premium outcome" claims.** Say what the evidence shows and what it
   cannot show. A provider-reported ATL is never a verified lifetime ATL.
6. Telegram message **first line is the exact classification label**
   (`classification_policy.py`); untrusted text can never claim a BUY label.
   Labels: NEW TOKEN DISCOVERY (pool created within 72h), EXISTING POOL DISCOVERY (older pool), EARLY BULLISH REVERSAL WATCH, CONFIRMED BULLISH REVERSAL,
   ALL-TIME LOW WATCH, RESEARCH WATCH, BUY CANDIDATE | MANUAL REVIEW, SYSTEM HEALTH REPORT,
   CRITICAL SYSTEM FAILURE (only when the core scan did not succeed).

## Test before every PR
`python -m unittest discover -s tests` (1050 tests on this branch; CI runs `test` and
`regression`). New behaviour needs tests, including failure and abuse cases; check a test
can fail by temporarily breaking the code it guards.

## Where things are
- `.github/workflows/main.yml`: scanner (cron `7,27,47 * * * *`, push and workflow_run
  triggers, cadence guard, scanner step limit 15 min, state published as git blobs).
- `crypto_oracle_scanner.py`: discovery, per-candidate `enrich()`, research alerts.
  `oracle_http.py` has per-host 429 cooldowns; `_fetch_waiting` waits out one cooldown of
  at most 75s within a per-stage budget (discovery 180s, enrichment 150s, revisit 90s).
- `hourly_evidence.py`, `verification.py`, `onchain.py` (eth/base/bsc RPC; `owner_control` reads owner() and EIP-1967 proxy slots, withhold-only),
  `solana_evidence.py` (legacy SPL and policy-checked Token-2022 mints), `evidence_coverage.py`: safety evidence.
  **No token identity means every check is skipped**, so identity failures cascade.
- `atl_hourly_research.py`, `atl_evidence.py`, `atl_lifetime.py`, `gate_history.py`, `atl_onchain.py`
  (exact-contract on-chain facts: code/mint exists, supply, authorities, owner/proxy; withhold-only):
  all-time-low pipeline. `atl_lifetime_registry.json` is empty, so no ATL can be verified.
  Gate venue history is informational and can only withhold an alert.
- `signal_tracker.py`, `signal_revisit.py`, `forward_ledger.py`: paper outcome tracking.
  `signal_history.json` is append-only (guard in `workflow_state.py`). Summaries refuse a
  conclusion below 30 samples; the 3% round-trip cost is an assumption, not measured.
- `pattern_lab.py` + state `pattern_dataset.json`: records features of EVERY candidate at first sight, re-prices
  at 24/72/168h (net of assumed 3% cost, unexitable = -100%), and `study()` reports a feature pattern only if it
  holds on a time-ordered held-out split with a CI and multiple-comparison correction; below 200 measured
  outcomes it says INSUFFICIENT SAMPLE. It shows no score and never loosens a gate. Next step once a pattern is
  validated: show it as research context only, never as an approval.
- `technical_watch.py`: Gate spot reversal alerts. `telegram_notify.py`: health and
  failure messages. `research_notice.py`: signed notice envelope and labels.
- State is committed by the bot as "Update scanner research state [skip ci]".

## Work log (merged)
#102 discovery rate-limit wait, BOT HEALTH label, peg-like ATL exclusion. #103 new
reversal and failure labels, NEW POOL vs EXISTING POOL wording. #104 tracked signals are
re-priced independently of discovery. #105 sectioned Telegram messages. #106 Gate venue
history and book depth. #107 enrichment waits out cooldowns (identity failures 5 -> 2
per scan). #108 health report names the ATL asset. #109 outcome tracker waits out cooldowns.
#110 "why no alerts" health section. #112 and #113 reversal/discovery/ATL alerts open with a plain-English block and explain jargon inline.
#114 Token-2022 parser (`solana_evidence.extension_policy`: benign allow-list, dangerous extensions FAIL, unknown extensions UNSUPPORTED; does not by itself make any token alert-eligible).
#115 EVM `owner_control` (proxy = FAIL; active owner = UNKNOWN; renounced = LIMITED; never clears a token). #116 `pattern_lab` winner-pattern study (needs ~200 measured outcomes before it reports anything).
Discovery headline now matches the pool: NEW TOKEN DISCOVERY only when the pool is NEW POOL (created within 72h); older or unknown pools say EXISTING POOL DISCOVERY and the plain-English block says it is not a new listing.
#119 `gate_listings.py` + workflow `gate-listings.yml`: read-only snapshot of Gate Spot tradable USDT bases, printed in the job log (`GATE_BASES`, `GATE_CHECK`), so token screens can be filtered to what is buyable on Gate; no state file, no gate change.
#120 `token_probe.py` + workflow `token-probe.yml`: read-only one-off probe of an EVM token contract (public RPC reads, GoPlus, DexScreener) printed as `PROBE` log lines; no keys, no orders, no gate change.
Open: ATL missing-data PR (on-chain facts, Gate hourly low-day candles, "Checked / Needs a human / Not verified yet" message sections). The 4 items needing a human stay human: first-trade provenance, migration/split inventory, independent full history, circulating-supply vesting. Older open PRs #101, #100, #80, #58, #50, #48,
#46, #45, #4 are the owner's; #101/#100 look superseded. Do not close or merge them
without asking.

## What scans showed (run 43126411214, after #107-#109)
58 candidates, 10 assessed, 0 alerts. Reasons: 5 flagged high-risk by GoPlus (correct
rejections), 4 with no GoPlus data (token too new), 2 Solana Token-2022 mints unsupported,
and LP lock, holders and live sell quote unverified for all 10. The outcome tracker priced
signals again (`priced: 1`). GeckoTerminal free quota is the main constraint.
GitHub's scheduler also skips many cron runs (one scheduled scan in about six hours was
observed), which is outside this repo's control.

## Next steps, in order
1. Check the next scans: look for `Pattern study` lines (outcomes measured/200) and `owner_control` in the Filter audit.
2. Extend Token-2022 or owner_control policy only after review.
3. Done in the open PR: on-chain owner and proxy reads for tokens GoPlus has not seen.
4. Price refreshes now go to DexScreener first (`dexscreener_prices.py`, used by `signal_revisit` and
   `pattern_lab` via `fetch_reprice`); pools DexScreener omits are re-asked from GeckoTerminal, never marked
   vanished. Check the `Reprice sources:` log line. Next: consider DexScreener for enrichment too.
5. Let outcome data accumulate (weeks), then test which filters separate winners from losers.
6. Paid provider keys (e.g. Alchemy, Helius) only if free sources prove insufficient, as
   GitHub secrets set by the owner.

## Verifying a scan
`gh run list --workflow "CRYPTO-ORACLE X100 Scanner"`, then `gh run view <id> --log`.
Useful lines: `Candidates found`, `Research WATCH messages delivered`, `Signal revisit:`,
`Paper <n>h measured`, `Enrichment identity unavailable` (should be rare), `waiting <n>s`,
`Filter audit` (JSON; per-candidate reasons), `Evidence coverage`, `Telegram delivery
confirmed by Bot API`. The log mixes unit-test output with scanner output (test fixtures use
addresses like 0x2222...): ignore those, and anchor on real chains and the later timestamps.
In Claude's cloud sandbox, artifact downloads and `gh pr create` are blocked; use `gh run view
--log` and `gh api repos/madukscoll-web/crypto-oracle-x100/pulls` instead.

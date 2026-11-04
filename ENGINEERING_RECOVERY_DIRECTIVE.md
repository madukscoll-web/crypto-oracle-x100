# CRYPTO-ORACLE X100 — END-TO-END ENGINEERING RECOVERY DIRECTIVE

## Mission
Autonomously inspect, repair, integrate, test and deploy the existing GitHub repository to produce useful, evidence-grounded cryptocurrency research and Telegram alerts. Preserve the production hourly scanner, security gates, human-only final approval and all completed work. Do not invent BUY signals, prices, liquidity, test results, or deployment success. Work to verifiable completion, not a predetermined BUY count or deadline.

## Existing work to reconcile
- Production branch: main.
- Issues #6 (admission evidence), #49 (established-altcoin reversals), #57 (integration), #63 (alert quality).
- PR #50 (read-only reversal engine), PR #58 (reversal WATCH delivery, currently based on PR #50), PRs #45, #46, #48, #55 and other open PRs. Inspect merge bases, changes, CI, and conflicts; do not blindly merge or duplicate.
- Modules include crypto_oracle_scanner.py, opportunity_alerts.py, telegram_notify.py, altcoin_reversal_*.py, evidence_audit.py, verification.py and tests.
- Current failure example: Solana token with ticker BTC but unrelated contract was sent as RESEARCH WATCH / WAIT AND VERIFY despite unverified identity and security. This must not recur as a token-level Telegram alert.

## Mandatory operating method
1. Baseline: inspect repository tree, workflows, active schedules, run logs, Telegram delivery accounting, open issues/PRs, existing tests and current architecture. Record reproducible failures and expected outputs.
2. Build a dependency-ordered implementation plan; execute it fully, continuously revisiting evidence and test outcomes. Avoid requiring user continuation prompts. If a permission or external service blocks work, report exact blocker, completed changes and actionable minimum request. Never imply unattended work continues after the session ends.
3. Implement on small reviewable branches, with tests and CI, and merge only after verification and required approval. Protect main and credentials.
4. Use only free existing GitHub infrastructure. Do not introduce paid providers, cloud VPS, subscription models or services without explicit authorization. Never print secrets or request exchange withdrawal/trading credentials.

## Repair workstreams
A. Discovery and capacity: preserve multi-chain sources, including Solana and EVM, with provenance, pagination, candidate prefilter, fair rotation and measured coverage. Diagnose why dozens of discovered pools lead to only ~6 assessed; add explicit counters and bounded workload scheduling. Separate launchpad/DEX discoveries from established Gate spot altcoins.
B. Identity: canonical chain + contract + pool + token metadata; check base/quote relationships and token symbol collisions, wrapped/pegged assets, impersonation, tokenized securities, stale feeds and source mismatches. A ticker such as BTC on a Solana meme token must never be represented as Bitcoin.
C. Security and evidence: independent sellability/honeypot/tax evidence; ownership/privileges; LP lock/burn and withdrawal controls; concentration and beneficial ownership limitations; supply/circulation, emissions, vesting/unlocks and bridge backing; volume authenticity, price corroboration, exchange listing, executable entry/slippage. Classify PASS/FAIL/UNKNOWN with source, timestamp, chain, contract and freshness; UNKNOWN cannot silently become PASS.
D. Market research: implement two independent research engines: (1) early-stage asymmetric opportunity research and (2) established-altcoin early bullish reversals. Integrate PR #50 and #58 carefully. For reversals use explainable trend/regime, support/resistance, volume, volatility, momentum and liquidity signals with no look-ahead bias. Add historical walk-forward backtests, realistic fees/slippage, out-of-sample tests and forward tracking. No promise of returns.
E. Admission: fail closed for BUY CANDIDATE — MANUAL REVIEW. Require all mandatory security, tokenomics, identity, freshness and execution gates; a strong market score alone never authorizes BUY. No autonomous orders. Keep LINK DEFERRED and AKE REJECTED unless independently re-reviewed and expressly approved.
F. Telegram: suppress all DISCARD/REJECT/INELIGIBLE, generic WAIT/WAIT AND VERIFY, unresolved identity, missing critical security and unverified symbol collisions from *individual token alerts*. Retain complete internal audit logs and compact operational digests. Send token-level alerts only for genuine, materially changed, high-quality research WATCH with verified identity and minimum evidence, or fully gated BUY CANDIDATE — MANUAL REVIEW. Deduplicate by canonical asset and setup, enforce cooldowns, message limits and delivery receipts; ensure retries do not create spam. Distinguish research-only alerts from BUY. Provide contract, chain, venue, timestamp, sources, market structure, proposed entry zone, invalidation/stop, targets, risk/reward, blockers and confidence limitations when supported; omit unsupported numerical levels rather than fabricate.
G. Reliability: review GitHub Actions cron, permissions, concurrency, caching, state persistence, API rate limits, timeouts, transient errors, observability, alerts on workflow failure and rollback. Never equate a successful workflow with valid research output. Protect Telegram tokens and all secrets.
H. Tests: unit, property, regression, integration, smoke and workflow tests covering ticker spoofing, Solana/EVM identity, failed/unknown sellability, stale prices, wash trading, fake BUY, high-score unsafe candidates, WATCH suppression, real reversal research eligibility, state/dedup, partial API failures, Telegram failure and recovery, and workflow scheduling. Run full test suite, compile checks, CI and controlled dry-run; capture commands, outputs, counts and commit SHAs.
I. Production: after tests and review, deploy only approved changes, verify live scheduled workflow and Telegram end-to-end, audit sample messages and coverage over multiple runs, monitor false positives and evidence completeness, and record rollback instructions. Report genuine BUY candidates only if all evidence gates pass; zero qualifying BUY candidates is an acceptable honest result.

## Definition of done
- All identified P0/P1 failures repaired or explicitly documented as external blockers.
- Reversal research is wired into production without weakening admission checks.
- Unsafe, generic WAIT and DISCARD candidates are absent from individual Telegram alerts.
- Meaningful qualifying WATCH alerts are delivered when genuine setups exist.
- BUY CANDIDATE — MANUAL REVIEW is possible when every mandatory gate genuinely passes, never forced.
- Full regression suite and CI green, live workflow evidence inspected, Telegram delivery verified, production state and rollback documented.
- Provide a final concise report with PRs, commits, tests, real run URLs, observed alert outcomes, remaining limitations and exact approvals needed. Never claim completion unless verified.

Proceed through investigation, implementation, testing, correction and verification without waiting for routine confirmations. Do not stop at writing another plan or prompt.

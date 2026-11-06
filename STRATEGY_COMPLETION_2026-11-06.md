# Strategy engineering acceptance matrix, 6 November 2026

Overall objective: **BLOCKED**. No validated strategy, live positive BUY admission,
or purchase authorization is asserted. This document supersedes older test counts,
not older retained evidence. Current baseline source is e7532e5967a51947b3b27e9be6ff96bcc5e1df08.

## Rechecked baseline

- Baseline compilation and all **633 tests pass locally** after retrieving both
  original historical fixtures. Test messages are mocked, not production sends.
- Latest inspected production run: https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/42133776942
  at 00:01–00:12 UTC on 6 November: 317 observations; 72 discovery-qualified
  pools; ten assessed; 62 deferred; eight adverse and two WAIT/VERIFY; zero core
  alerts. Twelve timeframe observations across six Gate pairs; four technical
  setups withheld (cooldown one, volume/boundary two, live-price divergence one),
  zero technical delivery errors. Historical validation still has zero records.
- Current admission_trust.json reviewers/sources/routers and gate_token_reviews.json
  tokens remain empty. No real reviewer enrollment, signed feed or bundle exists.
- Runtime preflight lacks ZEROX_API_KEY, ORACLE_TAKER_ADDRESS,
  ORACLE_FUNDING_TOKEN and ORACLE_ORDER_BASE_UNITS. Telegram bindings exist.
- AVAX/BNB/NEAR existing follow-up histories each contain five midpoint samples;
  these do not establish entry fills or strategy returns.

## Implemented experiment

Original Python implementation; no vendor source copied and no new framework or
paid dependency installed. Design references:
- https://www.freqtrade.io/en/stable/lookahead-analysis/
- https://hummingbot.org/strategies/v2-strategies/controllers/
- https://docs.jesse.trade/docs/research/optimize
- https://oss.octobot.online/developers/packages/backtesting
- https://help.3commas.io/en/articles/16281112-signal-bot-comprehensive-json-guide

strategy_lab_policy.json fixes three hypothesis families and costs/risk/split
rules. No optimization/search or test-driven threshold tuning is performed.
Daily/weekly Gate raw evidence already retained by production is replayed without
new production requests. The existing reversal detector remains unchanged.

strategy_lab.py uses shared plan/step logic for historical experiments and
prospective accounts. It supports pending entries, assumed capacity-limited
partial fills, cancelled remainders, pre-entry invalidation, expiry, open
positions, gap-sensitive stops, target/time exits, fees/slippage, marked drawdown,
exposure, turnover and closed-trade statistics. A limit touch is never treated as
a fill: the experiment explicitly uses next-bar-or-later buy-stop assumptions.
Same-bar target profit is withheld on entry; invalidation without a trigger
cancels; bars touching both entry and stop assume the adverse entry-then-stop
path, and ambiguous exits use stop-first. These are conservative assumptions,
not reconstructions of actual executions or guaranteed worst-case loss bounds.

Prospective accounts start on first real observation, never historical fills.
Only a full candle starting after a plan's observation time can trigger an entry.
Missed scans may replay existing positions/plans but never create intermediate
historical entry decisions. Closed-bar results are delayed research, not a live
stop service. Each account has a hash-linked event log; state publication rejects
rewritten event/trade/mark prefixes and preserves concurrent code changes.

Prospective pair/timeframe/strategy accounts are independent hypothetical USDT 1,000 accounts.
A separate retrospective strategy_portfolio.py replay partitions ONE USDT 1,000
balance into nonoverlapping static cash sleeves across the observed cohort. It
limits total pending/open positions to three, treats all pairs as one correlated
risk group, rotates deterministic simultaneous-signal order and reports aggregate
marked equity, closed trades, turnover and equal-weight buy-and-hold. No cash is
counted twice. It neither estimates empirical covariance nor claims optimal allocation. Allocation is at most 10%, planned
risk 1%, with gap loss explicitly unbounded by a guaranteed stop. The assumed
quote-volume participation cap does not establish historical depth or queue fills.

Chronological 50/25/25 descriptive splits have a 13-bar holding/entry embargo.
Historical warmup may precede a split, but no open position or pending order crosses
it. The final test is a fixed-rule descriptive screen, not independently certified
untouched data. Report unchanged rules, all strategies, buy-and-hold under the
same capital/allocation/cost assumptions (different actual exposure), and doubled
cost sensitivity. Numerical pass never authorizes promotion; current-survivor
selection and missing independent validation remain explicit blockers.

Technical messages may include an experimental 2R target/entry/stop/expiry/cost
plan only after replaying exact retained candles. The formula is not a forecast,
validated reward/risk or BUY eligibility. Caps, screening and deduplication remain.

pipeline_health.py reports DEGRADED and fails its health step when continued
research stages fail or required reports are absent. Artifacts and state still
publish under existing always conditions. Failure notification includes health.
COMPLETED stage execution remains distinct from BLOCKED overall admission.

## Local validation

Compilation, **663 unit tests**, workflow YAML parsing and whitespace checks pass.
Tests include replayed experimental message plans, causality, gap losses, partial
fills, absent capacity, expiry, split embargo, prefix-preserving state publication,
shared portfolio capital and global position caps. CI and production are recorded
separately below when available.

## Acceptance status

| Requirement | Status | Code/evidence | Remaining requirement |
|---|---|---|---|
| Discovery and safe notification suppression | Existing production verified | Latest baseline run; crypto_oracle_scanner.py | Sustained provider/scan coverage; fairer evidence prioritization |
| Three strategy hypotheses and frozen policy | Implemented/tested | strategy_lab.py; strategy_lab_policy.json | Broader representative data and independent review |
| Shared replay/prospective plan and lifecycle | Implemented/tested | strategy_lab_runner.py; tests/test_strategy_lab.py | Production state/artifacts; mature real observations |
| Partial fills/costs/gaps/ambiguity | Modeled under disclosed assumptions | strategy_lab.step | Historical executable depth/queue evidence |
| Portfolio capital/correlation controls | Implemented/tested under conservative static assumptions | strategy_portfolio.py; tests/test_strategy_portfolio.py | Dynamic allocation, empirical correlation and prospective portfolio validation |
| Chronological splits/bias disclosure/benchmarks | Implemented/tested | strategy_lab.evaluate | Point-in-time universe, delisted failures, regime/asset robustness and confidence |
| Historical/prospective strategy validation | BLOCKED | Numerical screen cannot promote | Adequate observations and preregistered independent validation |
| Complete research plan | Partial | technical_watch.message | Executable live sizing, validated targets, lifecycle notifications |
| Real candidate dossiers and reviewer intake | BLOCKED | Existing admission and context collectors | Authentic reviewers, source validation and complete exact-asset evidence |
| Venue-specific investment admission | BLOCKED | Existing Gate vs DEX paths preserved | Reviewed Gate cohort and strategy validation binding; no policy weakened |
| Explicit stage-health reporting | Implemented/tested | pipeline_health.py; main workflow | Post-deployment failure/health evidence |
| BUY CANDIDATE delivery | BLOCKED | Empty trust/review registries | Genuinely qualifying reviewed evidence plus validated strategy |
| Final CI and production | Pending | PR/run links to be recorded after execution | Inspect final-head checks and actual artifacts |

## First local public-data experiment

Bounded real Gate daily observations for AVAX_USDT, BNB_USDT and NEAR_USDT returned
RESEARCH_ONLY with retained metadata/candles. Initial transport failures were
retained as unavailable and a later independent bounded collection succeeded.
All nine strategy/asset final-test screens have insufficient evidence (0–6 closed
trades each). No strategy was promoted. Example closed-trade P&L under fixed paper
assumptions: AVAX reversal -6.92 USDT (one trade), BNB reversal -1.41 (three), BNB
pullback -10.43 (six); these are selected-snapshot descriptive simulated results,
not live returns. AVAX pullback positive P&L from two trades does not establish an
edge. Source raw data and exact hashes are retained by the CI probe artifact.

## Review and remaining dependencies

The full directive cannot be declared complete. External signed evidence and
real independent reviewers cannot be manufactured. Time-dependent forward results
cannot be accelerated. An alternative admission assurance policy requires explicit
user approval; this change proposes none and leaves all existing BUY gates intact.
The broader representative historical study, dynamic/prospective portfolio validation,
independent strategy-validation authority, provider coverage and complete live
lifecycle notifications remain engineering/research work, not merely credentials.

Rollback: revert this feature's source/workflow changes while preserving retained
strategy_lab_state.json and existing mutable histories. Never reset main or erase
old adverse/forward evidence. No account/order/signing API is introduced.

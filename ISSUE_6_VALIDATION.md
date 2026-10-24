# Issue 6 offline implementation and security review

Starting point: draft PR #7 head `062e93a173496244f48526a07d82dd794c2bc21e`.
This update is prepared for review, not approved for merge or deployment.

## Validation

Python 3.12: compileall and all **136 unittest cases pass** locally, including
all 78 baseline tests and all 12 tests from the original draft. Workflow YAML
parses; the hourly cron, concurrency, state persistence, secrets references,
scanner timeout, completion notification and failure notification are preserved.
The scanner artifact additionally retains evidence_report.json. No live scan or
Telegram delivery was attempted after the request to continue offline.

## Implemented behavior

- Exact-contract CoinGecko supply and valuation retrieval with per-field provider,
  URL, chain, contract, retrieval time, provider update time and response digest.
  Provider estimates remain UNVERIFIED; supply contradictions are CONFLICTING.
  The optional lookup has a five-second timeout and no retries.
- Independent supply comparison with explicit numeric validation and configurable
  disagreement tolerance. Claimed origins and distinct source families are both
  required. CoinGecko and GeckoTerminal are treated as one source family.
  Matching figures are CORROBORATED, not authenticated verification.
- Unlock schedule comparison requires two source families, explicit coverage and
  consistent event dates/amounts. Missing events do not mean no unlocks. Upcoming
  unlock totals are compared with circulating supply; large unlocks are flagged.
- Complete holder snapshots must reconcile to total supply. LP/CEX/burn exclusions
  require source-bound evidence and exact holder identity. The adjusted top-ten
  numerator and remaining-supply denominator are explicit. Incomplete lists,
  duplicates, invalid balances and missing exclusions fail closed.
- Exact-pool quote checks require network, base and quote tokens, observation and
  expiry, block, quote ID, bid/ask, order size, executable depth, fees, slippage and
  both buy and sell amounts. Stale, future, crossed, wide and thin quotes are
  rejected or flagged. Zero fees/slippage/spread are accepted only when explicit.
  Metric consistency does not establish simulation success or provider authenticity.
- GoPlus successful response code, exact token lookup, findings, retrieval time
  and response digest are retained. Pool identity must match the requested pool.
  Provider observations never become an independent audit. Critical concerns
  remain DISCARD / AVOID / HIGH CONCERN; offline records cannot hide live findings.
- Optional bounded offline evidence files are keyed to exact network/token/pool;
  malformed, oversized, duplicate and missing records remain UNVERIFIED. No URLs
  from these files are fetched. Provenance describes observations, not trust.
- Activity, security, fundamentals and trade readiness are labelled separately.
  Source estimates drive labelled dilution warnings without becoming buy authority.
  AXIS at 100 activity, VINU and unknown fixtures all remain WAIT / VERIFY.
- Decisions, gaps, timestamps and 3m/12m/3y scenario arithmetic precede verbose
  Telegram diagnostics. Unicode truncation respects UTF-16 limits. Delivery
  requires a positive integer Bot API message ID; mocked receipts are tests only.
- Evidence artifacts retain provider observations, raw research records, source
  reviews, decision blockers and market corroboration for review.

## Final offline security review

No private keys, auto-orders or transaction broadcasting are introduced. All
investment authorization stays fail-closed, including the legacy execution
validator: caller-controlled verified/authenticated booleans cannot authorize.
New remote lookups use a fixed HTTPS host and validated contract path. Solana
identity comparisons are case-sensitive. Provider findings with no flags are
never represented as safety verification. Numeric inputs reject booleans,
nonfinite values and extreme exponents. Evidence files have a two-megabyte bound.
Offline provenance does not establish source authenticity or ownership of a URL;
its records never authorize BUY. No probabilities or token price forecasts are
manufactured. Source timestamps refer to collection unless explicitly identified
as provider update times. Pool age does not establish token age.

## Remaining live verification and limitations

Reliable primary supply/vesting evidence, holder identities/exclusions, LP control
contracts, independent contract security and authenticated executable quotes must
still be obtained and reviewed for each token. These fields remain UNVERIFIED
when reliable evidence is absent. No live quote provider, RPC simulator or audit
trust authority is configured; local evidence validation cannot replace them.
Adoption claims remain UNVERIFIED. The scanner intentionally cannot issue BUY.

Compile/tests on the final remote commit, live provider integration, an actual
Telegram Bot API receipt, hourly workflow execution, any merge, and post-merge
verification must not be inferred from local results. No production deployment
has been performed by this update. Preserve the working hourly scanner on main.

Observed access limitations: Git over HTTPS failed because the inherited HTTP
proxy at proxy:8080 refused the connection. GitHub CLI authentication reported the
inherited GH_TOKEN invalid. Environment readiness listed no configured secret or
outbound identity bindings, and network policy enforcement was unknown. Credential
values were never requested or printed. The separate GitHub connector worked for
PR operations and the earlier commit's Actions run. No further CLI authentication
or provider network checks were run after the offline-only continuation request.

## Example alert (fixture, not live data)

    FINAL DECISION: WAIT AND VERIFY
    DECISION: WAIT / VERIFY
    EVIDENCE GATES: Activity is NOT safety.
    Security: INCOMPLETE
    Fundamentals/dilution: INCOMPLETE
    Trade readiness: NOT VERIFIED — no automatic BUY
    Supply / unlocks / adjusted holders / adoption / LP controls / execution: UNVERIFIED
    3m / 12m / 3y scenarios: P_future/P_now =
    (cap_future/cap_now)/(supply_future/supply_now).
    At every horizon, 2x cap with 2x supply = 1x price.
    Future inputs and probabilities: UNVERIFIED.

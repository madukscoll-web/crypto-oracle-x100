# Issue 6 upgrade validation — incomplete, not approved for deployment

Starting point: draft PR #7 head `062e93a173496244f48526a07d82dd794c2bc21e`.

Local verification: Python compileall and all 102 unittest cases pass. Both
workflow YAML files parse. The hourly cron, concurrency, state persistence,
Telegram secrets and failure notification steps are preserved. The scanner
artifact additionally retains evidence_report.json. Actual Actions execution
of these changes remains UNVERIFIED.

Changes: exact-contract CoinGecko supply and valuation retrieval with per-field
provider, URL, chain, contract, retrieval time, provider update time and response
digest. Provider estimates remain UNVERIFIED. Supply contradictions are labelled
CONFLICTING. Unsupported fields and API failures remain UNVERIFIED. Raw GoPlus
security findings retain source identity and observation time; no finding is
represented as an independent audit. Boolean assertions cannot remove independent
verification blockers. Decision, gaps, timestamps and scenario math precede
verbose diagnostics so Telegram truncation cannot remove them.

Security review: no keys, transactions or auto-orders were introduced. External
fundamentals use a fixed HTTPS provider host and a validated contract path.
Solana identity comparisons are case-sensitive. Numeric inputs reject booleans,
NaN, infinity and negatives. AXIS with 100 activity remains WAIT / VERIFY.
Critical GoPlus findings preserve the existing DISCARD decision and the gates
label AVOID / HIGH CONCERN. Quote claims never establish authenticity.

Remaining work: primary-source unlock/vesting verification; independent supply
corroboration; complete holder concentration with verified LP/CEX/burn exclusions;
LP control analysis; independent contract security evidence; authenticated exact
route buy/sell quote collection with order size, fees, spread, slippage and
executable depth; live provider integration checks; Telegram delivery receipt;
Actions validation; final review of the complete implementation; merge and
post-merge deployment verification. None of these are claimed complete.

Access blockers observed: inherited proxy proxy:8080 was unreachable, GH_TOKEN
was rejected, and the environment readiness report listed no configured secrets
or outbound identities. GitHub connector read/write access is separate from shell
access. Do not merge merely because offline tests pass.

Example alert prefix (illustrative fixture, not live market evidence):

    FINAL DECISION: WAIT AND VERIFY
    DECISION: WAIT / VERIFY
    EVIDENCE GATES: Activity is NOT safety.
    Security: INCOMPLETE
    Trade readiness: NOT VERIFIED — no automatic BUY
    Supply / unlocks / adjusted holders / adoption / LP controls / execution: UNVERIFIED
    3m / 12m / 3y scenarios: P_future/P_now =
    (cap_future/cap_now)/(supply_future/supply_now).
    2x cap with 2x supply = 1x price. Future inputs/probabilities UNVERIFIED.

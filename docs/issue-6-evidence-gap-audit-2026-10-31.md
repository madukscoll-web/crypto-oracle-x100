# Issue #6 evidence-gap audit (2026-10-31)

Status: **OPEN / NOT PRODUCTION-COMPLETE**. This is a source inspection, not proof of current runtime behavior. No BUY authorization or trading change is proposed.

## Source-confirmed gaps

1. `investment_gates.py::assess` unconditionally appends blockers for LP withdrawal authority, beneficial ownership and order-specific execution, and returns `buy_eligible: False` for every input. This is a deliberate fail-closed restriction, but the source currently offers no validated promotion path after complete evidence arrives. Do not replace this with permissive flags; implement a source-bound independently tested evidence-verification path first.
2. `evidence_audit.py::audit` hardcodes sellability, liquidity lock, holder distribution, unlocks and execution quote as UNKNOWN. This prevents unsupported claims, but the production audit cannot recognize future validated evidence without an authenticated adapter and verification policy.
3. `fundamental_evidence.py::collect` labels CoinGecko supply and valuation figures UNVERIFIED even after exact-contract matching. Unlocks, beneficial ownership, independent security, LP controls and executable quotes have no promotion in that module. Independent primary corroboration is needed.
4. `execution_quotes.py::collect` supports unsigned two-way 0x quotes for configured EVM networks but explicitly reports LIMITED. It does not establish funded sequential post-buy sellability, verified exact-pool execution, or approvals. It must never be treated as an independently verified exit.
5. `hourly_evidence.py::collect` imposes bounded candidate and request budgets and explicitly marks unsupported or unexamined candidates. `onchain` and supply adapters are conditional on supported EVM networks. Solana coverage must be assessed separately; do not infer equivalent security coverage from discovery support.
6. `.github/workflows/main.yml` schedules the scanner hourly at minute 7, runs compilation and unit tests, and has a Telegram failure notifier. The multichain and StonkFun audit steps use `continue-on-error: true`; their failure does not fail the scanner workflow. Their discovery reports explicitly disallow Telegram eligibility and BUY authorization. Distinguish optional discovery coverage from verified candidate evaluation.
7. `canonical_outcomes.py` maps research outcomes, but `VERIFIED BUY` is reachable only through the legacy opportunity classification plus `evidence_audit.audit(item)['trade_ready'] is True`. Verify all authorization gates jointly; never use caller-supplied `buy_eligible` or `decision`.

## Required implementation order

1. Build a versioned evidence schema with source, timestamp, exact chain/contract/pool, validation status, conflict handling and expiry.
2. Add independent sellability and LP-withdrawal checks where technically verifiable; label unsupported checks UNKNOWN rather than PASS.
3. Add holder-exclusion, unlock/vesting and supply reconciliation with provenance and conflict tests.
4. Add realistic trade-size quote, bid/ask or route, depth, gas, price impact, slippage and verified exit checks; refuse stale/mismatched data.
5. Introduce a strict single admission function that requires all mandatory validated evidence, independently adversarially tested. No score-only BUY path.
6. Separate DISCARD/REJECT internal diagnostics from WATCHLIST/BUY Telegram alerts. Ensure alert selection cannot bypass admission.
7. Test each provider outage and malformed/conflicting input, run the complete suite, then validate a real GitHub Actions scheduled run and Telegram delivery with actual run/job evidence.

## Acceptance evidence still required

- Reproducible tests and their exact results at a named commit SHA.
- Validated production configuration and scheduled-run conclusion.
- Real Telegram send success and message category verification (not just a passing workflow).
- Proven security, provenance and execution gates for any proposed BUY candidate.
- Human review for every purchase decision; automatic orders remain prohibited.

**Do not close Issue #6 or declare production completion on the strength of this audit alone.**

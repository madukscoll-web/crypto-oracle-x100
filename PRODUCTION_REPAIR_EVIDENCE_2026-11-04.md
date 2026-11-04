# Production repair evidence, 4 November 2026

**Overall project status: INCOMPLETE / BLOCKED.**
**Notification repair, rotating research collection and input forwarding: DEPLOYED AND PRODUCTION VERIFIED within the scope below.**

## 1. Implemented
- Evidence-only admission for secondary DEX research and legacy multipart notification routes, including cached retries.
- Confirmed Telegram receipts before delivered-state updates.
- One aggregate health digest per Lagos calendar day, persisted with serialized scanner state.
- Aggregate-only manual research summaries, without individual discarded or unverified contracts.
- Rotating Gate Spot daily/weekly research over a bounded six-pair batch, with exclusions, coverage, deferred and unavailable counts.
- Optional quote-setting forwarding and diagnostics that name missing/invalid settings without revealing their values.

## 2. Repaired
The secondary research path admitted generic WAIT observations based on activity and did not positively require identity and critical evidence. It now recomputes canonical admission and requires a complete independent audit. The legacy multipart path has the same evidence guard.

The production workflow previously supplied only Telegram environment variables to the scanner. Repository quote secrets/variables therefore could not reach the existing quote adapters. Explicit forwarding now works; production confirms the inputs themselves are still missing or invalid.

## 3. Tests
- Local: `python -m compileall -q *.py tests` passed.
- Local: `python -m unittest discover -s tests -q`, 532 tests passed.
- All ten existing workflow YAML files parsed; modified workflow also executed successfully in GitHub Actions.
- [PR 65 CI, 528 tests](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41924606889).
- [PR 66 CI, 532 tests](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41925585232).
- Latest production logs independently show 532 tests passing before the real scan.

Tests cover the spoofed BTC-symbol incident, caller-supplied approval labels, missing security, cached delivery bypass, corrupt/foreign state, unconfirmed receipts, Lagos midnight deduplication, rotating coverage, daily/weekly history, excluded instruments, unknown turnover, provider outages and configuration non-disclosure.

## 4. Commits and pull requests
- [PR 65](https://github.com/madukscoll-web/crypto-oracle-x100/pull/65), merged as `ed9516582c591c7386c7e617b6ad181648025577`.
- [PR 66](https://github.com/madukscoll-web/crypto-oracle-x100/pull/66), merged as `cbfe701426ad480c7ad992cd031fb32be42ca410`.
- Latest verified source: `cbfe701426ad480c7ad992cd031fb32be42ca410`.
- State publication after the latest scan: `1172162da7baa82e3e413b68f418a1a016ee687a`, preserving tested source and existing history.
- Existing PRs 50 and 58 were inspected and preserved. Their unverified WATCH formatter was not deployed.

## 5. Production evidence

| Observation | First repaired run | Latest run |
| --- | --- | --- |
| Run | [41924706241](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41924706241) | [41925740600](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41925740600) |
| Workflow | Success | Success |
| DEX discovery candidates | 63 | 64 |
| DEX candidates assessed | 6 | 6 |
| Individual DEX BUY alerts | 0 | 0 |
| Individual DEX research alerts | 0 | 0 |
| Suppressed assessments | 4 REJECT, 2 insufficient evidence | 5 REJECT, 1 insufficient evidence |
| Gate catalog / active altcoin pairs | 2,188 / 1,534 | 2,188 / 1,534 |
| Turnover-eligible pairs | 81 | 81 |
| Selected pairs / timeframe assessments | 6 / 12 | 6 / 12 |
| Successful research / unavailable histories | 9 / 3 | 8 / 4 |
| Technical hypotheses, not approved alerts | 2 | 3 |
| Health digest | Bot API receipt confirmed | SKIPPED_DAILY_DEDUP |
| Rotation cursor after publication | 6 | 12 |

The first digest's confirmed marker remains unchanged after the second run. These are actual exchange observations, not verified token identities, calibrated predictions or purchase authorizations. A zero-alert run is not proof that no opportunities exist.

Inspected both diagnostic ZIPs and verified their SHA-256 digests against GitHub:
- First artifact 13369945886: `9d2c5fdad0ac7461d0d1c491d565f27e1f81220f98dafb8e62c31e5943a42f42`.
- Latest artifact 13368484051: `c4ee7301417c72416a4d18fda8bb9d11b5cf1d0fd4cce32a33465b6b53bbeb70`.

Artifacts are retained for seven days; the run logs and this report provide longer-lived summary evidence.

## 6. Remaining limitations and blockers
- Production reports MISSING_OR_INVALID_INPUTS for ZEROX_API_KEY, ORACLE_TAKER_ADDRESS, ORACLE_FUNDING_TOKEN and ORACLE_ORDER_BASE_UNITS.
- Independent LP withdrawal controls, beneficial-owner concentration, source authority, complete supply/unlocks and funded exact-route execution are not established. Some chain adapters remain unsupported.
- The DEX trade-ready audit and authenticated execution validator deliberately remain fail-closed. Input forwarding alone does not implement or certify full investment admission.
- Gate's named-human-reviewed registry remains empty. No placeholder reviewer or approval was added.
- The source-bound historical cohort remains empty. Representative, non-leaky strategy validation and qualified reversal-alert delivery remain incomplete.
- DEX enrichment remains bounded to six assessments per run. Reversal enumeration covers the catalog, but only six pairs receive daily/weekly candle analysis each run; 75 turnover-eligible pairs were deferred in each observed run.
- Relative strength, independent candle corroboration, full evidence dossiers and executable forward paper-state validation remain outstanding.
- No genuine BUY candidate or profitable strategy is claimed. Issues 6, 49, 57 and 63 remain open.

## 7. Minimum operator action
For quote probes, configure the four settings documented in [EXECUTION_CONFIGURATION_REPAIR.md](EXECUTION_CONFIGURATION_REPAIR.md) through GitHub Actions secrets/variables. Use an existing permitted provider credential, a public address, an exact chain-specific funding contract and an explicitly chosen reference size. Do not send API credentials in chat; no private key or seed phrase is required.

Those inputs unblock quote collection, not the remaining security reviews or strategy validation. No token approval is requested because none currently satisfies admission. Purchases remain subject to the user's final approval; no order was placed and no paid service was introduced.

The hourly GitHub scanner remains scheduled. This report does not claim autonomous engineering continues after the active session. Rollback procedures are recorded in INCIDENT_63_REPAIR.md; preserve state and ledger history when reverting source.

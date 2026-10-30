# Verification coverage and alert repair

## Diagnosis

Remote main and `fix/explicit-evidence-coverage-reasons` both pointed to
`989b22e72f8365ecf9ab4d92b931ba43bb82fcd7` at inspection. Compared with local
`91878b5`, only persisted history/watchlist files changed. Issue #6 remains open.
Recent production runs 40960173359 and 40988055355 succeeded with zero token
alerts; the latter passed 370 tests and observed 301 pools / 69 research leads.
Telegram confirmations in unittest output are mocks, not production receipts.

The old independent collector rejected Solana identities and all but three EVM
chains before requesting evidence. Unsupported checks, transport failures,
missing credentials and actual inconclusive observations shared UNKNOWN states.
Failed requests used provider keys, leaving mandatory check keys absent. Three
candidate slots / 60 seconds were shared with Gate research. Selection reused
alert quotas, left new-pool slots idle, and repeatedly chose top-ranked silent
candidates. Full beneficial ownership, vesting and independent security are
still missing because no complete trustworthy evidence exists; these cannot be
fixed by relabelling provider screening as safety.

## Implementation

- Explicit complete-gate coverage: UNSUPPORTED, NOT_CHECKED, UNKNOWN, FAILED,
  VERIFIED. Original provider states/raw evidence remain intact for existing
  consumers. LIMITED/CORROBORATED do not verify complete gates. VERIFIED is used
  only for named narrow Solana account/authority claims with RPC evidence.
- GoPlus screening for all seven discovery EVM networks; independent honeypot
  simulator only for its reviewed Ethereum/Base/BSC network set. No unsupported
  simulator calls or fabricated alternate-pool results.
- Solana mainnet genesis check, finalized exact legacy SPL mint account,
  initialization/type/program checks, exact integer supply/decimals, explicit
  mint/freeze authority observations and largest token-account snapshots. Active
  mint/freeze authority is adverse under conservative policy. Token-2022 needs a
  reviewed extension parser and stays unsupported. Largest accounts are not
  beneficial owners. Gross supply is not circulating supply or unlock coverage.
- Every mandatory gate retains chain/token/pool, timestamp, reason and source.
  HTTP permission/credential denials and exhausted budgets are NOT_CHECKED;
  attempted but inconclusive/outage responses are UNKNOWN. Security failures
  remain adverse; no automatic trading or relaxed BUY requirements.
- Six research slots, 240-second / 270-request shared envelope, 40-second /
  45-request candidate envelope. Prefer new pools but fill spare research slots
  with existing pools. Oldest persisted evidence check rotates first; duplicate
  discovery token hints share a slot. Gate catalog/research follows core checks.
  Primary supply comparison precedes bounded eight-address EVM holder sampling.
  Exhaustion remains explicit; no claim that every discovered token was checked.
- Existing incomplete/rejected-alert suppression remains. Confirmed deliveries
  persist both original pool key and chain/token key, preventing repeat signals
  through alternate pools. Existing pool-only history is preserved; old token
  identities cannot be reconstructed when absent. Ambiguous Telegram transport
  acceptance before a crash still cannot provide exactly-once delivery.
- Hourly cron, state-only rebase/push, artifacts, operational failure notification
  and Gate Spot research remain. Pushes to main affecting scanner adapters also
  run the production workflow, allowing verification of a merged deployment.
- CI runs a bounded public integration probe with no secrets, orders or messages.
  It checks schema, identity binding and fail-closed behavior. Availability is
  reported separately; an outage never becomes a security pass.

## Validation before PR

Python compilation succeeded; all 386 unit tests passed. `git diff --check`
passed. Regressions cover unsupported chains/programs, missing credentials,
provider denials/outages, malformed mint evidence, active authorities, budget
exhaustion/fairness, persistent rotation, alternate-pool/token deduplication and
partial-versus-complete evidence. Existing positive alert-predicate fixtures are
mocked gates, not genuine BUY signals. Local live integration is blocked by an
unreachable inherited proxy; GitHub Actions integration and post-merge production
results must be recorded separately before claiming deployment verification.

## Remaining limitations

No reviewed Solana exact-pool sell simulator, pool withdrawal/control adapter,
Token-2022 parser or funded sequential execution adapter is configured. EVM
on-chain pool/holder adapters still cover Ethereum/Base/BSC; other EVM networks
receive provider screening with explicit on-chain coverage limitations. Complete
independent security, related-wallet beneficial ownership, circulating supply,
vesting and order-specific execution remain required. Public observations alone
cannot satisfy those gates. A zero-BUY run is expected when those gates are absent.

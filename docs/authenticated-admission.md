# Authenticated positive evidence admission

This implementation supports **BUY CANDIDATE — MANUAL REVIEW**, never an order.
`authenticated_admission.evaluate` is the positive evidence authority used by the
scanner, execution predicate, evidence audit, investment assessment and canonical
classification. Missing, adverse, conflicting, malformed, stale or unauthenticated
mandatory evidence blocks admission. Activity and caller-set verification flags
cannot create a positive decision.

## Trust and limitations

The production `admission_trust.json` intentionally contains no invented reviewers,
providers or live evidence. It must be populated through reviewed repository
configuration with two genuinely independent review organizations and their
Ed25519 public keys. Private keys never belong in this repository or the scanner.
Each reviewer needs `organization`, `public_key` (Ed25519 SPKI PEM), `revoked:false`,
`valid_from`, `valid_until`, and all five `scopes`: `security`, `lp_controls`,
`holders`, `tokenomics`, `execution`. Reusing one public key or organization for two
reviewers is rejected. Enrollment expiry and revocation are checked every time.
Router identities also require `routers[network+":"+router_address]` enrollment with an independently reviewed runtime SHA-256 and allowed four-byte selectors. Each quote must carry matching router bytecode. Transfer evidence in both simulated legs must involve the exact pool; a route label alone is insufficient.

Provider domains also require `sources[hostname].organization` enrollment; a
caller cannot invent source independence by supplying organization strings.

A signature proves the enrolled reviewer's identity and the integrity of the
reviewed payload. It does **not** prove that assertions in a review are true.
Both independent organizations must actually validate the primary evidence,
source provenance, source independence, complete authority/ownership coverage and
simulation request/results before signing. This is a review-attestation adapter,
not a claim that GoPlus, 0x or a public RPC signs its API responses. A dishonest
or compromised pair of trusted reviewers is outside the cryptographic guarantee.
Machine checks additionally reject inconsistent and incomplete signed assertions.

No current live candidate or provider response has been promoted by this change.
Synthetic keys and signed examples exist only in temporary test directories.
Enrollment and an evidence publishing service are external production prerequisites.

## Intake and signature format

An evidence bundle has exactly the decision material in `payload` and a
`signatures` array of `{reviewer, signature}` entries. Signatures use Ed25519 over
`authenticated_admission.canonical(payload)`: sorted JSON keys, no spaces,
ASCII escaping, UTF-8 bytes, no NaN/Infinity. Signatures are base64. Verification
uses OpenSSL `pkeyutl` without a shell, private keys or transaction operations.
A missing/incompatible OpenSSL binary blocks admission.

The payload schema is `authenticated-admission-v1`, with timezone-aware
`observed_at`, `expires_at` and `identity`: exact `network`, `token`, `pool`,
`funding`, `block_number`, `block_hash`, `block_timestamp`, `runtime_sha256`.
The signed `entry_status` must be READY or MONITOR. MONITOR can produce WATCHLIST after all mandatory safety checks pass, but never authorizes BUY. Whole-bundle lifetime and quote ages are at most 60 seconds. Block timestamps
must also be within that interval. This deliberately requires a fresh review
publisher; checking a days-old audit document cannot establish a current exit.

The five evidence sections require a PASS review verdict, metrics, and at least
two enrolled independent source organizations. Every source contains provider,
organization, exact network/contract, HTTPS URL, observation time, VERIFIED
status, explicit NONE conflict status, raw evidence and SHA-256 of canonical raw
JSON. `raw.metrics` is the independently normalized observation and must equal
the reviewed metrics. Raw original responses/review artifacts should accompany
that normalized observation. Known CoinGecko/GeckoTerminal mirrors remain one
source family. Source metadata alone never overrides signature requirements.
Do not include API credentials, private keys or personal nonpublic data in evidence.

The scanner can receive a bundle as `item.admission_bundle`, read a repository
snapshot from `admission_evidence/<asset-hash>.json`, or fetch the exact identity
from a repository-enrolled HTTPS `bundle_endpoint`. Asset hash is SHA-256 of
canonical `{network,token,pool}` using the item's exact values. The feed request
adds only those three public identity query parameters; a caller cannot choose
the endpoint. Feeds require two enrolled reviewers, bounded response/request
handling, five-second positive/negative transport caching, and existing provider
session budgets when present. Every cached response is still authenticated and
checked for expiration on every admission call. Transport success is never PASS.

The complete executable synthetic schema is constructed in
`tests/test_authenticated_admission.py::fixture`; it is not live evidence.

## Mandatory semantic checks

- Security: runtime bytecode must hash to the exact reviewed runtime hash; all enumerated honeypot, blacklist,
  balance mutation, mint, upgrade, pause, tax modification and privileged-wallet
  controls absent; bridge backing independently reconciled or explicitly native
  and not applicable; buy/sell/transfer taxes at most 5%.
- LP controls: exact pool; no uncovered withdrawal authority; burned plus locked
  units equal all LP units, with a minimum 30-day release horizon for locks.
  A concentrated pool needs independently established equivalent custody proof;
  its TVL or provider locker label does not establish coverage.
- Holders: complete attested beneficial-owner inventory, unique owner groups,
  exact supply reconciliation and reviewed exclusions. The top ten groups may
  control at most 50% of nonexcluded supply. Address lists alone do not establish
  beneficial ownership; the independent reviews must support that coverage claim.
- Tokenomics: circulating <= total <= maximum; holder total equals token total;
  exact circulating/team/treasury/other allocation reconciliation; complete
  enforceable vesting inventory and at least one year of unlock coverage.
  Vesting calculations recompute 30-day unlocks and remaining locked supply.
  Upcoming unlocks may not exceed 10% of circulation; FDV/cap at most 5, with
  their ratio consistent with maximum/circulating supply within 0.01. Market capitalization must also agree within 2% with circulating units and the executable token price.
- Execution: two validated unsigned 0x-shaped legs at the same pinned block, with a matching fresh RPC snapshot,
  exact token/funding identity and independently attested exact-pool routes;
  actual funding/allowance prerequisites; unexpired quotes, <=1% minimum-output
  slippage. The reverse size is the buy's minimum token output. The exact
  `eth_simulateV1` request is reconstructed with validation and without state,
  balance or approval overrides. All eight evolving-state calls must succeed;
  transfer logs and balance changes must agree with actual spend/minimum outputs.
  Gas is bounded from transaction gas budgets and L2 total network fees; explicit
  fee fields must be valued and reconciled. Funding decimals and USD price
  recompute order/exit value. Total round-trip loss plus gas/fees <=5%, impact
  and spread <=1%, executable depth >=100x order and >=$1,000, allocation <=10%
  of attested equity. Native-principal routes and unvalued fee assets are blocked.

Current support is restricted to reviewed EVM-shaped evidence on Ethereum, BSC,
Base, Arbitrum, Polygon, Avalanche and Optimism. Listing a network is **not** proof
of live simulator/provider coverage. Unsupported Solana admission remains blocked.
Neither successful eth_call nor a sellable provider label substitutes for the
sequential balance/transfer proof. Trusted source authenticity and pool/authority
reviews remain external attestation responsibilities.

## Reporting and hourly operation

Canonical outcomes are BUY CANDIDATE — MANUAL REVIEW, WATCHLIST, WAIT/VERIFY,
REJECT and DISCARD. High-ranked legacy research with mandatory gaps remains
WAIT/VERIFY. Legacy setup names remain internal compatibility metadata. Positive
Telegram alerts are rebuilt from fresh admission and contain exact chain/contract,
pool, discovery source, review identities, bundle digest, expiry, mandatory checks,
valuation and execution summaries, and loss risks. They are length-checked before
sending rather than truncating mandatory evidence. Unchanged signed WATCHLIST/BUY categories are deduplicated per exact chain/token; a WATCHLIST-to-BUY promotion can notify once after confirmed delivery. Confirmed delivery still
requires the Bot API receipt; ambiguous transport responses may duplicate a send.

`python admission_preflight.py` records credential-safe configuration blockers in
`work/admission_preflight.json`; configuration is not live verification. The
hourly scanner step binds optional `ZEROX_API_KEY` from repository secrets and
public `ORACLE_TAKER_ADDRESS`, `ORACLE_FUNDING_TOKEN`, `ORACLE_ORDER_BASE_UNITS`
from repository variables. Existing Telegram secrets and hourly cron remain intact.

`hourly_health.py` compares actual scheduled scanner starts. A gap over 90 minutes
is DEGRADED, regardless of successful job conclusions. The next scheduled run can
send one health alert and retain `work/hourly_health.json`. This cannot detect a
missing trigger while no runner is running and cannot guarantee GitHub's scheduler.
A separate reliable scheduler/watchdog is required for a continuous-operation SLA.

The existing `independent-research.yml` manual workflow already supports an isolated
scanner run and a labelled real Telegram validation/failure drill. It must be run
on the reviewed revision with the appropriate repository credentials. PR offline
or provider-probe success is not deployment or Telegram-delivery evidence.

## Reproduction and rollback

Run compilation and the complete unittest suite. The signed fixture exercises the
actual signature verifier and semantic checks with a fixed test clock, then the
scanner, canonical classifier, investment gate, audit and simulated Bot API receipt.
It does not replace provider authentication or claim live delivery.

Admission diagnostics retain signed positive evidence, bundle/trust hashes and
evaluation time. The forward ledger policy hash now includes the admission code,
trust registry, adverse policy and sequential validator. Never edit old events.

No automatic trading is enabled. Before production integration, enroll real
independent reviewers/providers, install a fresh evidence feed, supply quote/RPC
prerequisites and validate an actual candidate, live Telegram receipt and repeated
scheduled execution. Revert the admission implementation commit to return to the
prior fail-closed behavior; no production deployment has yet occurred.

A signed feed may supply verified quotes independently of this runtime's optional 0x collector. Missing local quote credentials are reported separately as collector limitations, not proof that an independently operated feed is unusable. Telegram credentials in this workspace are separate from GitHub repository secrets; only an actual run and receipt establishes deployment delivery.

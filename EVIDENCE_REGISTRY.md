# Exact-contract evidence registry

`evidence_registry.json` is versioned with the code. It starts empty deliberately: the reference tokens do not come with a reviewed escrow inventory or complete, attributable unlock disclosures. Never populate it from token symbols, marketing claims or guessed schedules.

`tokens` maps `network:lowercase-token-address` to a disclosure containing:

| Field | Required meaning |
|---|---|
| `network`, `token_address` | Exact identity of the disclosure |
| `source_url` | Public HTTPS primary disclosure or provider record |
| `observed_at` | Timezone-bearing retrieval timestamp, at most one day old |
| `total_supply_base_units`, `circulating_supply_base_units` | Explicit integer token base units, not dollar values |
| `schedules` | Nonempty list of allocations with unique `id`, `kind` (`cliff` or `linear`), positive integer `amount_base_units`, and timezone-bearing `start`/`end` |

A cliff has equal start/end timestamps. Linear allocations vest continuously using integer arithmetic. Disclosed future unlocks are reported for 7, 30, 90 and 365 days against the disclosed circulating supply. Duplicate IDs, overallocated or contradictory supply, stale records and wrong identities are rejected. This module cannot certify that the disclosure is complete or that on-chain vesting/minting authority matches it. Its result stays LIMITED. Missing data is UNKNOWN, never zero dilution.

`lp_locks` maps `network:lowercase-pair-address` to a list of reviewed escrow descriptors:

| Field | Required meaning |
|---|---|
| `standard` | `openzeppelin_token_timelock` |
| `address` | Exact escrow contract |
| `runtime_sha256` | SHA256 of exact deployed runtime bytecode, including immutable constructor values; no proxy or wildcard matching |
| `review_source_url` | Public source/build review evidence |

At a fresh pinned block the inspector checks runtime fingerprint, `token()`, `beneficiary()`, `releaseTime()`, and LP `balanceOf()`. Release must be more than 30 days away. Duplicate escrow/burn addresses cannot be double-counted. Results remain LIMITED because a configured fingerprint does not prove an independent source/build review or complete lock inventory. Do not add arbitrary hashes merely to make a check appear green.

The live LP adapter currently recognizes only Ethereum canonical Uniswap V2 factory `0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f`. It cross-checks `factory()`, `token0()`, `token1()` and the factory's `getPair()`. V3/V4 NFTs and other factories remain UNKNOWN. LP locks cannot protect against malicious token supply, transfer or reserve behavior.

Holder observations come from on-chain balances at the same block, with zero/dead address balances reported separately. Provider LP/exchange labels and common-funder heuristics do not establish beneficial ownership. Without independently verified ownership and complete coverage, the possible common-control upper bound remains 100%.

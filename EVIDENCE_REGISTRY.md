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

Reviewed per-chain factory and position-manager mappings are recorded with official sources in `chain_factories.json`. V2 identity cross-checks the actual factory and getPair; supported V3 and Base Slipstream identity cross-check getPool using the correct fee or signed tick-spacing key. Bounded NFT checks bind positions and ownerOf to that exact pool. V4, complete NFT inventories, lock withdrawal restrictions and beneficial identity remain UNKNOWN. LP locks cannot protect against malicious token supply, transfer or reserve behavior.

Holder observations come from on-chain balances at the same block, with zero/dead address balances reported separately. Provider LP/exchange labels and common-funder heuristics do not establish beneficial ownership. Without independently verified ownership and complete coverage, the possible common-control upper bound remains 100%.

## Public source and provider adapters

Sourcify v2 exact-runtime source matches are compared against independent pinned RPC bytecode. `source_profiles.json` pins every source/dependency hash for the OpenZeppelin v4.9.6 simple TokenTimelock profile; extra or substituted sources cannot match it. Automated escrow discovery examines provider-nominated LP holders, verifies actual selected-pool holdings and deployed code, and only inspects this canonical source profile. It does not assume that a missing or bounded candidate list is a complete lock inventory. Independent local compiler reproduction remains unverified.

Safe service owner lists and thresholds are compared with on-chain `getOwners()`/`getThreshold()`. This corroborates signing authority, not beneficial persons, custody customers, hidden modules or unrelated wallets.

`provider_bindings` optionally maps `network:lowercase-token-address` to `tokenomist_id`, `source_url` and timezone-bearing `observed_at`. Bindings must be sourced, fresh and manually attributable: Tokenomist's token-list API does not contain contract addresses, so the engine never guesses a slug from a name or symbol. `TOKENOMIST_API_KEY` stays in runtime secrets and is sent only in the documented `x-api-key` header. API quota metadata is excluded from saved evidence.

The Tokenomist v5 adapter checks allocation TBD/untracked amounts and up to four 100-row daily-emission pages over an explicit 365-day window. Missing, stale, duplicate, overlapping or inconsistent pages stay unresolved. An empty dataset cannot establish zero future unlocks. Even a complete queried window is not complete lifetime supply/vesting/mint coverage.

Expanded live coverage and exact public/credential/account-state boundaries: [21 October report](validation/larger-scan-2026-10-21.md). Diagnostic calldata parameter matching is not execution proof; reference senders are rejected by funded execution verification. Session budgets and host/resource circuit breakers preserve unavailable evidence.

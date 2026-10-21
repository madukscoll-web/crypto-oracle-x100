# Expanded bounded live verification — 21 October 2026

Existing draft PR #4. No BUY signal. Automated trading, signing, approvals and broadcasts remain disabled.

## Exact accounting

Collection: 2026-10-21T21:18:19.593213+00:00 through 2026-10-21T21:23:11.704961+00:00 (UTC). Follow-up observations have separate timestamps and request ledgers in the raw evidence. Saved quotes are expired historical evidence, never current executable offers.

180 pool observations; 179 unique discovered pools; 22 discovery-qualified; 157 excluded by discovery filters (not security rejections). Twelve assessed: seven discovery-qualified and five explicitly verification-only. One rejected; eleven assessed remain unverified. Fifteen qualified pools were not assessed. Across all discovered pools, 178 remain unverified and one is rejected; zero verified BUY signals.

Nine of twelve requested feed pages succeeded. BSC new page 2 was rate-limited; BSC trending pages were skipped during cooldown. Missing pages do not represent empty markets. The earlier partial attempt is retained separately and is not added to these totals.

## Scoped corroboration

| Check | Count |
|---|---:|
| pool identity corroborated | 6 |
| fungible lp observed | 1 |
| concentrated pool identity | 5 |
| holder balance observations | 12 |
| ownable owner returned | 4 |
| source runtime matches | 1 |
| independent sellability results | 2 |
| two way calldata built | 8 |
| encoded parameter pairs matched | 6 |
| funded sequential execution verified | 0 |
| unique safe signer sets corroborated | 0 |
| unique nft position owners corroborated | 8 |
| nft position owner disagreements | 0 |

Pool identities, NFT owners and `owner()` roles are scoped facts, not complete LP inventory, escrow withdrawal restrictions, legal beneficial ownership or authority audits. Safe requests now use EIP-55; corrected live non-Safe lookups returned 404, not an inferred signer set. Eight position owners were bound to the exact Ethereum pool; other-pool positions were excluded.

## Candidate decisions

Every assessment below also lacks complete beneficial-owner concentration, circulating supply/unlock/mint coverage, funded sequential execution, complete order costs/risk sizing and validated historical entry evidence. Verification-only entries cannot become BUY merely by passing security checks.

### eth — `0x232ce3bd40fcd6f80f3d55a522d03f25df784ee2`

Pool: `0x8366b1dde4de12c8806985fbb599d408d92d01a6faf2e478cc6bb76189cc00f1`. Decision: **WAIT AND VERIFY**. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### base — `0x940181a94a35a4569e4529a3cdfb74e38fd98631`

Pool: `0xdfe5f275020def30993f042174fc2d335678b626`. Decision: **WAIT AND VERIFY**. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### bsc — `0xb9e8f30729a6b5e84cc6a86fe2fbdcbd48d8115a`

Pool: `0x795f7917ca5f6244d6b0992e7d47090feb95eee2`. Decision: **WAIT AND VERIFY**. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Verification-only cohort: original market discovery filters failed; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### eth — `0x28d4e499c4cde621e1cea7c9cbf9d43bf75a9525`

Pool: `0x2c2226a6381e68a86c1a8dcb8d9fdab050959dd5`. Decision: **WAIT AND VERIFY**. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### base — `0x311935cd80b76769bf2ecc9d8ab7635b2139cf82`

Pool: `0x1131db5977242a03ebead1acd18f80a9a29e5922`. Decision: **WAIT AND VERIFY**. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### bsc — `0xc7d3871be1e5ad7b38846468430228f6c4e97777`

Pool: `0x3a2feefb8f3adbcefd39404ed77f9f410e751c62`. Decision: **WAIT AND VERIFY**. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

Token identity scope: Base token from GeckoTerminal pool relationship.

- Verification-only cohort: original market discovery filters failed; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: Insufficient fresh closed five-minute candles
- Exact-pool market corroboration: Provider prices differ 6.4%

### eth — `0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7`

Pool: `0xb07d640fd9e2eb9dc81b953c8e4fd006bdfeaf276010fb5418eb763ca15abfb3`. Decision: **WAIT AND VERIFY**. Missing or uninterpretable provider security fields: cannot_sell_all. Independent security, sellability, tokenomics and execution evidence is incomplete; limited provider checks are not a contract audit.

Token identity scope: Base token from GeckoTerminal pool relationship.

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: Malformed historical candle evidence

### base — `0x29cc30f9d113b356ce408667aa6433589cecbdca`

Pool: `0x83f3aca29bc79b048b99c56013475570acc97ccf`. Decision: **DISCARD**. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### bsc — `0x739d1108949a0a4e0683a4037802f9630045b6ea`

Pool: `0x023f841d8d137338d1bfaaad16e5cb523c8fd215f732f909080c193de7952b52`. Decision: **WAIT AND VERIFY**. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Verification-only cohort: original market discovery filters failed; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup
- Exact-pool market corroboration: Exact pool/base-token match absent

### eth — `0xea67a73c3eb902cb8a26fa123a3b8dea52a856ea`

Pool: `0x8a567d591a4b1874781ef82cf13fb45ef75d694ecbd83da511666bd0f663517b`. Decision: **WAIT AND VERIFY**. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Verification-only cohort: original market discovery filters failed; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### base — `0xb2000000000000000000004884b426556b92883d`

Pool: `0x8b27f626ab668197000bc722a1012022caed10e2`. Decision: **WAIT AND VERIFY**. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

Token identity scope: UNVERIFIED (discovery hint only; fresh pool binding unavailable).

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### bsc — `0x69f345f15b1cba542a47a3af15fde6052e2dffff`

Pool: `0x69f345f15b1cba542a47a3af15fde6052e2dffff`. Decision: **WAIT AND VERIFY**. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

Token identity scope: Base token from GeckoTerminal pool relationship.

- Verification-only cohort: original market discovery filters failed; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: Insufficient fresh closed five-minute candles
- Exact-pool market corroboration: Exact pool/base-token match absent

## Access and execution boundaries

Public checks completed: documented chain factory/getPair/getPool identity, RPC balances and ownership roles, bounded NFT custody, source/runtime and ABI matching, independent sellability reports, keyless two-way route/build responses and encoded minimum-output/recipient/amount checks. Builds use an explicit reserved diagnostic sender and base-unit reference order; they do not prove funded execution or runtime slippage enforcement.

Tokenomist credentials and reviewed contract bindings are absent; complete unlock coverage is blocked. Optional 0x requires a key; keyless Kyber supplies diagnostic alternatives. Base Blockscout returned HTTP 403 once and was disabled for that session. Denied hosts are not repeatedly retried; rate limits have one bounded cooldown recovery and request/time budgets.

Non-overridden unsigned execution simulation needs a specified public taker, adequate existing balances and allowances. Those account-state prerequisites are absent. No funded transaction is required for public identity/custody/calldata checks. Actual settlement, realized fees and trading performance require transactions and were excluded. No private keys are accepted.

Full observations, exact per-provider responses/statuses and follow-up timestamps: [compressed raw evidence](larger-scan-2026-10-21.json.gz). Regression validation: 133 tests passed locally, retaining all original tests; Python compilation and actionlint passed. GitHub runtime results are recorded on PR #4 after the final code push. Telegram receipt was personally confirmed previously; read-only deployment preflight is retained.

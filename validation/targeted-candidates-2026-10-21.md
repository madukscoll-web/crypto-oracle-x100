# Targeted candidate requirements review — 21 October 2026

Existing draft PR #4; no new discovery, merge, trading, signing, approvals or broadcasts. **No verified BUY. Every reviewed candidate is excluded from BUY consideration.**

## Scope and exact accounting

Fresh evidence collection: 2026-10-21T21:41:37.746780+00:00–2026-10-21T21:49:27.010705+00:00 UTC. Additional custody/authority observations: 2026-10-21T21:49:40.686765+00:00–2026-10-21T21:50:58.474617+00:00 UTC. Each API/RPC observation has its own timestamp/block. Quotes are historical and expired, not executable current offers.

All **15 previously unassessed discovery-qualified pools** were assessed first, followed by **all 11 previously unverified candidates**. Of these **26 pools**, **seven were rejected and 19 remain unverified**. All original eleven remain excluded as unverified. The earlier separately rejected pool remains rejected and was not needlessly re-probed.

On the original saved universe of 179 unique pools (180 observations), this completes assessment of all 22 historically discovery-qualified pools. The cumulative assessment set is 27 pools: eight rejected, 19 assessed but unverified. Another 152 discovery-filter-excluded pools remain unassessed. Thus 171 of 179 discovered pools remain unverified overall. These are historical-cohort counts; old discovery qualification is not fresh entry evidence.

## Operational evidence, with limits

| Check | Current targeted count |
|---|---:|
| pool identity corroborated | 20 |
| fungible lp observed | 7 |
| concentrated pool identity | 13 |
| holder balance observations | 25 |
| ownable owner returned | 10 |
| source runtime matches | 5 |
| independent sellability results | 9 |
| two way calldata built | 23 |
| encoded parameter pairs matched | 23 |
| funded sequential execution verified | 0 |
| unique safe signer sets corroborated | 9 |
| unique nft position owners corroborated | 17 |
| nft position owner disagreements | 0 |

Six additional Aerodrome V2 pool identities were corroborated using the documented factory, stable/volatile boolean key, and exact minimal-proxy implementation binding. They remain subject to adverse simulator reports; identity does not clear sellability. Nine distinct Safe signer sets and seventeen NFT position owners are scoped signing/custody facts, not beneficial identity or complete position inventories.

Public Coinbase issuer data and independent pinned RPC agree on AAPLc current supply (7570.95493938 tokens, 8 decimals) and MSTRc current supply (10333.02900487 tokens, 8 decimals). Both observed share multipliers were 1. These are timestamped supply observations, not live prices, unlock guarantees or reserve attestations.

## Original eleven: mandatory evidence matrix

LIMITED means an observed subset, never a passed mandatory gate. Every row lacks complete beneficial ownership, future supply/authority coverage, funded sequential execution, all order fees/gas and approved risk/entry evidence.

| Chain / exact contract | Pool/liquidity identity | Token source / current supply | Independent sellability / calldata policy | Decision |
|---|---|---|---|---|
| eth `0x232ce3bd40fcd6f80f3d55a522d03f25df784ee2` | UNKNOWN: Unsupported pair/factory or unavailable LP proof | UNKNOWN / LIMITED | UNKNOWN / LIMITED | EXCLUDED |
| base `0x940181a94a35a4569e4529a3cdfb74e38fd98631` | AerodromeSlipstream; complete escrow UNKNOWN | LIMITED / LIMITED | UNKNOWN / LIMITED | EXCLUDED |
| bsc `0xb9e8f30729a6b5e84cc6a86fe2fbdcbd48d8115a` | PancakeV3; complete escrow UNKNOWN | UNKNOWN / LIMITED | UNKNOWN / UNKNOWN | EXCLUDED |
| eth `0x28d4e499c4cde621e1cea7c9cbf9d43bf75a9525` | UniswapV3; complete escrow UNKNOWN | UNKNOWN / LIMITED | LIMITED / LIMITED | EXCLUDED |
| base `0x311935cd80b76769bf2ecc9d8ab7635b2139cf82` | AerodromeSlipstream; complete escrow UNKNOWN | UNKNOWN / CONFLICTING | UNKNOWN / LIMITED | EXCLUDED |
| bsc `0xc7d3871be1e5ad7b38846468430228f6c4e97777` | PancakeV2; observed burn 0.00000000%; complete escrow UNKNOWN | UNKNOWN / UNKNOWN | UNKNOWN / LIMITED | EXCLUDED |
| eth `0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7` | UNKNOWN: Unsupported pair/factory or unavailable LP proof | UNKNOWN / LIMITED | UNKNOWN / LIMITED | EXCLUDED |
| bsc `0x739d1108949a0a4e0683a4037802f9630045b6ea` | UNKNOWN: Unsupported pair/factory or unavailable LP proof | UNKNOWN / LIMITED | UNKNOWN / UNKNOWN | EXCLUDED |
| eth `0xea67a73c3eb902cb8a26fa123a3b8dea52a856ea` | UNKNOWN: Unsupported pair/factory or unavailable LP proof | UNKNOWN / LIMITED | UNKNOWN / LIMITED | EXCLUDED |
| base `0xb2000000000000000000004884b426556b92883d` | AerodromeSlipstream; complete escrow UNKNOWN | UNKNOWN / LIMITED | UNKNOWN / LIMITED | EXCLUDED |
| bsc `0x69f345f15b1cba542a47a3af15fde6052e2dffff` | UNKNOWN: Unsupported pair/factory or unavailable LP proof | UNKNOWN / LIMITED | UNKNOWN / UNKNOWN | EXCLUDED |

## Exact findings and remaining requirements per assessment

### 1. base `0x940181a94a35a4569e4529a3cdfb74e38fd98631`

Pool `0x6cdcb1c4a4d1c3c6d054b27ac5b77e89eafb971d`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

- Liquidity: AerodromeV2; observed burn 0.00000018%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: LIMITED. Source service match corroborated with RPC runtime; no full authority, ownership or vesting-completeness audit Diagnostic: {}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native prices agree; GeckoTerminal source timestamp and executable gas estimate remain unverified
- Adverse provider diagnostic (not an independent proof of malicious intent): execution reverted: "revert: Target contract does not contain code". The provider router field is ''. The existing exclusion gate remains enforced.
- Source/runtime-bound authority getter follow-up: [{"signature": "minter()", "output_type": "address", "value": "0xeb018363f0a9af8f91f06fee6613a751b2a33fe5"}]. Source/runtime-bound getter observations; complete dependency, bridge-peer, mint and transfer authority audit remains unverified
- Public disclosure review: Official documentation describes ongoing emissions, not fixed zero dilution. Exact runtime-bound Aero source exposes mint/setMinter; fresh minter() equals the officially listed Minter 0xeb018363f0a9af8f91f06fee6613a751b2a33fe5. Complete current veNFT release inventory, future governance decisions and authority dependency audit remain incomplete. Sources: https://aerodrome.finance/docs, https://aerodrome.finance/security

Remaining mandatory blockers:

- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No confirmed volume-supported breakout

### 2. base `0x9eadbe35f3ee3bf3e28180070c429298a1b02f93`

Pool `0xbe4c36b9542610df83ca690c8b5bc53bbbc5d542`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Missing or uninterpretable provider security fields: cannot_sell_all. Independent security, sellability, tokenomics and execution evidence is incomplete; limited provider checks are not a contract audit.

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native prices agree; GeckoTerminal source timestamp and executable gas estimate remain unverified

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No confirmed volume-supported breakout

### 3. base `0x07b3d902783c3c12b077508c3b5c00113d1291d0`

Pool `0x2df380544b88adb3ad0a94100dcc45fd705aae2d`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. No specified risk flags detected in returned fields; not proof of safety. Independent security, sellability, tokenomics and execution evidence is incomplete; limited provider checks are not a contract audit.

- Liquidity: UniswapV3; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: LIMITED. Independent buy/sell simulation succeeded; size-specific quotes still required
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native prices agree; GeckoTerminal source timestamp and executable gas estimate remain unverified

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No confirmed volume-supported breakout

### 4. base `0xacfe6019ed1a7dc6f7b508c02d1b04ec88cc21bf`

Pool `0x01784ef301d79e4b2df3a21ad9a536d4cf09a5ce`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

- Liquidity: AerodromeV2; observed burn 0.00000000%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Adverse provider diagnostic (not an independent proof of malicious intent): execution reverted: "revert: Target contract does not contain code". The provider router field is ''. The existing exclusion gate remains enforced.

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 5. base `0x9b5e262cf9bb04869ab40b19af91d2dc85761722`

Pool `0x85f1aa3a70fedd1c52705c15baed143e675cd626`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

- Liquidity: AerodromeV2; observed burn 0.00000000%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Adverse provider diagnostic (not an independent proof of malicious intent): execution reverted: "revert: Target contract does not contain code". The provider router field is ''. The existing exclusion gate remains enforced.

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 6. base `0xef5997c2cf2f6c138196f8a6203afc335206b3c1`

Pool `0x995985c9027e8a90c823a5e0a9112fea72d1f4dd`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

- Liquidity: AerodromeV2; observed burn 0.00000000%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Adverse provider diagnostic (not an independent proof of malicious intent): execution reverted: "revert: Target contract does not contain code". The provider router field is ''. The existing exclusion gate remains enforced.

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup
- Exact-pool market corroboration: Provider prices differ 5.8%

### 7. base `0x11030f79109269d796fd0fb956d6244e502757f7`

Pool `0x0ab02e160f0df68dc049b012c514857306960eae`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: UNKNOWN: Exact supported pool/custody not corroborated. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: No canonical supported-pool proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 8. base `0xfb31f85a8367210b2e4ed2360d2da9dc2d2ccc95`

Pool `0x566bee7ef7b39f29d150ab3be6b6242c17cc5a31`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

- Liquidity: AerodromeV2; observed burn 0.00000000%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Adverse provider diagnostic (not an independent proof of malicious intent): execution reverted: "revert: Target contract does not contain code". The provider router field is ''. The existing exclusion gate remains enforced.

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 9. base `0x6985884c4392d348587b19cb9eaaf157f13271cd`

Pool `0x717e174d5dae280802d1a2c15c1c0976561a3f61`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Independent evidence failed: market_depth, independent_supply_comparison

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: LIMITED. Source service match corroborated with RPC runtime; no full authority, ownership or vesting-completeness audit Diagnostic: {}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Source/runtime-bound authority getter follow-up: [{"signature": "owner()", "output_type": "address", "value": "0x28937ca4873f7289ebea0708c4e42b24835ecff0"}]. Source/runtime-bound getter observations; complete dependency, bridge-peer, mint and transfer authority audit remains unverified

Remaining mandatory blockers:

- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No confirmed volume-supported breakout

### 10. base `0x940181a94a35a4569e4529a3cdfb74e38fd98631`

Pool `0x4e506648d493c8870f55e870480f92f2f33ece51`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Independent evidence failed: independent_contract_security, independent_tokenomics

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: LIMITED. Source service match corroborated with RPC runtime; no full authority, ownership or vesting-completeness audit Diagnostic: {}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Source/runtime-bound authority getter follow-up: [{"signature": "minter()", "output_type": "address", "value": "0xeb018363f0a9af8f91f06fee6613a751b2a33fe5"}]. Source/runtime-bound getter observations; complete dependency, bridge-peer, mint and transfer authority audit remains unverified
- Public disclosure review: Official documentation describes ongoing emissions, not fixed zero dilution. Exact runtime-bound Aero source exposes mint/setMinter; fresh minter() equals the officially listed Minter 0xeb018363f0a9af8f91f06fee6613a751b2a33fe5. Complete current veNFT release inventory, future governance decisions and authority dependency audit remain incomplete. Sources: https://aerodrome.finance/docs, https://aerodrome.finance/security

Remaining mandatory blockers:

- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 11. base `0xe0cd4cacddcbf4f36e845407ce53e87717b6601d`

Pool `0x9331f571f79d1e186a095c93756b5680a43932ac`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Critical security concern: owner_change_balance=1: Owner can change balances. Do not treat high volume or activity as a reason to override this warning.

- Liquidity: UniswapV3; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: LIMITED. Source service match corroborated with RPC runtime; no full authority, ownership or vesting-completeness audit Diagnostic: {}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Adverse provider diagnostic (not an independent proof of malicious intent): HONEYPOT DETECTED. The provider router field is '0x2626664c2603336E57B271c5C0b26F421741e481'. The existing exclusion gate remains enforced.
- Source/runtime-bound authority getter follow-up: [{"signature": "bridge()", "output_type": "address", "value": "0x4200000000000000000000000000000000000010"}, {"signature": "remoteToken()", "output_type": "address", "value": "0xe5e0b73380181273abcfd88695f52c4d0c825661"}]. Source/runtime-bound getter observations; complete dependency, bridge-peer, mint and transfer authority audit remains unverified

Remaining mandatory blockers:

- Critical provider security concern: owner_change_balance=1: Owner can change balances; hidden_owner=1: Hidden owner; is_mintable=1: Minting capability reported
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 12. base `0x3ec2156d4c0a9cbdab4a016633b7bcf6a8d68ea2`

Pool `0x385b47e56b73eb6549378f78f7c7cbc42c56c9e0`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 13. base `0xb200000000000000000000c2e324d24d7eecd1fb`

Pool `0xa3b1e3f9747065e2073722ff4c9027d3ea4994f0`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "HTTPError", "http_status": 404}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Issuer stock reference: LIMITED. Issuer reference and pinned supply agree; no complete mint/unlock, reserve, beneficiary or execution proof

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 14. base `0x311935cd80b76769bf2ecc9d8ab7635b2139cf82`

Pool `0xccfa472815563ff9eb2de95c7b2be1ccf91f7f31`; cohort `previously_unassessed_qualified`; decision **WAIT AND VERIFY**, excluded from BUY. Independent evidence failed: independent_supply_comparison

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "HTTPError", "http_status": 404}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Official deployment documentation binds this Base wrapped SOL address. Bridge mint/burn mechanics mean local ERC20 supply is not global SOL circulation. Reserve reconciliation, in-flight transfers, validator/upgrade powers and cross-chain dilution evidence remain incomplete. Sources: https://docs.base.org/specifications/base-protocol/bridging/base-solana-bridge, https://github.com/base/sol2base/blob/main/README.md

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No confirmed volume-supported breakout

### 15. base `0x8c0d3adcf8ce094e1ae437557ec90a6374dc9bdd`

Pool `0xe2444faa67022125a059c19d5737d8e4dad251fa`; cohort `previously_unassessed_qualified`; decision **DISCARD**, excluded from BUY. Exact-chain/token/pool independent provider reports honeypot; other provider clearance cannot override this adverse evidence.

- Liquidity: AerodromeV2; observed burn 0.00000000%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: FAIL. Independent provider reports honeypot
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Adverse provider diagnostic (not an independent proof of malicious intent): execution reverted: "revert: Target contract does not contain code". The provider router field is ''. The existing exclusion gate remains enforced.

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Independent provider reports honeypot
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 16. eth `0x232ce3bd40fcd6f80f3d55a522d03f25df784ee2`

Pool `0x8366b1dde4de12c8806985fbb599d408d92d01a6faf2e478cc6bb76189cc00f1`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: UNKNOWN: Unsupported pair/factory or unavailable LP proof. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Official utility page retrieved HTTP 200, but it does not supply a complete exact-contract allocation/vesting inventory. Direct issuer announcement returned HTTP 403 in web access; not retried. Third-party schedule dates disagree; no machine-verified binding or vesting contracts admitted. Sources: https://docs.lighter.xyz/about-lighter/lit-utility.md, https://x.com/Lighter_xyz/status/2005862682608472263

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 17. base `0x940181a94a35a4569e4529a3cdfb74e38fd98631`

Pool `0xdfe5f275020def30993f042174fc2d335678b626`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Prior failed/conflicting evidence remains unresolved; see retained timestamped observations

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: LIMITED. Source service match corroborated with RPC runtime; no full authority, ownership or vesting-completeness audit Diagnostic: {}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Source/runtime-bound authority getter follow-up: [{"signature": "minter()", "output_type": "address", "value": "0xeb018363f0a9af8f91f06fee6613a751b2a33fe5"}]. Source/runtime-bound getter observations; complete dependency, bridge-peer, mint and transfer authority audit remains unverified
- Public disclosure review: Official documentation describes ongoing emissions, not fixed zero dilution. Exact runtime-bound Aero source exposes mint/setMinter; fresh minter() equals the officially listed Minter 0xeb018363f0a9af8f91f06fee6613a751b2a33fe5. Complete current veNFT release inventory, future governance decisions and authority dependency audit remain incomplete. Sources: https://aerodrome.finance/docs, https://aerodrome.finance/security

Remaining mandatory blockers:

- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup
- Unresolved prior contract_security: Contract capability or sellability concern reported
- Unresolved prior tokenomics: Mint authority creates dilution exposure

### 18. bsc `0xb9e8f30729a6b5e84cc6a86fe2fbdcbd48d8115a`

Pool `0x795f7917ca5f6244d6b0992e7d47090feb95eee2`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

- Liquidity: PancakeV3; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "HTTPError", "http_status": 404}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Keyless quote unavailable, stale, identity-conflicting, unsupported or missing explicit order configuration Calldata policy: Two live calldata builds unavailable; no encoded slippage claim Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Bounded exact-contract public web search found no usable issuer allocation/vesting disclosure. This is a retrieval limitation, not proof that no disclosure exists. RPC/provider findings below are retained; no symbol-only or zero-unlock inference is used. Sources: 

Remaining mandatory blockers:

- Verification-only or historical cohort: not a fresh discovery-qualified setup; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 19. eth `0x28d4e499c4cde621e1cea7c9cbf9d43bf75a9525`

Pool `0x2c2226a6381e68a86c1a8dcb8d9fdab050959dd5`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: UniswapV3; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: LIMITED. Independent buy/sell simulation succeeded; size-specific quotes still required
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Helix AI website and Helix lending documentation describe different protocol/chain contexts. Ticker and a shared supply headline cannot bind the lending allocation to this Ethereum contract. No complete contract-bound vesting inventory admitted. Sources: https://helix.org/, https://docs.helix.org/whitepaper, https://docs.helix.org/whitepaper/helix-token/tokenomics

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 20. base `0x311935cd80b76769bf2ecc9d8ab7635b2139cf82`

Pool `0x1131db5977242a03ebead1acd18f80a9a29e5922`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Independent evidence failed: independent_supply_comparison

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ProviderUnavailable", "http_status": null}.
- Current supply: CONFLICTING. CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native prices agree; GeckoTerminal source timestamp and executable gas estimate remain unverified
- Public disclosure review: Official deployment documentation binds this Base wrapped SOL address. Bridge mint/burn mechanics mean local ERC20 supply is not global SOL circulation. Reserve reconciliation, in-flight transfers, validator/upgrade powers and cross-chain dilution evidence remain incomplete. Sources: https://docs.base.org/specifications/base-protocol/bridging/base-solana-bridge, https://github.com/base/sol2base/blob/main/README.md

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Supply evidence conflict: CoinGecko total differs from gross on-chain supply by more than 0.1%; burn/circulation methodology unresolved
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No confirmed volume-supported breakout

### 21. bsc `0xc7d3871be1e5ad7b38846468430228f6c4e97777`

Pool `0x3a2feefb8f3adbcefd39404ed77f9f410e751c62`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

- Liquidity: PancakeV2; observed burn 0.00000000%; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "HTTPError", "http_status": 404}.
- Current supply: UNKNOWN. Pinned supply/units or independent evidence unavailable
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Bounded exact-contract public web search found no usable issuer allocation/vesting disclosure. This is a retrieval limitation, not proof that no disclosure exists. RPC/provider findings below are retained; no symbol-only or zero-unlock inference is used. Sources: 

Remaining mandatory blockers:

- Verification-only or historical cohort: not a fresh discovery-qualified setup; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP permanent-burn coverage observed 0.000000%; complete corroborated escrow coverage/review unavailable
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup
- Exact-pool market corroboration: Provider prices differ 35.4%

### 22. eth `0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7`

Pool `0xb07d640fd9e2eb9dc81b953c8e4fd006bdfeaf276010fb5418eb763ca15abfb3`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: UNKNOWN: Unsupported pair/factory or unavailable LP proof. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Issuer token page binds the exact address and describes FP/VIBE/IMD renaming and cross-chain supply. This resolves the naming lead, but the issuer supply/burn claim is not independently reconciled across Ethereum, Base and Robinhood, bridge peers, hooks and authorities. Sources: https://imd.fun/token/, https://imdusd.com/docs/reference/contracts-and-addresses/

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 23. bsc `0x739d1108949a0a4e0683a4037802f9630045b6ea`

Pool `0x023f841d8d137338d1bfaaad16e5cb523c8fd215f732f909080c193de7952b52`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

- Liquidity: UNKNOWN: Unsupported pair/factory or unavailable LP proof. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Execution: Keyless quote unavailable, stale, identity-conflicting, unsupported or missing explicit order configuration Calldata policy: Two live calldata builds unavailable; no encoded slippage claim Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Bounded exact-contract public web search found no usable issuer allocation/vesting disclosure. This is a retrieval limitation, not proof that no disclosure exists. RPC/provider findings below are retained; no symbol-only or zero-unlock inference is used. Sources: 

Remaining mandatory blockers:

- Verification-only or historical cohort: not a fresh discovery-qualified setup; ineligible for BUY
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

### 24. eth `0xea67a73c3eb902cb8a26fa123a3b8dea52a856ea`

Pool `0x8a567d591a4b1874781ef82cf13fb45ef75d694ecbd83da511666bd0f663517b`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

- Liquidity: UNKNOWN: Unsupported pair/factory or unavailable LP proof. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "ValueError", "http_status": null}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Bounded exact-contract public web search found no usable issuer allocation/vesting disclosure. This is a retrieval limitation, not proof that no disclosure exists. RPC/provider findings below are retained; no symbol-only or zero-unlock inference is used. Sources: 

Remaining mandatory blockers:

- Verification-only or historical cohort: not a fresh discovery-qualified setup; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Simulator requires a 20-byte pool address; this discovery pool identifier is unsupported
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup
- Exact-pool market corroboration: Provider prices differ 25.9%

### 25. base `0xb2000000000000000000004884b426556b92883d`

Pool `0x8b27f626ab668197000bc722a1012022caed10e2`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Token identity could not be verified. Confirm the exact contract and independently check sellability, holders, and liquidity lock.

- Liquidity: AerodromeSlipstream; complete escrow UNKNOWN. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "HTTPError", "http_status": 404}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim Calldata policy: Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified Gas valuation: Native prices agree; GeckoTerminal source timestamp and executable gas estimate remain unverified
- Issuer stock reference: LIMITED. Issuer reference and pinned supply agree; no complete mint/unlock, reserve, beneficiary or execution proof
- Public disclosure review: Public exact-contract issuer record and pinned RPC agree on current supply, with share multiplier retained. B20 precompiles do not have ordinary contract bytecode. Current supply/NAV do not establish legal beneficiary registers, reserves, issuer roles, future mint/burn/corporate actions or execution. Omitted pause fields are not interpreted as a safety clearance. Sources: https://docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks, https://docs.base.org/sdks/tokenized-stocks/overview

Remaining mandatory blockers:

- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- Canonical concentrated-pool identity corroborated; complete position NFT custody and escrow coverage remain unverified
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup

### 26. bsc `0x69f345f15b1cba542a47a3af15fde6052e2dffff`

Pool `0x69f345f15b1cba542a47a3af15fde6052e2dffff`; cohort `previously_unverified`; decision **WAIT AND VERIFY**, excluded from BUY. Original market discovery filters failed; verification-only observations cannot qualify for BUY.

- Liquidity: UNKNOWN: Unsupported pair/factory or unavailable LP proof. NFT/custody/escrow observations do not establish full beneficial control or enforceable exit coverage.
- Security source: UNKNOWN. Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion Diagnostic: {"error_type": "HTTPError", "http_status": 404}.
- Current supply: LIMITED. Current supply observations only; complete circulating ownership, future unlocks and mint authority remain unverified
- Unlocks: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution Tokenomist API key or sourced exact-contract provider binding missing; no slug/symbol guessing
- Independent sellability: UNKNOWN. Provider unavailable or invalid response: HTTPError
- Execution: Keyless quote unavailable, stale, identity-conflicting, unsupported or missing explicit order configuration Calldata policy: Two live calldata builds unavailable; no encoded slippage claim Gas valuation: Native price evidence unavailable, stale, malformed or unsupported
- Public disclosure review: Bounded exact-contract public web search found no usable issuer allocation/vesting disclosure. This is a retrieval limitation, not proof that no disclosure exists. RPC/provider findings below are retained; no symbol-only or zero-unlock inference is used. Sources: 

Remaining mandatory blockers:

- Verification-only or historical cohort: not a fresh discovery-qualified setup; ineligible for BUY
- Exact source/bytecode verification unavailable: Exact source/chain/runtime match unavailable; no source-based safety or supply conclusion (HTTP 404)
- Independent contract mint/upgrade/transfer authority audit is incomplete
- LP coverage unknown: Unsupported pair/factory or unavailable LP proof
- Beneficial ownership and related-wallet concentration coverage are incomplete; signing addresses do not prove beneficial persons
- Complete circulating supply, vesting/unlocks and mint authority are unverified: No exact-contract sourced unlock disclosure; missing data does not mean zero dilution
- Exact-pool independent sellability: Provider unavailable or invalid response: HTTPError
- Funded size-specific sequential buy/sell execution, allowances and minimum-output proof unavailable
- Order-specific total fees/gas, approved slippage, equity sizing and historical invalidation are not fully verified
- Entry evidence: No verified historical setup
- Exact-pool market corroboration: Exact pool/base-token match absent

## What public access could and could not establish

Public: exact supported factory/pool identity, fungible LP burn balances, bounded NFT owners/approvals, token/holder balances, current issuer supply, source/runtime matches, current minter/owner/bridge getters, Safe owner/threshold agreement, and unsigned keyless routes/calldata parameter checks. None requires private keys or funded transactions.

Incomplete public reconstruction: full V3/V4 position and escrow inventories, hook behavior, all withdrawal/upgrade/dependency paths, related-wallet attribution, circulating allocations and all bridge/vesting releases. Some source/role data is available, but a complete independent audit was not achieved. This is not presented as a problem solvable merely by buying credentials. Legal beneficiaries behind custodians may not be publicly disclosed at all.

Credential-dependent: Tokenomist API key plus reviewed exact-contract bindings remain absent; optional 0x also lacks a key. Public disclosures and keyless Kyber were used instead where scoped evidence exists. Missing schedules never mean zero unlocks.

Account-state-dependent: a specified funded public taker, order, balances and existing allowances are absent. Non-overridden unsigned buy-then-sell simulation cannot pass with the diagnostic fixture. Its builds deliberately disable funded gas estimation. No wallet signing, token approvals, balance overrides or actual transactions were performed. L2 data fees and complete gas/slippage enforcement remain unverified. Realized performance needs settlement evidence and was not invented.

Access: 1769 attempted requests in the main targeted session, with HTTP-error counts {'404': 56, '429': 5, '400': 3}. The inherited Base Blockscout 403 host denial was retained without a new probe. HTTP 404 resources are cached; rate limits permit one bounded cooldown recovery. Provider cooldown/absence is not a negative market finding. Additional sessions have separate ledgers in raw evidence.

## Validation and reproduction

All original tests preserved; **146 tests pass locally**. Compilation, actionlint and diff checks pass. Added regressions preserve the saved backlog despite changing filters, retain unresolved adverse observations, bind Aerodrome bool-key/clone identity, validate issuer pagination/missing supply and reject supply rounding conflicts.

```sh
python -m unittest discover -s tests -v
python reassess_candidates.py --input validation/larger-scan-2026-10-21.json.gz --output work/reassessment.json.gz
```

The committed raw report includes the separately timestamped additional public observations. Latest-commit GitHub Actions and read-only Telegram preflight results are linked in PR #4 after push; prior successful Telegram receipt remains personally confirmed. No duplicate Telegram test message is needed.

[Full raw targeted evidence](targeted-candidates-2026-10-21.json.gz). [Public disclosure/access review](targeted-public-disclosure-review-2026-10-21.json).

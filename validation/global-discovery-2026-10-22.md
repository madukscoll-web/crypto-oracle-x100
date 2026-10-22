# Global discovery / Gate Spot — first complete research increment

Existing Draft PR #4, branch `improve-independent-verification`. No merge, deployment, Telegram transmission, approvals, signatures, account requests or orders. Trading remains disabled.

## Audit and smallest safe sequence

Before this increment: PR head `cbf92e4`; 147 committed tests plus unfinished watch-alert work (172 total passing workspace tests). Existing validation included 27 assessed pools, retained adverse decisions, strict independent BUY gates, public RPC/source/LP/quote adapters, Telegram preflight and stateful paper tracking. Unfinished watch functionality was preserved and included in this change, not discarded.

1. Canonical chain/contract identity, four modular public discovery adapters and bounded source fallback.
2. Exact-contract Gate Spot identity/tradability, public books/candles and conditional manual-research references.
3. Later increments: independently reconstruct missing risk evidence, calibrated historical cohorts, developer/adoption analysis, expanded permissions/LP/unlock coverage. Missing components remain UNKNOWN, not passed.

## Implemented boundary

Global discovery runs independently of Gate. Tokens are deduplicated with EIP-155 chain IDs or Solana mainnet CAIP-2 plus canonical contracts; Solana case is preserved. Pool observations are retained, never summed into duplicated liquidity/volume. Tickers are display metadata only. A Solana case-insensitive comparison in the existing independent-market adapter was corrected and tested.

New/trending GeckoTerminal feeds cover Solana, Ethereum, Base and BNB Chain. A bounded latest-profile DEX Screener fallback is available when a chain has no primary discovery results. Promotional profiles are not organic-adoption proof; an independent Gecko confirmation is required for corroboration of fallback leads. Request budgets, host/resource circuit breakers, one bounded cooldown recovery and short explicit caching remain active.

The Gate catalog is joined on exact chain/contract first. Wallet-chain evidence must agree, with an enabled network and a fresh normal two-way Spot pair. Blank native addresses are not wrapped-token aliases. Missing, ambiguous, disabled, premarket, ST or future-start evidence blocks eligibility. Futures, Web3, Trenches and Alpha endpoints are not used. Absence of an exact contract mapping means UNKNOWN, not proof a token is unlisted everywhere.

Public Spot books provide spread, bounded depth and hypothetical size-specific gross VWAP/slippage for an explicit 100-USDT diagnostic notional. USDT is not silently equated to USD. Account maker/taker fees, eligibility, balances, net proceeds and actual fills remain UNKNOWN. Candles must be closed, contiguous, fresh and geometrically valid. Any conditional limit reference is observed support rounded down to the pair tick, not an order, entry signal or price forecast. Rejected/high-risk candidates cannot receive an entry reference.

Global categories are EARLY DISCOVERY, WATCH, HIGH RISK, REJECTED and VERIFIED BUY. Existing HIGH-PRIORITY WATCH and ENTRY WATCH are preserved as WATCH subtypes. Known failures and historical exclusions override scores and Gate eligibility. VERIFIED BUY still requires the original independent audit, execution and risk gates; this increment does not manufacture the missing evidence.

Activity scores are transparent/configurable via `watch_policy.json` and receive zero Gate-listing bonus. They are explicitly uncalibrated heuristic research scores, never return probabilities. Circulating supply, holder attribution, developer history, complete permissions, LP withdrawal risk, unlocks, volume authenticity and adoption remain separately status-labelled. Market cap/FDV are provider estimates, not reconciled facts. No labelled forward-test dataset exists here to claim calibration.

## Actual local live results

Collection: 2026-10-22T16:02:49.093226+00:00–2026-10-22T16:04:34.065562+00:00 UTC (**17:02–17:04 Africa/Lagos, 22 October 2026**). Eight first-page feeds succeeded. These are bounded historical snapshots; prices and 30-second book windows are expired.

| Measurement | Actual count |
|---|---:|
| pool observations | 160 |
| unique chain pool keys | 160 |
| unique chain contracts | 151 |
| assessed unique tokens | 8 |
| unassessed unique tokens | 143 |
| gate spot eligible | 1 |
| verified buy | 0 |
| EARLY DISCOVERY | 1 |
| REJECTED | 5 |
| HIGH RISK | 2 |

No WATCH or VERIFIED BUY qualified. The 143 unassessed token identities remain unverified; discovery inclusion is not approval.

| Chain / exact token | Category | Gate Spot | Decision basis |
|---|---|---|---|
| eth `0x4e67db19044549ff420860834c91b45bad298722` | EARLY DISCOVERY | UNKNOWN | Fresh independent market corroboration; security/advanced evidence still incomplete. Pool age does not prove early token launch |
| base `0x29cc30f9d113b356ce408667aa6433589cecbdca` | REJECTED | CONFIRMED_SPOT | Unresolved previously excluded exact token/pool evidence retained |
| bsc `0x91152b4ef635403efbae860edd0f8c321d7c035d` | REJECTED | UNKNOWN | contract_security: Contract capability or sellability concern reported |
| solana `CSocnzcRpgSCr1naKcNTieWZUxb6rABe45j844m7pump` | HIGH RISK | UNKNOWN | Thin/abnormal or one-sided market flow; wash trading/manipulation not ruled out |
| eth `0x07696dcab55e62cfef953666b29fe1970518cb00` | REJECTED | UNKNOWN | contract_security: Contract capability or sellability concern reported |
| base `0x5be75e3b0aff5d1a042a5363ae36acb1d6d755ea` | REJECTED | UNKNOWN | contract_security: Contract capability or sellability concern reported |
| bsc `0x4902c5ebc598265ed2212b559b042de8a5eeec3f` | REJECTED | UNKNOWN | contract_security: Contract capability or sellability concern reported |
| solana `EhuiZVks9ExNTQUg2ZLeW4SQUMAGiwwhK73rASzBpump` | HIGH RISK | UNKNOWN | Thin/abnormal or one-sided market flow; wash trading/manipulation not ruled out |

The EARLY DISCOVERY Ethereum contract `0x4e67db19044549ff420860834c91b45bad298722` had independent market identity/price corroboration but incomplete security fields, holders and supply/unlocks. Its observed pool age was approximately 598 hours: neither early token launch nor pre-listing status is proved. It is not a WATCH or recommendation.

The previously rejected Base contract `0x29cc30f9d113b356ce408667aa6433589cecbdca` was confirmed by exact contract as Gate normal Spot pair `ELSA_USDT`. Its prior adverse evidence was retained; the candidate remained REJECTED and its entry plan BLOCKED. Exchange tradability did not clear security.

The public catalog returned 5675 currency records, 2181 Spot-pair records, 2180 normal tradable pairs and 3425 supported-chain exact contract keys. This is one inventory snapshot, not a count of new listings. Optional `--previous` compares snapshots and labels differences newly observed, without fabricating listing times.

The separately labelled Ethereum USDC reference matched `USDC_USDT`, with fresh 20-level two-sided depth and closed five-minute candles. Its public pair fee was 0.1%; personal fees remained UNKNOWN. The saved book supported the diagnostic 100-USDT notional on both sides. Its support-derived conditional limit reference is retrospective technical integration evidence only, never a stablecoin opportunity, trade approval or current quote.

## Validation, alerts and deployment status

**203 tests pass locally**, retaining every prior test. Compilation, actionlint and diff checks pass. New tests cover cross-chain/ticker spoofing, Solana case, duplicate observations, missing data, Gate outages, metadata disagreement, native/wrapped identity, stale/crossed/unsorted/nonfinite books, partial depth, closed-candle integrity, strict BUY rejection and denied private/write endpoints. Prior unfinished alert tests cover scoring, known failures, staleness, deduplication, cooldowns, state transitions, multipart delivery recovery and formatting.

The existing registered `oracle-z-tests.yml` workflow has an opt-in `global_research=true` mode with read-only repository permissions, no credentials or Telegram secrets, no state commit step, and uploads raw compressed evidence plus unsent concise alert previews. The existing scanner watch path is preserved; no production scheduler was upgraded or activated. GitHub rejected direct dispatch of a newly added unregistered workflow, so the opt-in mode uses the already registered test workflow on the draft branch. GitHub Actions results for the final commit are recorded on PR #4 after push.

Alerts in [the example preview file](global-alert-previews-2026-10-22.txt) use real historical observations and are explicitly labelled unsent/expired examples. No Telegram message was sent in this increment; earlier personally confirmed delivery/preflight evidence is historical, not a claim of a new deployment.

```sh
python -m unittest discover -s tests -v
python global_discovery.py --limit 8 --output work/global-report.json.gz
# Optional inventory comparison; no production state is changed:
python global_discovery.py --limit 8 --previous validation/global-discovery-2026-10-22.json.gz --output work/global-next.json.gz
```

Full raw data, source URLs, observation/provider timestamps, preserved exclusion provenance and request ledgers: [compressed report](global-discovery-2026-10-22.json.gz).

## Documented sources

- https://www.gate.com/docs/developers/apiv4/en/spot/
- https://www.gate.com/docs/developers/apiv4/en/wallet/
- https://docs.dexscreener.com/api/reference
- https://apiguide.geckoterminal.com/ (redirects to CoinGecko on-chain documentation)
- https://namespaces.chainagnostic.org/solana/caip2
- https://namespaces.chainagnostic.org/solana/caip10

## Genuine remaining blockers

Independent beneficial ownership and complete supply/vesting/bridge/LP withdrawal/permission audits remain unavailable or incomplete for assessed candidates. Solana-specific mint/freeze/Token-2022 controls and developer history are not verified by this increment. Historical performance calibration, genuine adoption and wash-trading reconstruction require additional evidence and prospective labelled outcomes. Personal exchange fees/eligibility and manual risk inputs are absent. Public books cannot prove future fills or remove those blockers. Historical FAIL/CONFLICTING security or supply evidence is retained even when an older assessment was WAIT; a fresh missing field cannot erase it. No known security-critical implementation issue was left unresolved; adverse candidate evidence remains excluded.

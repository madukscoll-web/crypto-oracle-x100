# Production reporting and research repair

## Observed production evidence

- Scanner run 41323850833 (2026-11-01): 320 returned pool observations, 58 discovery candidates, six independent assessments, zero DEX candidate alerts. Selected risk triage: one WAIT, three high concern, two limited research. Repeated GeckoTerminal HTTP 429s. These are bounded discovery observations, not market-wide coverage or unique-token rejection totals.
- Latest completed scanner run 41346759926: 317 observations, 55 candidates, six assessed, zero alerts. Five WAIT and one high concern. Evidence included unsupported Solana execution/liquidity/sellability adapters, incomplete contract/holder/unlock evidence, and unavailable funding/quote configuration. Save-state and diagnostic artifact upload steps succeeded.
- Independent delivery check 41345134954 / job 124963237070 recorded an actual Bot API message-ID confirmation at 20:06:48 UTC. Mocked delivery confirmations in the unit-test portion of scanner logs were excluded from this finding.
- The hourly workflow intentionally lacked successful-scan notifications. Its existing policy regression explicitly prohibited routine success summaries. Therefore silent successful runs with no eligible candidates were expected; candidate silence alone did not establish broken Telegram connectivity.

## Implemented behavior

Each successful hourly workflow sends one aggregate operational summary after state publication. Discarded/incomplete token details remain in artifacts, never individual Telegram messages. Failed scans still use the failure notification. The summary checks the originating workflow run ID and retains a confirmation artifact only after the Bot API confirms a message ID. Ambiguous transport retries can duplicate messages; exactly-once Telegram delivery is not claimed.

Discovery uses shared rejection rules and records one terminal result per returned pool observation, including malformed data, missing measurements, age, liquidity/activity thresholds and duplicate qualified pools. Candidate statistics separately report unique qualified pools, known delivered pools, deduplicated research identities, selected/revisited assessments, overlapping evidence blockers and mutually exclusive notification outcomes. Deferred candidates are not called safety rejections. Security concerns and missing evidence remain separate.

Independent collection reserves time for security, quotes, current supply, pool/holder RPC checks and runtime-matched source inspection. The hourly collector no longer spends time on five-minute entry candles, which never authorize BUY. Holder failure retains separately collected pinned-pool evidence. Exact-contract CoinGecko supply comparisons now support all seven configured EVM networks. Source matches, provider screening, wallet balances, simulations, public routes and exchange books remain narrowly scoped observations; none substitutes for audited controls, beneficial ownership, complete vesting or funded executable sell evidence.

The existing issue-49 reversal research engine and 18 tests were imported from `feature/issue-49-altcoin-reversal-research`. A bounded hourly runner evaluates LINK/USDT and ONDO/USDT daily exchange candles, retains exchange metadata/candles, technical findings and historical paper evaluation, and labels all outputs speculative research. Pair symbols do not establish exact chain/contract identity or investment quality. No Telegram candidate eligibility or order permission is granted. Numeric candle timestamps sort numerically.

## Validation and remaining limits

Local Python compilation and all 501 offline tests passed. Regressions cover missing discovery flow, malformed rows, overlapping blocker accounting, aggregate-only summaries, provider budget restoration, partial RPC evidence retention and research outages.

The managed execution environment's configured HTTP proxy refused connections. Git fetch, live adapter requests and transfer of the diagnostic ZIP into this environment were unavailable. GitHub connector access works: production jobs/logs and artifact metadata were inspected; the connector returned a downloadable ZIP reference, but its contents could not be read locally. No claim of examining its JSON contents is made. Remote CI and post-merge production evidence must establish live behavior.

Unresolved evidence remains fail-closed: full contract controls, beneficial-owner attribution, complete circulating supply/vesting, Solana pool/sell adapters, and funded order-specific execution. Existing GitHub secrets are preserved; no credentials are invented and no automatic trading is enabled.

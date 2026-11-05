# Technical research channel: production evidence, 5 November 2026

**Channel status: ENABLED, TESTED, DEPLOYED AND LIVE DELIVERY VERIFIED.**
This completes the separately authorized technical notification change, not the entire CRYPTO-ORACLE investment-admission project.

## Implemented and repaired
The previous reversal stage produced JSON artifacts but never invoked Telegram delivery. PR 67 adds a separate technical channel for a bounded established-market research scope, with prominent unverified-security/fundamentals disclosures, exact market/candle replay, retained adverse-evidence vetoes, active currency screening, fresh spread/depth checks, historical trigger/invalidation references, delivery limits and durable receipt state. It also prevents a steadily rising market from being mislabelled a reversal without a preceding decline.

PR 68 hardens the adverse veto: Boolean provider flags cannot escape as UNKNOWN simply because an older parser expects strings or integers. This can only withhold messages.

The user explicitly approved this notification policy after its implications were explained. No asset or purchase approval was recorded. LINK and AKE remain excluded; unverified early-stage DEX notifications remain silent.

## Tests and source
- Local compilation and all **547 unit tests passed**, with no skips or failures.
- Workflow YAML parsing and whitespace checks passed.
- [PR 67](https://github.com/madukscoll-web/crypto-oracle-x100/pull/67): merge source `f9a0fdc5cf3f2638d7ec417304427154638a254f`.
- [PR 68](https://github.com/madukscoll-web/crypto-oracle-x100/pull/68): latest verified application source `3ef4c8f0910c0441b17d57404f4a909374fd4d54`.
- [Latest feature CI](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41971976719): success, logs confirm 547 tests.
- Latest production also ran 547 tests successfully before collecting real market data.

Regression cases include genuine decline/recovery, steady-uptrend false positives, unknown early assets, retained exact-asset negatives, string and Boolean honeypot findings, thin/stale/crossed/wide books, stale reports, missing provenance, forged approval flags, daily/material-change deduplication, unconfirmed receipts and failed receipt-state persistence.

## Actual production outcome

| Run | Application source | Confirmed technical messages | Failures |
| --- | --- | --- | --- |
| [41971408306](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41971408306) | f9a0fdc | AVAX_USDT and BNB_USDT | 0 |
| [41972074508](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41972074508) | 3ef4c8f | NEAR_USDT | 0 |

These were real technical WATCH messages accepted by Telegram's Bot API in the live reversal stage, not unit-test confirmations:
- AVAX: 05:10:35 UTC / 06:10:35 Lagos.
- BNB: 05:10:36 UTC / 06:10:36 Lagos.
- NEAR: 05:19:50 UTC / 06:19:50 Lagos.

Both workflows completed successfully. Latest research enumerated 2,188 Gate catalog records and 1,534 active altcoin pairs. There were 83 turnover-eligible markets overall, 16 within the restricted research scope, six selected pairs and 12 successful daily/weekly assessments. Five technical observations were assessed for delivery; only one remaining daily notification slot was available in the latest run. Suppression after the third daily message was intentional.

Persisted `technical_watch_state.json` contains the three confirmed per-asset receipts and `daily_counts["2026-11-05"] = 3`. Latest state publication commit is `cc28a26b613ff56403130799165a81f646384d24`. State refresh carried first-run receipts into the second run, demonstrating cross-run limits rather than merely process-local counters.

Both diagnostic ZIPs were downloaded and their SHA-256 values checked against GitHub. Reconstructed message formatting from retained screen/candle data confirmed the prominent required disclosures:
- First artifact 13389694656: `65d085e5e4c67fbdd36352dd10bb178bc43ba6493a227f96cb662a59c09aece8`.
- Latest artifact 13390951502: `30ecf9e92ebdab5bc24f6b5b031d2200be554de142e31cc2e210ff523cb7807c`.

Bot API acceptance is delivery-transport evidence, not proof that the user read a message or that any setup is profitable.

## Limits and remaining work
Messages are capped at two per run and three per Lagos calendar day. An unchanged setup is not repeated merely because another candle closes. Later notifications require at least 24 hours and a material change.

The setups remain unvalidated research hypotheses. Security, authority, sellability, holders, supply/unlocks, fees and funded execution are not fully verified. An exchange market/book observation is not an independently verified on-chain token identity or audit. No BUY gate, human approval requirement, order permission, token-review registry or trading function was relaxed.

The six-candidate DEX enrichment bottleneck, full independent evidence collection, quote configuration, qualified investment admission and strategy validation remain separate unfinished work. No paid service, order, private key or fabricated BUY was introduced.

## User action and rollback
No further configuration is needed for the authorized technical channel. Receiving these messages does not approve a purchase.

The existing hourly GitHub workflow will continue research under this policy; no unattended engineering is claimed. To stop technical alerts, set `enabled` to false in `technical_watch_policy.json`. Revert source through a reviewed PR if necessary, preserving notification state, signal history and the forward ledger. Full policy and operational limits: [TECHNICAL_RESEARCH_CHANNEL.md](TECHNICAL_RESEARCH_CHANNEL.md).

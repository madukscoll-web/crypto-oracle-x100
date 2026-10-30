# Multi-launchpad discovery and origin attribution specification

Scope: Pump.fun, Bags.fm, BONK.fun, Four.meme. This specification does not imply that any provider integration is live.

## Discovery adapters
- Pump.fun: Solana
- Bags.fm: Solana
- BONK.fun: Solana
- Four.meme: BNB Chain

Each adapter must use documented, permitted and verifiable provider or chain data. Never fabricate a token or fall back to ticker matching.

## Mandatory token provenance
Every candidate must include `origin_launchpad`, `origin_chain`, `token_contract`, `launch_transaction`, `origin_evidence_url`, `origin_verified_at`, `discovered_via` and `current_trading_venue`. Origin launchpad and discovery source are distinct. Verify launch origin using factory/program transaction evidence, not merely the website where a token was seen. If attribution cannot be established, mark UNKNOWN and do not issue a BUY candidate.

Use canonical chain + contract/mint as the deduplication key; retain multiple discovery sightings and original origin. Never classify a DEX pool, exchange listing or aggregator as the launchpad without proof.

## Alert format
TOKEN / SYMBOL
ORIGIN: <verified launchpad or UNKNOWN>
CHAIN: <chain>
CONTRACT: <exact address>
DISCOVERED VIA: <source>
TRADING VENUE: <venue>
ORIGIN PROOF: <transaction URL>
CHECKS: liquidity, holders, security, supply, execution and source freshness
DECISION: WATCH / MANUAL REVIEW / REJECT

Never send REJECT/DISCARD tokens in ordinary Telegram candidate alerts; preserve diagnostics for auditing. UNKNOWN provenance or missing essential evidence must fail closed.

## Implementation acceptance tests
1. One verified launch from each of four sources shows correct origin and chain.
2. Same token discovered on two sources deduplicates without overwriting original launchpad.
3. Symbol collision across different contracts remains separate.
4. Unknown or conflicting launch origin cannot generate BUY candidate.
5. Missing/failed provider endpoints cannot generate BUY candidate.
6. Telegram alerts include launchpad origin and distinguish current venue.
7. Existing hourly workflow, safety thresholds and read-only behavior remain unchanged.
8. No live trading or order placement.

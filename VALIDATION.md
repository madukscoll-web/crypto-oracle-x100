# Validation — 21 October 2026

This revision is an expanded, fail-closed research engine. It is **not yet a fully operational independently verified BUY engine**. `evidence_audit.audit().trade_ready` intentionally remains false. No BUY NOW signal was issued. No trading, signing or broadcasting functionality is included.

## Reproduced failures

Baseline: 57 tests, 51 passed, six failed. Two failure messages were hidden by a generic early return; diagnostics now retain the provider reason and explain that limited checks are not a contract audit. Missing-security diagnostics now describe unclassified LP concentration metadata without presenting it as a contract flaw. Three outdated expectations were corrected: caller-set verification booleans cannot authorize BUY, the default allocation remains 10% with a 1% risk budget, and prices cannot manufacture 10% stops or arbitrary take profits. These are deliberate safety corrections, not claims that the old behavior was implemented.

Local final validation: 70 unittest tests passed; compileall passed; git diff --check passed; actionlint 1.7.12 passed for both workflows. YAML parsed successfully. Tests use offline fixtures; they are not live execution evidence. CI runs on all pushes and pull requests. Scanner runs also upload raw verification evidence as an artifact.

## Implemented

* Read-only GoPlus contract capability, holder, liquidity and supply diagnostics, including explicit proxy/mint/pausing/slippage authority concerns.
* Independent Honeypot.is buy/sell simulation, exact returned-token matching, explicit success and tax validation. A simulation is labelled LIMITED, never a size-specific executable sell.
* GeckoTerminal closed five-minute candle analysis: continuity, freshness, valid OHLC geometry, observed resistance break and relative volume. No price predictions.
* Optional 0x v2 two-way unsigned quotes with exact pair/amount binding, minimum output, gas and simulation checks. Quoted routes remain LIMITED until execution prerequisites and gas valuation are verified. No API key is persisted in evidence.
* Risk sizing from explicit USD equity, historical invalidation, fees, slippage and depth. Includes full-allocation loss exposure. It is a tested calculation utility; it does not authorize an order.
* Independent adverse evidence vetoes decisions. Missing/partial evidence stays UNKNOWN. Raw observations and reasons are saved in `verification_report.json` for CI artifact upload.
* Existing paper performance tracking remains indicative, not an execution backtest. Existing tests cover identity changes, duplicate prices, missing and late outcomes. No historical performance has been invented.
* Telegram confirmation and missing-credential tests; decision and reason are placed before verbose diagnostics so truncation cannot hide them. Delivery errors exclude exception text that might contain a bot URL.

## Actual live checks

Network-enabled execution was required; initial sandbox-only attempts failed. GitHub authentication and remote access succeeded on retry. Real responses were collected for Ethereum USDC (`0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48`) and the reference pool `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640` at approximately 19:52 UTC. This token was a reference integration check, not a BUY candidate.

GoPlus returned a matching token result with `is_proxy=1`, which fails the strict capability policy. Its holder list accounted for approximately 26.7% of supply; classification/coverage remained UNKNOWN. Total supply was returned, but circulating supply and future unlocks were not verified. Honeypot.is returned simulationSuccess=true and isHoneypot=false; this was labelled LIMITED. GeckoTerminal returned candle data; the entry rule returned WAIT. The engine did not produce a BUY. Raw responses are committed in `validation/reference-live-evidence-2026-10-21.json`, not interpreted as enduring current market facts.

GeckoTerminal API guide was accessible. The referenced GoPlus, Honeypot and 0x documentation URLs returned HTTP errors from this runtime; documentation content could not be independently reviewed in this session. Consequently the new adapters must not be described as fully validated against live documentation. The 0x executable quote API was not called: configuration is absent.

GitHub Actions independently passed all 70 tests for commit `c27c713`: https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/39665542204 (push) and https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/39665552557 (pull request). These are CI results, not production deployment evidence.

## Genuine remaining integration blocks

* No 0x key, public taker, funding token or explicit base-unit order size is configured. Add `ZEROX_API_KEY` as a repository secret and `ORACLE_TAKER_ADDRESS`, `ORACLE_FUNDING_TOKEN`, `ORACLE_ORDER_BASE_UNITS` as repository variables. A public address is sufficient; never supply a wallet private key. Funding, allowance, post-buy sell simulation, route/pool identity, quote TTL and gas valuation still require verification.
* LP ownership/lock contract validity/expiry, beneficial holder ownership and related wallets, circulating supply and complete vesting/unlock schedules are not independently integrated. GoPlus metadata cannot establish those facts. No generic cross-chain unlock source was invented.
* Independent simulator coverage is currently Ethereum, BSC and Base. Other discovery networks remain UNKNOWN for this module.
* `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are not configured in this environment. Delivery was tested with mocks only; no real Telegram message was sent.
* No full scheduled scan or production deployment was claimed. Scheduled Actions must execute in GitHub with configured integrations. Branch-protection inspection returned HTTP 403, so use a reviewable feature branch and pull request rather than assuming permission to bypass rules.

The required time-limited BUY NOW — VERIFIED SETUP formatter and issuance path remain disabled because the mandatory verification sources above are incomplete. Enabling them before resolving those sources would turn unknown evidence into an invented verified signal.

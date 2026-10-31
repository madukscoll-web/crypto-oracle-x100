# crypto-oracle-x100
AI-assisted early detection and risk screening of newly launched cryptocurrency tokens.

## Evidence upgrade (draft)

Run offline checks with:

```sh
python -m compileall -q *.py tests
python -m unittest discover -s tests -v
```

The hourly scanner remains research-only. Missing security, tokenomics, holders,
LP controls, adoption and execution evidence is **UNVERIFIED**. No caller boolean,
activity score or consistent offline record can authorize BUY.

Optional `ORACLE_EVIDENCE_FILE` selects a local JSON evidence file, limited to 2 MB:

```json
{"schema_version":1,"tokens":[{"network":"base","contract":"EXACT_TOKEN_ADDRESS","pool":"EXACT_POOL_ADDRESS","records":{}}]}
```

`records` supports `supply` and `unlocks` lists, plus `holders`, `security` and
`execution` objects. Each observation needs `provider`, `origin` (the original
source family, not a mirror), HTTPS `source_url`, `network`, `contract` and
`observed_at` with timezone. Quote records also need `pool`. Nothing in this file
is fetched or trusted as authenticated. Exact schemas and synthetic examples are
in `tests/test_evidence_checks.py`; the validation and limitations report is
[ISSUE_6_VALIDATION.md](ISSUE_6_VALIDATION.md).

Thresholds: `ORACLE_SUPPLY_CONFLICT_PERCENT` (1),
`ORACLE_VOLUME_LIQUIDITY_WARNING` (10), `ORACLE_DILUTION_WARNING` (5),
`ORACLE_TOP10_WARNING` (0.5), `ORACLE_UNLOCK_WARNING_DAYS` (30),
`ORACLE_UNLOCK_FRACTION_WARNING` (0.1), `ORACLE_QUOTE_MAX_AGE_SECONDS` (120),
`ORACLE_SPREAD_WARNING_PERCENT` (1), `ORACLE_MIN_DEPTH_USD` (1000), and
`ORACLE_SLIPPAGE_WARNING_PERCENT` (2). Invalid thresholds fall back to defaults.
Supply and other general records currently have a 24-hour freshness limit.

Supply records contain `values` with circulating/total/max supply, market cap USD
and FDV USD. Unlock records contain `coverage_start`, `coverage_end`, and `events`
with `at` and token `amount`. Holder records contain `complete`, `total_supply`
and `holders` with address/balance; an optional exclusion needs kind LP/CEX/BURN,
exact holder identity, and its own provenance. Quotes require quote token, ID,
block, kind EXECUTABLE, expiry, bid/ask, order/depth USD, both-direction amounts,
fees USD and slippage percent. These requirements validate observations; provider
authenticity, RPC simulation and independent audits remain separate requirements.


## Hourly live evidence integration

The production scanner now runs a bounded read-only enrichment stage after basic
market screening. A shared budget permits at most three candidates, 90 requests
and 60 seconds, with five-second request timeouts. Unsupported networks, missing
configuration, API denial and candidates beyond the budget remain explicit.
The hourly schedule and Telegram credentials are unchanged.

The stage reuses exact-pool Honeypot/GoPlus checks, pinned on-chain pool/holder
observations, supply comparison, registry unlock disclosures and configured
0x/Kyber quote adapters. Gate public Spot metadata and books are matched by exact
network/contract, never symbol alone. Gate snapshots are separate from DEX
execution and do not prove future fills, LP safety or beneficial ownership.
No quote credential, taker address or funding/order size is invented; missing
configuration is reported. Complete verification and automatic trading remain
disabled. This stage does not perform an independent contract audit.

Telegram shows identity first and per-check findings. Full blocker reasons, raw
provider observations, timestamps and Gate evidence are preserved in
`evidence_report.json` under the workflow's diagnostics artifact; shared budget
and provider failures are in `scan_summary.json`. A successful workflow means
collection completed, not that any candidate is safe or ready to trade.

## Gate Spot paper BUY candidates

The hourly scanner also runs the independent strategy in
`gate_spot_candidates.py`. See [GATE_CANDIDATE_STRATEGY.md](GATE_CANDIDATE_STRATEGY.md)
for exact admission rules, paper sizing, source-review requirements, cost
assumptions, expiry, delivery deduplication and forward-observation limitations.
The qualifying label is **BUY CANDIDATE — MANUAL REVIEW**, never VERIFIED BUY.

The default `gate_token_reviews.json` has no approved records. This is explicitly
reported; fixture success is not a live opportunity. Actual source-backed token
reviews and live endpoint validation are required before live candidate delivery.
Run `python gate_spot_candidates.py` for a no-notification diagnostic report.

Gate catalog-first research and recorded live results are documented in [GATE_SPOT_DISCOVERY.md](GATE_SPOT_DISCOVERY.md). Research queues do not grant token approval.

## Eight-network read-only discovery and signal retention

`multichain_live_research.py` now requests Solana, Ethereum, BNB Chain, Base,
Arbitrum, Polygon POS, Avalanche C-Chain and Optimism. Exact CAIP chain IDs and
GeckoTerminal/DEX Screener network identifiers remain distinct. Expanded discovery
does not activate security or BUY authorization. Provider responses and invalid-row
ledgers are retained in `provider_observations`; failures and chain counts are
reported separately. Empty or throttled feeds do not prove market coverage.
GeckoTerminal requests use a conservative 6.1-second interval within a 180-second
run budget; shared provider limits may still cause explicit coverage gaps.

Paper signals retain their first entry and all accepted samples. Backdated entries,
Solana case changes and boolean prices are rejected. Capacity prevents admission
instead of deleting prior signals or changing return baselines. The scanner's
`scan_summary.json` exposes tracking capacity, 24h/7d/30d/90d/365d outcomes and
sampled MFE/MAE/drawdown. These are indicative sampled-price statistics, without
intrahour extremes, execution costs or liquidity adjustments. Already-lost legacy
samples cannot be reconstructed by this repair. No predictive validation is implied.

## Completion policy and reproducible limits

See [COMPLETION_MATRIX.md](COMPLETION_MATRIX.md) for current evidence and explicit
external blockers. The hourly discovery audit now stores `research_discovery_state.json`
for durable feed/candidate rotation, and runs at most three isolated provider
workers. `--include-launchpads` adds the documented Pump RPC and Raydium LetsBONK
sources; provenance remains narrower than a security audit. Failed/partial feeds
are reported in provider health and retained observations.

Scanner and discovery diagnostics include the five-outcome canonical policy.
Critical gaps retain RESEARCH WATCH/INSUFFICIENT EVIDENCE; existing BUY authorization
is unchanged. `forward_events.jsonl` is an append-only hash-linked observation and
model ledger; legacy records are explicitly imports with unknown model lineage.
It does not invent liquidity-adjusted returns or mature forward outcomes.

`research_validation.py` provides fixed separate meme/utility heuristics and a
point-in-time, depth/cost-aware walk-forward/holdout protocol. The real cohort is
empty and reports BLOCKED. Passing synthetic protocol tests is not predictive
validation, calibration, a historical 100x finding or investment authorization.

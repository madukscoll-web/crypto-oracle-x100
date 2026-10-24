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

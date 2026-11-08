# Historical cohort ingestion

`historical_ingestion.py` imports supplied archives reproducibly. It does not fetch current charts to reconstruct historical executable prices, authenticate source organizations or mark performance validated.

Run:

```bash
python historical_ingestion.py --manifest path/to/manifest.json --output path/to/ingested_cohort.json --report path/to/ingestion_report.json
python research_validation.py --dataset path/to/ingested_cohort.json --output path/to/validation_report.json
```

The second command remains a separate explicit offline evaluation. The ingestion command does not replace `historical_cohort.json` unless explicitly given that output path. Invalid ingestion exits with status 2, reports the rejection and preserves the previous output dataset.

## Manifest requirements

Use schema version 1 with these fields:

| Field | Required contents |
| --- | --- |
| `cohort_id` | Nonempty exact cohort identifier shared by every record |
| `selection_basis` | `LAUNCH_COHORT_BEFORE_OUTCOMES` |
| `selected_at` | Timezone-aware selection time, no later than any entry feature timestamp |
| `universe.asset_keys` | Complete distinct pre-outcome asset inventory, exactly matching imported records |
| `universe.failed_asset_keys` | Nonempty distinct failed controls included in that inventory and the records |
| `universe.source_url`, `origin` | HTTPS source location and identified origin of the census |
| `universe.observed_at`, `available_at` | Timezone-aware census timestamps, ordered before selection |
| `sources` | Nonempty array of archive descriptors |
| Each source | Relative `path` inside manifest directory, exact raw-file `sha256`, HTTPS `source_url`, `origin`, and timezone-aware `captured_at` |

Each source archive is a JSON object containing a nonempty `records` array in the existing `research_validation.py` schema. Records retain exact chain/contract identity, provenance for each feature and execution leg, observed/available feature timestamps, label availability, contemporaneous executable entry/exit price and depth, position size, fees and slippage. The archive capture must occur after its outcome labels were available. Paths must not escape the manifest directory. Source archives and the manifest cannot be overwritten by dataset or report outputs.

The complete census prevents silently dropping failed assets. A declared failed control must have a below-one cost-adjusted executable outcome. A failed or delisted token without a genuine executable exit snapshot remains a missing-data blocker; the command does not manufacture a zero price, assume liquidation or discard it. A full loss with unavailable exit evidence is therefore not admitted by the current execution-study protocol.

## Evidence limits

A manifest hash proves that the same bytes were used. It does not prove source authenticity, honest selection timing, independent reviewers or representative market coverage. Ingestion remains `INGESTED_NOT_EXTERNALLY_VERIFIED`; BUY authorization and order execution remain false. The existing evaluator separately requires at least 20 independent assets, winning and losing controls per represented stratum, purged walk-forward folds and an out-of-sample holdout. Neither command produces calibrated 100× probabilities.

No genuine historical records were supplied with this implementation. The production cohort remains empty until appropriate archives are obtained. The regression fixtures are explicitly synthetic protocol tests.

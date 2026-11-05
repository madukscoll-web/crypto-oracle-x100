# Authorized technical WATCH channel

The user authorized a separate research channel on 5 November 2026 after reviewing
the implications: incomplete security/fundamental evidence may be disclosed in a
technical WATCH, while every BUY retains its full evidence and final-human-approval
requirements. This authorization approves a notification policy, not any asset.

## Scope and safeguards

- `technical_watch_policy.json` enables this channel for a bounded list of named
  established exchange markets. Inclusion selects research scope; it does not
  certify legitimacy, fundamentals, native/wrapped identity or investment quality.
  LINK and AKE are excluded to preserve the user's deferred/rejected decisions.
- Enumerate real Gate Spot markets and turnover, then rotate six in-scope pairs.
  Require normal, active, non-delisting metadata; the existing stablecoin,
  leveraged, wrapped and pegged exclusions remain. Unknown early tokens never
  enter this channel solely because they have high trading activity.
- Analyze only sufficient, chronological, closed daily/weekly candles. A prior
  decline is now required: at least 8% peak/trough drawdown and a declining prior
  mean, followed by the existing higher-low/recovery criteria. A steady uptrend
  is no longer labelled a reversal. These thresholds are unvalidated heuristics,
  not calibrated probabilities or demonstrated trading performance.
- Recompute each setup from exact retained exchange metadata and candles at
  delivery. Reject stale/future reports, absent or mismatched provenance, weak
  relative volume and incoherent invalidation levels.
- Check active currency metadata, retain exact-contract historical adverse
  findings, and query GoPlus for supported EVM representations. A known adverse
  finding vetoes delivery. Missing provider or native-chain security review stays
  UNKNOWN and is prominently disclosed, never promoted to verified safety.
- Fetch the book after slow screening. Require a fresh ordered book, spread at
  most 50 bps, at least 1,000 USDT on each side within 1%, and displayed depth for
  a 100-USDT diagnostic calculation. That calculation is not a proposed purchase,
  authenticated fill or evidence of account funding. Reject breached invalidation
  or a live price more than 10% from the closed-candle reference.

## Notifications

Messages begin `TECHNICAL WATCH — NOT APPROVED FOR PURCHASE` and immediately state
`SECURITY / FUNDAMENTALS NOT FULLY VERIFIED. NOT A BUY SIGNAL.` They include exact
Gate market, timeframe, source URLs, UTC observation, historical trigger and
invalidation, relative volume, displayed depth/spread and unresolved checks.
USDT is not assumed equal to USD. No executable order, target-price forecast,
position size or guaranteed stop fill is claimed.

Maximum two messages per run and three per Lagos calendar day. An asset receives
only one timeframe per day. Later messages require at least 24 hours and a
breakout-classification upgrade or a 10% trigger/invalidation change; a new candle
or price change alone cannot create repeated alerts. Confirmed per-message receipts
are persisted atomically, then published by the serialized hourly state workflow.
Failed/ambiguous sends do not advance delivery state. Telegram's lack of idempotent
send IDs still permits a duplicate after a network ambiguity or process crash.

The daily health digest reports technical delivery separately from DEX research
and verified BUY counts. `technical_watch_delivery.json` and the retained reversal
report expose suppression reasons and provider coverage. An empty qualified batch
produces no individual notification. No synthetic current signal is manufactured.

## Admission separation and operation

This channel does not change `evidence_audit.py`, `investment_gates.py`, canonical
BUY classification, `validate_execution_evidence`, or `gate_token_reviews.json`.
Unverified early-stage DEX notifications remain suppressed. Missing quote settings,
reviewed fundamentals and strategy validation still block investment admission.
The six-candidate DEX enrichment bottleneck is a separate outstanding issue.

No new paid service, key, wallet signing, private account method or order submission
is introduced. The existing Telegram secrets are bound only for notification.
Disable `enabled` in the policy to stop this channel. Revert the change through a
reviewed PR to remove it; preserve technical notification state and the forward
ledger. Existing PR 58's incomplete formatter/delivery prototype was inspected;
its unguarded selection and per-candle deduplication were not deployed unchanged.

## Validation

Run compilation and the full offline suite, including `tests/test_technical_watch.py`.
Fixtures cover a real decline/recovery pattern, steady-uptrend false positives,
unknown early assets, exact-asset adverse history, adverse provider findings,
thin/stale/crossed/wide books, missing provenance, forged approval flags, stale
reports, daily limits, material-change deduplication and per-message receipt
failure. Fixture transport success is not a real Telegram receipt. Verify the
post-merge production run and diagnostics before claiming actual live delivery.

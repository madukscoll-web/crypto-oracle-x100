# Altcoin reversal module: operational readiness

**Status: research prototype; no validated trading edge, no live alerts, no order execution.**

## What is implemented
- Daily and weekly closed-candle technical WATCH detection with read-only Gate public API integration.
- Preliminary technical entry trigger and invalidation (not executable prices or position sizing).
- Rolling 10-candle forward paper evaluation using next-bar open, illustrative fees and slippage.
- Manual GitHub Actions workflow with downloadable JSON output. The workflow **fails** if any requested pair lacks verifiable public Spot data.
- Existing BUY approval and trading controls are unchanged.

## Evidence required before production use
1. Run the manual workflow on the feature branch after merge or through an authorized GitHub Actions dispatch; preserve run URL and the full JSON artifact. GitHub PR unit tests are not a live exchange validation.
2. Validate the actual Gate candlestick schema and daily/weekly timestamp semantics. Reject missing, stale, duplicated, partial or irregular candles; compare a sample to independent OHLCV.
3. Test on a pre-registered diversified altcoin universe across bullish, bearish and sideways regimes, with survivorship-bias-aware delisted history.
4. Use non-overlapping walk-forward folds and realistic order-book fees, spreads, slippage, stops and limit-order fill assumptions. Current rolling signals overlap and reported hit rate must not be treated as independent predictive probability.
5. Add an executable paper trade state machine: entry confirmation, stop, staged targets, expiry, cancellation and invalidation. Current entry trigger and prior low are **not** an approved order plan.
6. Verify fundamentals, unlocks, token identity and current liquidity before any human-review BUY classification.
7. Run alert deduplication and delivery tests with real Telegram delivery receipts; do not enable automatic trading.

## Manual operation
From a checked-out branch with Python 3.11:
```bash
python -m unittest discover -s tests -p 'test_altcoin_reversal_*.py' -v
python altcoin_reversal_cli.py --pairs LINK_USDT,ONDO_USDT --interval 1d
```
A RESEARCH_ONLY record confirms successful data retrieval, **not** a trade recommendation. An UNAVAILABLE record means the market evidence was not verified. No token purchase should follow solely from this report.

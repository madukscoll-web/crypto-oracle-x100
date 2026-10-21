# OMEGA engineering readiness (evidence-based)

This is a research-alert scanner, **not** a production-ready verified BUY engine.

## Implemented
- GeckoTerminal pool discovery and activity screening.
- GoPlus provider-flag checks for supported EVM chains (not an audit).
- Fail-closed BUY candidate checks; no automatic verification flags are populated.
- Telegram research alerts, rotating tracked-pool refresh, persistent state.
- Paper signal tracking for qualifying momentum/pullback observations.
- Unit tests and hourly GitHub Actions configuration.

## Not implemented / blocked
- Independent executable buy **and sell** simulation tied to exact chain,
  token, pool, input size, block height and authenticated quote provider.
- Independently established liquidity lock/withdrawal risk, wallet clustering,
  verified supply/unlocks and chain-specific Solana security coverage.
- Multi-candle technical analysis, support/invalidation and executable stop levels.
- Audited valuation and dilution-adjusted 10x/100x feasibility model.
- Representative out-of-sample backtest and live signal performance evidence.
- Verified live GitHub Actions success after the most recent changes.

## Release gate
Until all independent evidence adapters are integrated, validated and tested,
the system must not advertise VERIFIED BUY NOW. Provider-reported security
fields and market activity cannot substitute for independent execution tests.

## Operator verification
Check the Actions tab on main for a completed run of the latest commit.
Review the 'Validate scanner and signal rules' step and Telegram delivery.
No GitHub check status was available for the latest commit at documentation time.

Never paste wallet seed phrases, private keys or Telegram secrets into issues.

# CRYPTO-ORACLE Z — Gate Decision Intelligence (development)

## Implemented in this branch
- Read-only public Gate spot-market adapter (`gate_spot_research.py`).
- Active USDT spot-pair selection, 24-hour quote turnover screening, top-five bid/ask depth, spread, and abnormal price-change screening.
- Explicit `BUY WATCHLIST — RESEARCH ONLY` classification distinct from `BUY CANDIDATE`.
- Offline regression tests. No private Gate credentials required.

## Not yet implemented
- Independent token contract/holder/tokenomics security verification for Gate assets.
- Fresh authenticated executable order quote and fee-adjusted entry/exit risk model.
- GitHub Actions cross-run persistence for Gate alert state and live Telegram delivery testing. A read-only Telegram proposal renderer and local 24-hour alert deduplication are implemented, but sending is opt-in and not scheduled.
- Per-order Telegram approval bound to pair, side, amount, price ceiling and short expiry.
- Secure Gate API credentials, signed private requests, paper-trading mode, order reconciliation and idempotency.
- Daily loss cap, cumulative portfolio exposure tracking, emergency kill switch.
- Production rollout and real-money order execution.

## Strict security conditions before live orders
1. Spot only; withdrawals and futures permissions disabled.
2. No order without explicit per-order human approval.
3. Approval expires and cannot be replayed; order price/quantity limits are enforced server-side.
4. API secrets must not be placed in GitHub source, chat messages or Telegram.
5. Independent security and execution evidence must be checked; missing evidence is not `True`.
6. Paper-trade simulations, failure-injection tests and manual release approval precede production.
7. Gate-listed pairs do not require a DEX liquidity-lock check, but do require relevant market, custody and token risk checks.

## Running locally
`python -m unittest discover -s tests -v`

`python gate_spot_research.py` queries public Gate spot endpoints for a research report only. It never trades.

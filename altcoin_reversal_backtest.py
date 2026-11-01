"""Walk-forward, no-lookahead paper evaluation of technical reversal watches.

Research only. A signal is assessed at the last CLOSED candle of a rolling
window, then its subsequent returns and drawdown are measured separately.
"""
from __future__ import annotations

import math
from statistics import median
from altcoin_reversal_research import analyze


def walk_forward(symbol, candles, *, source, interval="1d",
                 horizon=10, fee_bps=10, slippage_bps=10):
    if not isinstance(candles, list) or len(candles) < 55 + horizon:
        raise ValueError("Insufficient history for forward evaluation")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise ValueError("Invalid horizon")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) and 0 <= v <= 1000
               for v in (fee_bps, slippage_bps)):
        raise ValueError("Invalid transaction cost assumptions")
    round_trip_cost = 2 * (fee_bps + slippage_bps) / 10000
    signals = []
    for end in range(55, len(candles) - horizon + 1):
        window = candles[end - 55:end]
        future = candles[end:end + horizon]
        report = analyze(symbol, window, source=source,
                         observed_at=str(window[-1].get("timestamp", "")),
                         interval=interval)
        if report["classification"] not in (
                "EARLY REVERSAL WATCH", "TECHNICAL REVERSAL WATCH"):
            continue
        # Outcome uses next candle OPEN as hypothetical entry, not signal close.
        entry = future[0].get("open")
        if not isinstance(entry, (int, float)) or isinstance(entry, bool) or not math.isfinite(entry) or entry <= 0:
            raise ValueError("Invalid next-bar entry price")
        prices = []
        for bar in future:
            if bar.get("closed") is not True:
                raise ValueError("Unclosed forward observation")
            close, low = bar.get("close"), bar.get("low")
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) or
                   not math.isfinite(v) or v <= 0 for v in (close, low)):
                raise ValueError("Invalid forward market observation")
            prices.append((close, low))
        exit_close = prices[-1][0]
        net_return = exit_close / entry - 1 - round_trip_cost
        worst_excursion = min(low / entry - 1 for _, low in prices)
        signals.append(dict(signal_at=window[-1]["timestamp"],
                            classification=report["classification"],
                            hypothetical_entry=entry, horizon_close=exit_close,
                            net_return=net_return, worst_excursion=worst_excursion,
                            horizon=horizon))
    returns = [s["net_return"] for s in signals]
    return dict(symbol=symbol, source=source, interval=interval,
                horizon=horizon, fee_bps=fee_bps, slippage_bps=slippage_bps,
                evaluated_windows=len(candles) - 54 - horizon,
                signals=len(signals),
                hit_rate=(sum(r > 0 for r in returns) / len(returns) if returns else None),
                median_net_return=(median(returns) if returns else None),
                worst_excursion=(min(s["worst_excursion"] for s in signals)
                                 if signals else None),
                observations=signals, buy_authorized=False,
                warning="Overlapping signals are correlated; historical paper outcomes are not predictive probabilities")

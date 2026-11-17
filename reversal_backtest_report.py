"""Read-only, fee-adjusted walk-forward report for the Gate reversal rule.

Runs the existing no-lookahead evaluation (`altcoin_reversal_backtest.walk_forward`) on
public Gate Spot candles for a fixed pair list and prints `BACKTEST` lines. For each
interval it compares reversal signals with a baseline of entering at EVERY window, so a
falling market cannot make a rule look broken or a rising one make it look good. Signals
closer than one horizon on the same pair overlap and are counted once. Fewer than 30
independent signals is reported as INSUFFICIENT SAMPLE. No Telegram, keys or orders.

Usage: python reversal_backtest_report.py [--pairs A_USDT,B_USDT] [--intervals 1h,4h]
"""
import argparse
import json
import math
from statistics import median

import altcoin_reversal_cli as cli
from altcoin_reversal_gate import INTERVAL_SECONDS

PAIRS = ('TAO_USDT', 'AVAX_USDT', 'LINK_USDT', 'ONDO_USDT', 'NEAR_USDT',
         'INJ_USDT', 'SUI_USDT', 'APT_USDT', 'ATOM_USDT', 'DOT_USDT')
MIN_INDEPENDENT = 30
HORIZON = 10
WARMUP = 55


def baseline_returns(candles, horizon=HORIZON, cost=0.004):
    """Net return of entering at the next open at every window the rule could be asked about."""
    returns = []
    for end in range(WARMUP, len(candles) - horizon + 1):
        entry = candles[end]['open']
        exit_close = candles[end + horizon - 1]['close']
        if entry > 0 and math.isfinite(entry) and math.isfinite(exit_close):
            returns.append(exit_close / entry - 1 - cost)
    return returns


def independent(signals, period, horizon=HORIZON):
    """Keep a signal only if it starts at least one horizon after the previous kept one."""
    kept, last = [], None
    for signal in sorted(signals, key=lambda s: s['signal_at']):
        if last is None or signal['signal_at'] - last >= horizon * period:
            kept.append(signal)
            last = signal['signal_at']
    return kept


def stats(returns):
    if not returns:
        return dict(n=0, hit_rate=None, median_net=None)
    return dict(n=len(returns), hit_rate=round(sum(r > 0 for r in returns) / len(returns), 4),
                median_net=round(median(returns), 5))


def summarise(result, interval):
    period = INTERVAL_SECONDS[interval]
    pairs, all_signals, all_base, skipped = [], [], [], []
    for row in result['results']:
        if row.get('status') != 'RESEARCH_ONLY':
            skipped.append(dict(pair=row.get('pair'), reason=row.get('reason', 'unavailable')))
            continue
        kept = independent(row['backtest'].get('observations', []), period)
        base = baseline_returns(row['candles'])
        returns = [s['net_return'] for s in kept]
        pairs.append(dict(pair=row['pair'], candles=row['candle_count'], independent_signals=len(kept),
                          signal=stats(returns), baseline=stats(base)))
        all_signals += returns
        all_base += base
    sample = len(all_signals)
    if sample < MIN_INDEPENDENT:
        verdict = f'INSUFFICIENT SAMPLE: {sample} independent signals (need {MIN_INDEPENDENT}); no conclusion'
    else:
        edge = median(all_signals) - median(all_base)
        verdict = ('MEASURED: signal median net ' + format(median(all_signals), '.3%') + ' vs baseline ' +
                   format(median(all_base), '.3%') + ' (difference ' + format(edge, '+.3%') +
                   '); historical, correlated across pairs, not a forecast')
    return dict(interval=interval, horizon_bars=HORIZON, round_trip_cost='0.4% (10 bps fee + 10 bps slippage each side, assumed)',
                pooled_signal=stats(all_signals), pooled_baseline=stats(all_base), pairs=pairs, skipped=skipped,
                verdict=verdict, buy_authorized=False, orders_allowed=False)


def report(pairs=PAIRS, intervals=('1h', '4h'), *, fetch=cli.fetch_public, now=None):
    return [summarise(cli.run(list(pairs), interval, fetch=fetch, now=now, keep_observations=True), interval)
            for interval in intervals]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', default=','.join(PAIRS))
    parser.add_argument('--intervals', default='1h,4h')
    args = parser.parse_args(argv)
    intervals = tuple(x.strip() for x in args.intervals.split(',') if x.strip())
    if any(x not in INTERVAL_SECONDS for x in intervals):
        parser.error('Unsupported interval')
    for item in report(tuple(p.strip() for p in args.pairs.split(',') if p.strip()), intervals):
        print('BACKTEST', json.dumps(item, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()

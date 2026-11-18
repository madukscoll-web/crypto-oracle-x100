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
import datetime as dt
import json
import math
from statistics import median

import altcoin_reversal_cli as cli
from altcoin_reversal_gate import GATE_INTERVAL, INTERVAL_SECONDS, gate_candles
from gate_spot_research import PublicGate

PAIRS = ('TAO_USDT', 'AVAX_USDT', 'LINK_USDT', 'ONDO_USDT', 'NEAR_USDT',
         'INJ_USDT', 'SUI_USDT', 'APT_USDT', 'ATOM_USDT', 'DOT_USDT')
MIN_INDEPENDENT = 30
HORIZON = 10
WARMUP = 55
Z95 = 1.96
# Market regime, fixed in advance and never tuned: BTC_USDT return over the last LOOKBACK closed bars.
REFERENCE = 'BTC_USDT'
LOOKBACK = 24
REGIME_THRESHOLD = 0.03
REGIMES = ('FALLING', 'SIDEWAYS', 'RISING')


def baseline_returns(candles, horizon=HORIZON, cost=0.004):
    """Net return of entering at the next open at every window the rule could be asked about."""
    returns = []
    for end in range(WARMUP, len(candles) - horizon + 1):
        entry = candles[end]['open']
        exit_close = candles[end + horizon - 1]['close']
        if entry > 0 and math.isfinite(entry) and math.isfinite(exit_close):
            returns.append(exit_close / entry - 1 - cost)
    return returns


def baseline_points(candles, horizon=HORIZON, cost=0.004):
    """(window end time, net return) for every window; the time matches a signal's signal_at."""
    points = []
    for end in range(WARMUP, len(candles) - horizon + 1):
        entry = candles[end]['open']
        exit_close = candles[end + horizon - 1]['close']
        if entry > 0 and math.isfinite(entry) and math.isfinite(exit_close):
            points.append((candles[end - 1]['timestamp'], exit_close / entry - 1 - cost))
    return points


def regime_map(reference):
    """{candle time: FALLING|SIDEWAYS|RISING} from the reference closes, using only closed bars up to that time."""
    labels = {}
    for i in range(LOOKBACK, len(reference)):
        before = reference[i - LOOKBACK]['close']
        if before > 0 and math.isfinite(reference[i]['close']):
            change = reference[i]['close'] / before - 1
            labels[reference[i]['timestamp']] = ('FALLING' if change <= -REGIME_THRESHOLD else
                                                 'RISING' if change >= REGIME_THRESHOLD else 'SIDEWAYS')
    return labels


def market_reference(interval, fetch, now):
    gate = PublicGate(fetch)
    raw = gate.get('/spot/candlesticks', dict(currency_pair=REFERENCE, interval=GATE_INTERVAL[interval], limit=1000))
    return gate_candles(raw, interval_seconds=INTERVAL_SECONDS[interval], now=now)


def _mean_var(values):
    n = len(values)
    mean = sum(values) / n
    return mean, (sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0)


def slice_verdict(signal_returns, baseline_returns_, variants):
    """Signal mean vs baseline mean. Baseline windows overlap by one horizon, so its effective n is n/horizon.
    The bar rises with the number of variants tested (same correction style as pattern_lab)."""
    n = len(signal_returns)
    if n < MIN_INDEPENDENT:
        return f'INSUFFICIENT SAMPLE: {n} independent signals (need {MIN_INDEPENDENT}); no conclusion', None
    effective = len(baseline_returns_) / HORIZON
    if effective < 2:
        return 'INSUFFICIENT BASELINE: too few comparison windows; no conclusion', None
    mean_s, var_s = _mean_var(signal_returns)
    mean_b, var_b = _mean_var(baseline_returns_)
    error = math.sqrt(var_s / n + var_b / effective)
    if error < 1e-12:  # floating-point dust counts as no variation
        return 'INSUFFICIENT SAMPLE: no variation in returns; no conclusion', None
    z = (mean_s - mean_b) / error
    bar = Z95 + 0.5 * math.log(max(variants, 1))
    if z >= bar:
        label = f'EDGE vs baseline after correcting for {variants} variants (z={z:.2f} >= {bar:.2f})'
    elif z <= -bar:
        label = f'WORSE than baseline after correcting for {variants} variants (z={z:.2f} <= -{bar:.2f})'
    else:
        label = f'NO MEASURABLE EDGE (z={z:.2f}, needs |z| >= {bar:.2f} for {variants} variants)'
    return label + '; historical, not a forecast', round(z, 3)


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


def summarise(result, interval, reference=None, variants=None):
    """reference: closed BTC_USDT candles for regime labels (None = regimes unavailable).
    variants: how many comparisons this run reports in total; sets the significance bar."""
    period = INTERVAL_SECONDS[interval]
    pairs, signal_points, base_points, skipped = [], [], [], []
    for row in result['results']:
        if row.get('status') != 'RESEARCH_ONLY':
            skipped.append(dict(pair=row.get('pair'), reason=row.get('reason', 'unavailable')))
            continue
        kept = independent(row['backtest'].get('observations', []), period)
        base = baseline_points(row['candles'])
        pairs.append(dict(pair=row['pair'], candles=row['candle_count'], independent_signals=len(kept),
                          signal=stats([s['net_return'] for s in kept]), baseline=stats([r for _, r in base])))
        signal_points += [(s['signal_at'], s['net_return']) for s in kept]
        base_points += base
    all_signals = [r for _, r in signal_points]
    all_base = [r for _, r in base_points]
    variants = variants or 1
    sample = len(all_signals)
    if sample < MIN_INDEPENDENT:
        verdict = f'INSUFFICIENT SAMPLE: {sample} independent signals (need {MIN_INDEPENDENT}); no conclusion'
    else:
        edge = median(all_signals) - median(all_base)
        verdict = ('MEASURED: signal median net ' + format(median(all_signals), '.3%') + ' vs baseline ' +
                   format(median(all_base), '.3%') + ' (difference ' + format(edge, '+.3%') +
                   '); historical, correlated across pairs, not a forecast')
    pooled_test, pooled_z = slice_verdict(all_signals, all_base, variants)
    labels = regime_map(reference) if reference else {}
    regimes = None
    if labels:
        regimes = {}
        for name in REGIMES:
            sig = [r for t, r in signal_points if labels.get(t) == name]
            base = [r for t, r in base_points if labels.get(t) == name]
            test, z = slice_verdict(sig, base, variants)
            regimes[name] = dict(independent_signals=len(sig), baseline_windows=len(base), signal=stats(sig),
                                 baseline=stats(base), z=z, verdict=test)
    return dict(interval=interval, horizon_bars=HORIZON, round_trip_cost='0.4% (10 bps fee + 10 bps slippage each side, assumed)',
                pooled_signal=stats(all_signals), pooled_baseline=stats(all_base), pairs=pairs, skipped=skipped,
                verdict=verdict, pooled_test=pooled_test, pooled_z=pooled_z, variants_tested=variants,
                regime_definition=f'{REFERENCE} return over the last {LOOKBACK} closed bars: FALLING <= -{REGIME_THRESHOLD:.0%}, RISING >= +{REGIME_THRESHOLD:.0%}, else SIDEWAYS (fixed in advance, not tuned)',
                regime_status='OK' if regimes else 'UNAVAILABLE: reference series missing or too short',
                regimes=regimes, buy_authorized=False, orders_allowed=False)


def report(pairs=PAIRS, intervals=('1h', '4h'), *, fetch=cli.fetch_public, now=None):
    # Every pooled test plus every regime slice, for every interval, is one variant counted against chance.
    variants = len(intervals) * (1 + len(REGIMES))
    now_ts = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    out = []
    for interval in intervals:
        try:
            reference = market_reference(interval, fetch, now_ts)
        except Exception:
            reference = None
        out.append(summarise(cli.run(list(pairs), interval, fetch=fetch, now=now, keep_observations=True),
                             interval, reference, variants))
    return out


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

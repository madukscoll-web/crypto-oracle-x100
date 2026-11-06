"""Fixed-rule Spot experiments. Simulated fills are assumptions, never real trades.

No notification or admission authority. The same plan()/step() functions serve
historical replay and prospective closed-candle paper observation. New histories
are bootstrapped at observation time, never at an invented earlier alert fill.
"""
import copy
import hashlib
import json
import math
import pathlib
from statistics import mean

from altcoin_reversal_research import analyze

ROOT = pathlib.Path(__file__).resolve().parent
STRATEGIES = ('reversal_baseline', 'trend_pullback', 'range_breakout')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def positive(value, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Numeric measurement required')
    if not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError('Invalid measurement')
    return float(value)


def policy():
    p = json.loads((ROOT/'strategy_lab_policy.json').read_text())
    if (p.get('version') != 1 or p.get('strategies') != list(STRATEGIES)
            or p.get('buy_authorized') is not False or p.get('orders_allowed') is not False
            or p.get('warmup') != 55 or p.get('split_fractions') != [.5, .25, .25]):
        raise ValueError('Unsupported experiment policy')
    for k in ('entry_expiry_bars', 'maximum_holding_bars', 'minimum_test_closed_trades'):
        if type(p[k]) is not int or p[k] < 1:
            raise ValueError('Invalid bar/trade count')
    for k in ('risk_fraction', 'allocation_fraction', 'maximum_stop_fraction',
              'maximum_quote_volume_fraction', 'maximum_test_drawdown_fraction'):
        if not 0 < positive(p[k]) < 1:
            raise ValueError('Invalid fraction')
    for k in ('starting_equity_usdt', 'reward_risk', 'minimum_test_profit_factor'):
        positive(p[k])
    for k in ('fee_bps_per_side', 'slippage_bps_per_side'):
        if not 0 <= positive(p[k], True) <= 100:
            raise ValueError('Unsupported cost assumption')
    return p


def candles_valid(candles, period):
    if period not in (86400, 604800) or not isinstance(candles, list):
        raise ValueError('Unsupported candle sequence')
    previous = None
    for c in candles:
        if not isinstance(c, dict) or c.get('closed') is not True:
            raise ValueError('Closed candles required')
        t = c.get('timestamp')
        if type(t) is not int or t <= 0 or (previous is not None and t-previous != period):
            raise ValueError('Noncontiguous or invalid timestamps')
        o, h, l, close = (positive(c[k]) for k in ('open', 'high', 'low', 'close'))
        positive(c['volume'], True)
        if l > min(o, close) or h < max(o, close) or h < l:
            raise ValueError('Inconsistent OHLC')
        previous = t


def plan(pair, strategy, history, p):
    """Uses only supplied closed history. Targets are hypotheses, not forecasts."""
    if strategy not in STRATEGIES or len(history) < p['warmup']:
        return None
    c = history[-55:]
    close = [x['close'] for x in c]
    highs, lows = [x['high'] for x in c], [x['low'] for x in c]
    volumes = [x['volume'] for x in c]
    vmean = mean(volumes[-21:-1])
    if vmean <= 0:
        return None
    ratio = volumes[-1]/vmean
    ma20, ma50 = mean(close[-20:]), mean(close[-50:])
    if strategy == 'reversal_baseline':
        result = analyze(pair, c, source='Retained Gate closed candles',
                         observed_at=str(c[-1]['timestamp']))
        if result['classification'] not in ('EARLY REVERSAL WATCH', 'TECHNICAL REVERSAL WATCH'):
            return None
        entry, stop = result['entry_trigger'], result['invalidation']
    elif strategy == 'trend_pullback':
        if not (ma20 > ma50 and ma50 > mean(close[-55:-5])
                and min(lows[-5:]) <= ma20 and close[-1] > ma20
                and close[-1] > close[-2] and ratio >= 1):
            return None
        entry, stop = max(highs[-3:]), min(lows[-10:])
    else:
        top, bottom = max(highs[-21:-1]), min(lows[-21:-1])
        if not (top/bottom-1 <= .15 and close[-1] > top and ratio >= 1.5):
            return None
        entry, stop = max(top, close[-1]), bottom
    # Buy-stop confirmation: if price has already crossed the reference, require
    # at least the signal close. No backdated fill at the old breakout level.
    entry = max(entry, close[-1])
    risk = entry-stop
    if not 0 < risk/entry <= p['maximum_stop_fraction']:
        return None
    return dict(strategy=strategy, pair=pair, signal_at=c[-1]['timestamp'],
                entry=entry, stop=stop, target=entry+p['reward_risk']*risk,
                entry_type='SIMULATED_BUY_STOP_NEXT_BAR_OR_LATER',
                expires_after_bars=p['entry_expiry_bars'],
                maximum_holding_bars=p['maximum_holding_bars'],
                target_basis='Fixed experimental R multiple, not predicted resistance',
                buy_authorized=False, orders_allowed=False)


def account(p):
    return dict(equity=p['starting_equity_usdt'], pending=None, position=None,
                events=[], trades=[], marks=[], peak=p['starting_equity_usdt'],
                maximum_drawdown=0.0, turnover=0.0, exposed_bars=0, bars=0)


def event(a, kind, at, **values):
    record = dict(sequence=len(a['events']), kind=kind, at=at, **values,
                  previous_hash=a['events'][-1]['hash'] if a['events'] else None)
    record['hash'] = digest(record)
    a['events'].append(record)


def verify_events(events):
    previous = None
    for index, row in enumerate(events):
        content = {k:v for k,v in row.items() if k != 'hash'}
        if row.get('sequence') != index or row.get('previous_hash') != previous or digest(content) != row.get('hash'):
            raise ValueError('Paper event history invalid')
        previous = row['hash']


def step(a, bar, p, cost_multiplier=1):
    """One closed bar. Stop-first if intrabar path is unknown; no live fills."""
    fee = p['fee_bps_per_side']/10000*cost_multiplier
    slip = p['slippage_bps_per_side']/10000*cost_multiplier
    at, o, high, low, close = (bar[k] for k in ('timestamp', 'open', 'high', 'low', 'close'))
    a['bars'] += 1
    pending, position = a['pending'], a['position']
    if pending and at >= pending.get('eligible_after', 0):
        pending['age'] += 1
        if low <= pending['stop']:
            # Unknown path could have invalidated before entry; do not assume fill.
            event(a, 'CANCELLED', at, reason='Pre-entry invalidation or ambiguous path')
            a['pending'] = None
        elif pending['age'] > p['entry_expiry_bars']:
            event(a, 'EXPIRED', at)
            a['pending'] = None
        elif high >= pending['entry']:
            price = max(o, pending['entry'])*(1+slip)
            distance = price-pending['stop']
            # Reconcile risk after gaps, entry/exit fees and assumed stop slippage.
            per_unit_loss = distance + price*fee + pending['stop']*(slip+fee)
            desired = min(a['equity']*p['allocation_fraction']/(price*(1+fee)),
                          a['equity']*p['risk_fraction']/per_unit_loss)
            # Quote-volume participation is an explicit coarse assumption, not
            # proof that size was available at the trigger or in an order book.
            cap = bar['volume']*p['maximum_quote_volume_fraction']/price
            qty = min(desired, cap)
            if qty <= 0 or price >= pending['target']:
                event(a, 'CANCELLED', at, reason='No modeled capacity or gap beyond target')
                a['pending'] = None
            else:
                position = dict(entry=price, stop=pending['stop'], target=pending['target'],
                                quantity=qty, opened_at=at, age=0, mae=0.0,
                                entry_fee=qty*price*fee, signal_at=pending['signal_at'])
                a['equity'] -= position['entry_fee']
                a['turnover'] += qty*price
                a['position'] = position
                event(a, 'PARTIALLY_FILLED' if qty < desired else 'OPEN', at,
                      quantity=qty, requested_quantity=desired, entry=price,
                      remainder='CANCELLED; no automatic later averaging',
                      capacity_basis='Assumed quote-volume participation, not observed depth')
                a['pending'] = None
    position = a['position']
    if position:
        a['exposed_bars'] += 1
        position['age'] += 1
        position['mae'] = min(position['mae'], low/position['entry']-1)
        reason = None
        if low <= position['stop']:
            exit_price = min(o, position['stop'])*(1-slip)
            reason = 'STOP; stop-first on ambiguous bar'
        elif high >= position['target']:
            # Same-bar target may precede a new entry. Never award that gain.
            if at != position['opened_at']:
                exit_price = position['target']*(1-slip)
                reason = 'TARGET'
        if reason is None and position['age'] >= p['maximum_holding_bars']:
            exit_price, reason = close*(1-slip), 'TIME_EXPIRY'
        if reason:
            qty = position['quantity']
            exit_fee = qty*exit_price*fee
            pnl = qty*(exit_price-position['entry'])-position['entry_fee']-exit_fee
            a['equity'] += qty*(exit_price-position['entry'])-exit_fee
            a['turnover'] += qty*exit_price
            trade = dict(**position, closed_at=at, exit=exit_price, net_pnl_usdt=pnl,
                         reason=reason, simulated=True)
            a['trades'].append(trade)
            event(a, 'CLOSED', at, **trade)
            a['position'] = None
    unrealized = 0
    if a['position']:
        pos = a['position']
        liquidation = close*(1-slip)
        unrealized = pos['quantity']*(liquidation-pos['entry'])-pos['quantity']*liquidation*fee
    marked = a['equity']+unrealized
    a['peak'] = max(a['peak'], marked)
    a['maximum_drawdown'] = max(a['maximum_drawdown'], 1-marked/a['peak'])
    a['marks'].append(dict(at=at, equity=marked))


def queue(a, candidate, at, eligible_after=0):
    if candidate and not a['pending'] and not a['position']:
        a['pending'] = dict(candidate, age=0, eligible_after=eligible_after)
        event(a, 'AWAITING_ENTRY', at, plan=candidate)


def metrics(a, p):
    pnl = [t['net_pnl_usdt'] for t in a['trades']]
    wins, losses = sum(max(0,x) for x in pnl), -sum(min(0,x) for x in pnl)
    return dict(closed_trades=len(pnl), net_pnl_usdt=sum(pnl),
                net_expectancy_usdt=mean(pnl) if pnl else None,
                profit_factor=wins/losses if losses else None,
                profit_factor_status='FINITE' if losses else 'NO_LOSS_OBSERVATIONS',
                maximum_drawdown_fraction=a['maximum_drawdown'],
                marked_return=a['marks'][-1]['equity']/p['starting_equity_usdt']-1 if a['marks'] else 0,
                exposure_fraction=a['exposed_bars']/a['bars'] if a['bars'] else 0,
                turnover_usdt=a['turnover'],
                mean_holding_bars=mean(t['age'] for t in a['trades']) if pnl else None,
                worst_adverse_excursion=min((t['mae'] for t in a['trades']), default=None),
                open_position=a['position'] is not None, pending_entry=a['pending'] is not None)


def replay(pair, strategy, candles, start, end, p, cost_multiplier=1):
    a = account(p)
    # All decisions precede the bar they may fill. A split starts with no position
    # and cannot import the last signal of a training/validation period.
    for i in range(start, end):
        step(a, candles[i], p, cost_multiplier)
        if i+1 < end:
            queue(a, plan(pair, strategy, candles[:i+1], p), candles[i]['timestamp'])
    return metrics(a,p)


def benchmark(candles, start, end, p, multiplier=1):
    fee=p['fee_bps_per_side']/10000*multiplier
    slip=p['slippage_bps_per_side']/10000*multiplier
    first,last=candles[start],candles[end-1]
    entry=first['open']*(1+slip)
    capital=p['starting_equity_usdt']*p['allocation_fraction']
    qty=capital/(entry*(1+fee))
    equity=p['starting_equity_usdt']-capital+qty*last['close']*(1-slip)*(1-fee)
    return dict(marked_return=equity/p['starting_equity_usdt']-1,
                allocation_fraction=p['allocation_fraction'],
                assumptions='Static buy-and-hold, same starting capital/allocation/costs; different exposure')


def evaluate(pair, interval, candles, p):
    period=86400 if interval=='1d' else 604800
    candles_valid(candles,period)
    n=len(candles)
    embargo=p['maximum_holding_bars']+p['entry_expiry_bars']
    train_end=int(n*.5);validation_end=int(n*.75)
    splits={'training':(55,train_end),'validation':(train_end+embargo,validation_end),
            'final_test':(validation_end+embargo,n)}
    if any(end-start<20 for start,end in splits.values()):
        return dict(status='INSUFFICIENT_HISTORY', candle_count=n, buy_authorized=False)
    experiments=[]
    for strategy in p['strategies']:
        periods={name:dict(start=candles[start]['timestamp'],end=candles[end-1]['timestamp'],
                          metrics=replay(pair,strategy,candles,start,end,p),
                          doubled_cost_metrics=replay(pair,strategy,candles,start,end,p,2),
                          buy_hold=benchmark(candles,start,end,p))
                 for name,(start,end) in splits.items()}
        test=periods['final_test']['metrics']
        enough=test['closed_trades']>=p['minimum_test_closed_trades']
        passed=(enough and test['profit_factor'] is not None
                and test['profit_factor']>=p['minimum_test_profit_factor']
                and test['net_expectancy_usdt']>p['minimum_test_expectancy_usdt']
                and test['maximum_drawdown_fraction']<=p['maximum_test_drawdown_fraction']
                and periods['final_test']['doubled_cost_metrics']['net_pnl_usdt']>0
                and test['marked_return']>periods['final_test']['buy_hold']['marked_return'])
        experiments.append(dict(strategy=strategy,periods=periods,
                                numerical_screen='PASS' if passed else 'FAIL' if enough else 'INSUFFICIENT_EVIDENCE',
                                promotion='BLOCKED: current-survivor sample, historical depth and independent validation incomplete',
                                latest_plan=plan(pair,strategy,candles,p)))
    return dict(status='RESEARCH_ONLY',policy_id=p['policy_id'],policy_sha256=digest(p),
                candles_sha256=digest(candles),candle_count=n,embargo_bars=embargo,
                selection_bias='Current active-market selection; not historical point-in-time universe',
                final_test_usage='Fixed-rule descriptive test; never adaptive optimization or independent untouched certification',
                experiments=experiments,buy_authorized=False,orders_allowed=False)


def prospective(state, pair, interval, candles, p, observed_at):
    period=86400 if interval=='1d' else 604800
    candles_valid(candles,period)
    if len(candles)<55:
        raise ValueError('Insufficient prospective warmup')
    if not 0 <= observed_at-(candles[-1]['timestamp']+period) <= 2*period:
        raise ValueError('Stale/future prospective observation')
    ph=digest(p)
    if state.get('version')!=1 or not isinstance(state.get('accounts'),dict):
        raise ValueError('Invalid paper state')
    outcomes={}
    for strategy in p['strategies']:
        identity=f'{pair}|{interval}|{strategy}|{ph}'
        row=state['accounts'].get(identity)
        if row is None:
            a=account(p)
            row=dict(pair=pair,interval=interval,strategy=strategy,policy_sha256=ph,
                     monitoring_started_at=observed_at,last_timestamp=candles[-1]['timestamp'],
                     last_candle_sha256=digest(candles[-1]),account=a)
            event(a,'BOOTSTRAP',observed_at,history_fill='NONE',policy_sha256=ph)
            queue(a,plan(pair,strategy,candles,p),observed_at,eligible_after=observed_at)
            state['accounts'][identity]=row
            outcomes[strategy]='BOOTSTRAPPED_WITHOUT_BACKDATED_FILL'
            continue
        verify_events(row['account']['events'])
        bytime={c['timestamp']:c for c in candles}
        if row['last_timestamp'] not in bytime or digest(bytime[row['last_timestamp']])!=row['last_candle_sha256']:
            raise ValueError('Prospective history missing or revised')
        new=[c for c in candles if c['timestamp']>row['last_timestamp']]
        for c in new:
            if c['timestamp']!=row['last_timestamp']+period:
                raise ValueError('Prospective gap; no invented bars')
            step(row['account'],c,p)
            row['last_timestamp']=c['timestamp'];row['last_candle_sha256']=digest(c)
        if new:
            # Missed scans do not create historical decisions between observations.
            queue(row['account'],plan(pair,strategy,candles,p),observed_at,eligible_after=observed_at)
        outcomes[strategy]='ADVANCED' if new else 'NO_NEW_CLOSED_CANDLE'
    return outcomes


def attach(report, state, p, observed_at):
    """Replay retained exact public candles, with no additional network requests."""
    from altcoin_reversal_gate import gate_candles
    rows=[]
    portfolio_series={}
    updated=copy.deepcopy(state)
    for row in report.get('results',[]):
        if row.get('status')!='RESEARCH_ONLY':
            continue
        result=dict(pair=row['pair'],interval=row['interval'])
        try:
            period=86400 if row['interval']=='1d' else 604800
            evidence=[e for e in row['provider_evidence'] if '/spot/candlesticks?' in e['url']]
            if len(evidence)!=1:
                raise ValueError('Exact candle provenance missing')
            candles=gate_candles(evidence[0]['raw'],interval_seconds=period,now=observed_at)
            result['evaluation']=evaluate(row['pair'],row['interval'],candles,p)
            portfolio_series.setdefault(row['interval'],{})[row['pair']]=candles
            result['prospective']=prospective(updated,row['pair'],row['interval'],candles,p,observed_at)
        except (ValueError,KeyError,TypeError,OverflowError) as exc:
            result.update(status='UNAVAILABLE',reason=str(exc)[:180])
        rows.append(result)
    import strategy_portfolio
    portfolios=[]
    for interval,series in portfolio_series.items():
        for strategy in p['strategies']:
            try:
                portfolios.append(dict(interval=interval,**strategy_portfolio.replay(series,strategy,p)))
            except (ValueError,KeyError,TypeError) as exc:
                portfolios.append(dict(interval=interval,strategy=strategy,status='UNAVAILABLE',reason=str(exc)[:180]))
    return updated,dict(portfolio_evaluations=portfolios,scope='EXPERIMENTAL_PAPER_ONLY',policy_id=p['policy_id'],policy_sha256=digest(p),
                        rows=rows,buy_authorized=False,orders_allowed=False,
                        strategy_validated=False,
                        limitations=['Current-survivor selection; no strategy certified.',
                                     'Prospective per-pair accounts are independent; separate retrospective static-sleeve portfolio results are explicitly labelled.',
                                     'Candle fills and capacity are assumptions; real depth/fills unknown.',
                                     'Prospective entries require a full bar starting after observation; no backdated intrabar fills.',
                                     'Missed scans never create intermediate historical entry decisions.',
                                     'Closed-bar processing may discover stops late; not real-time execution.',
                                     'No statistical confidence or market-regime robustness established.'])

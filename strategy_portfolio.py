"""Conservative shared-capital historical experiment with static cash sleeves.

All assets are treated as one correlated risk group. At most three pending/open
positions per portfolio; cash is partitioned once, never counted twice. No claim
of empirical covariance modelling, real fills, or independently validated returns.
"""
import copy
from statistics import mean

import strategy_lab as lab


def replay(series, strategy, p, *, split='final_test', maximum_positions=3):
    if strategy not in lab.STRATEGIES or type(maximum_positions) is not int or not 1<=maximum_positions<=3:
        raise ValueError('Invalid portfolio policy')
    if split not in ('training','validation','final_test') or not series:
        raise ValueError('Invalid portfolio input')
    pairs=sorted(series)
    # Exact common chronological dates only. Do not forward fill absent markets.
    common=set.intersection(*(set(c['timestamp'] for c in series[pair]) for pair in pairs))
    times=sorted(common)
    if len(times)<240:
        return dict(status='INSUFFICIENT_COMMON_HISTORY',pairs=pairs,buy_authorized=False)
    normalized={pair:[c for c in series[pair] if c['timestamp'] in common] for pair in pairs}
    for candles in normalized.values():
        period=candles[1]['timestamp']-candles[0]['timestamp']
        lab.candles_valid(candles,period)
    embargo=p['maximum_holding_bars']+p['entry_expiry_bars']
    n=len(times)
    ranges={'training':(55,int(n*.5)), 'validation':(int(n*.5)+embargo,int(n*.75)),
            'final_test':(int(n*.75)+embargo,n)}
    start,end=ranges[split]
    sleeve=copy.deepcopy(p)
    sleeve['starting_equity_usdt']=p['starting_equity_usdt']/len(pairs)
    accounts={pair:lab.account(sleeve) for pair in pairs}
    curve=[];peak=p['starting_equity_usdt'];drawdown=0.;slots=0;deferred=0
    for i in range(start,end):
        for pair in pairs:
            lab.step(accounts[pair],normalized[pair][i],sleeve)
        used=sum(bool(a['position'] or a['pending']) for a in accounts.values())
        # Rotate deterministic tie order; it cannot depend on later outcomes.
        rotation=i%len(pairs)
        order=pairs[rotation:]+pairs[:rotation]
        if i+1<end:
            for pair in order:
                a=accounts[pair]
                if a['position'] or a['pending']:
                    continue
                candidate=lab.plan(pair,strategy,normalized[pair][:i+1],p)
                if candidate:
                    if used>=maximum_positions:
                        deferred+=1
                    else:
                        lab.queue(a,candidate,times[i]);used+=1
        slots=max(slots,used)
        total=sum(a['marks'][-1]['equity'] for a in accounts.values())
        peak=max(peak,total);drawdown=max(drawdown,1-total/peak)
        curve.append(dict(at=times[i],equity=total,occupied_slots=used))
    trades=[dict(pair=pair,**t) for pair,a in accounts.items() for t in a['trades']]
    pnl=[t['net_pnl_usdt'] for t in trades]
    gains=sum(max(0,x) for x in pnl);loss=-sum(min(0,x) for x in pnl)
    hold=mean(lab.benchmark(normalized[pair],start,end,p)['marked_return'] for pair in pairs)
    return dict(status='RESEARCH_ONLY',strategy=strategy,split=split,pairs=pairs,
                start=times[start],end=times[end-1],closed_trades=len(trades),
                starting_equity_usdt=p['starting_equity_usdt'],
                final_marked_equity_usdt=curve[-1]['equity'],
                marked_return=curve[-1]['equity']/p['starting_equity_usdt']-1,
                net_closed_pnl_usdt=sum(pnl),net_expectancy_usdt=mean(pnl) if pnl else None,
                profit_factor=gains/loss if loss else None,
                maximum_drawdown_fraction=drawdown,maximum_occupied_slots=slots,
                deferred_signals_due_to_slots=deferred,
                turnover_usdt=sum(a['turnover'] for a in accounts.values()),
                equal_weight_buy_hold_marked_return=hold,
                curve=curve,trades=trades,
                capital_policy='One shared starting balance partitioned into static nonoverlapping cash sleeves; no cash transfer or double counting',
                correlation_policy='All pairs one risk group; total planned allocation at most 10% of summed sleeve equity, risk 1%; gaps can exceed risk',
                limitations=['Current-survivor sample; empirical correlation/regime robustness not established.',
                             'Candle capacity and execution costs are assumed; real fills/depth unknown.',
                             'Static sleeves can underutilize capital; results do not imply optimal allocation.'],
                strategy_validated=False,buy_authorized=False,orders_allowed=False)

"""Read-only validation cohort, NOT an approved or recommended token universe."""
import datetime as dt
import json
import pathlib

from asset_identity import key
from gate_spot_research import PublicGate
from provider_session import Session
import fundamental_evidence
import verification
import supply_evidence

COHORT = (
    dict(symbol='QUID', network='base', token_address='0x1a44233fae8d50f1aeb3a5d58dd426ff4814cb53', address='0x07c4bc0f5fb6cb069124df3e1ae0b8fd8148ccc4'),
    dict(symbol='XDP', network='base', token_address='0x07b3d902783c3c12b077508c3b5c00113d1291d0', address='0x2df380544b88adb3ad0a94100dcc45fd705aae2d'),
    dict(symbol='GENIUS', network='bsc', token_address='0x1f12b85aac097e43aa1555b2881e98a51090e9a6', address='0x2a45d6e78af8531b026f2d50e2db238c2dbfdfbf5201eb0669b0fd5ac377d545'),
)


def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()


def summarize(candidate):
    sec=candidate.get('verification') or {}
    supply=candidate.get('fundamentals') or {}
    return dict(symbol=candidate['symbol'], network=candidate['network'], contract=candidate['token_address'],
        gate_spot=candidate['gate_spot'],
        provider_screening={k:dict(status=v.get('status'),reason=v.get('reason'),diagnostic=v.get('diagnostic'))
                            for k,v in sec.items() if k in ('contract_security','goplus','sellability','honeypot','holders','tokenomics')},
        supply={k:dict(value=supply.get(k,{}).get('value'),status=supply.get(k,{}).get('status'),reason=supply.get(k,{}).get('reason'))
                for k in ('circulating_supply','total_supply','max_supply')},
        pinned_supply_comparison={k:(candidate.get('supply_comparison') or {}).get(k) for k in ('status','reason')},
        market=candidate.get('gate_market',{}),
        decision='RESEARCH ONLY — NO BUY AUTHORITY')


def run(fetch=None, cohort=COHORT, checkpoint=None):
    if fetch is None:
        with Session(max_requests=120,max_seconds=150,max_request_seconds=5) as session:
            report=run(session.get,cohort,checkpoint)
            report['provider_session']=session.summary()
            return report
    report=dict(started_at=utc(),scope='Three historical bot leads; not market coverage or token approval',
                automated_trading_enabled=False,can_issue_buy=False,candidates=[],errors=[])
    gate=PublicGate(fetch)
    try: report['gate_catalog']=gate.catalog()
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        report['errors'].append('Gate catalog unavailable: '+type(exc).__name__)
    for original in cohort:
        item=dict(original)
        try:
            item['asset_key']=key(item['network'],item['token_address'])
            item['gate_spot']=gate.eligibility(item)
            item['verification']=verification.collect(item,fetch)
            item['fundamentals']=fundamental_evidence.collect(item,fetch)
            item['supply_comparison']=supply_evidence.collect(item,fetch)
            if item['gate_spot'].get('status')=='CONFIRMED_SPOT':
                item['gate_market']=gate.research(item['gate_spot'])
            # Every raw source response from Gate is retained in the report.
            report['gate_evidence']=gate.evidence
            report['candidates'].append(item)
            print('GATE_PROBE_RESULT '+json.dumps(summarize(item),sort_keys=True),flush=True)
        except Exception as exc:
            item['error_type']=type(exc).__name__
            item.setdefault('gate_spot',dict(status='UNKNOWN',reason='Probe incomplete'))
            report['candidates'].append(item)
            print('GATE_PROBE_ERROR '+json.dumps(dict(symbol=item['symbol'],error_type=type(exc).__name__)),flush=True)
        if checkpoint:checkpoint(report)
    report['finished_at']=utc()
    report['remaining_requirements']=['Actual primary unlock/circulation and holder/authority review',
        'Gate Spot eligibility is distinct from futures and from underlying token safety',
        'Live strategy qualification and forward observation; no reviewed-token record is fabricated']
    return report


if __name__=='__main__':
    path=pathlib.Path('gate_live_probe_report.json')
    def save(report):
        temp=path.with_suffix('.json.tmp')
        temp.write_text(json.dumps(report,indent=2)+'\n')
        temp.replace(path)
    save(run(checkpoint=save))

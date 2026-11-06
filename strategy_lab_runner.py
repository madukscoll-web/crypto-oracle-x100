"""Read retained production evidence and atomically publish prospective paper state."""
import datetime as dt
import json
import pathlib

import strategy_lab


def main():
    p=strategy_lab.policy()
    report=json.loads(pathlib.Path('altcoin_reversal_report.json').read_text())
    state_path=pathlib.Path('strategy_lab_state.json')
    state=json.loads(state_path.read_text()) if state_path.exists() else {'version':1,'accounts':{}}
    at=dt.datetime.now(dt.timezone.utc).timestamp()
    observed=dt.datetime.fromisoformat(report['as_of'].replace('Z','+00:00')).timestamp()
    if not 0 <= at-observed <= 900:
        raise ValueError('Stale/future source report')
    state,result=strategy_lab.attach(report,state,p,at)
    result['as_of']=dt.datetime.fromtimestamp(at,dt.timezone.utc).isoformat()
    result['source_as_of']=report['as_of']
    result['source_report_sha256']=strategy_lab.digest(report)
    result['errors']=[r for r in result['rows']+result['portfolio_evaluations'] if r.get('status')=='UNAVAILABLE']
    result['status']='DEGRADED' if result['errors'] else 'COMPLETED' if result['rows'] else 'UNAVAILABLE'
    pathlib.Path('strategy_lab_report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    if result['errors'] or not result['rows']:
        # Never publish a partially advanced state after any row failed.
        print(json.dumps({'status':result['status'],'errors':result['errors']}))
        return 1
    if len(state['accounts'])>180:
        raise ValueError('Prospective account capacity reached; no history silently deleted')
    temp=state_path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(state,indent=2,allow_nan=False)+'\n')
    temp.replace(state_path)
    print(json.dumps({'status':result['status'],'rows':len(result['rows']),
                      'accounts':len(state['accounts']),'strategy_validated':False,
                      'buy_authorized':False,'orders_allowed':False}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

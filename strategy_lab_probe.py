"""Bounded read-only CI probe. Never sends messages or persists production state."""
import json
import pathlib
import time

from provider_session import Session
from altcoin_reversal_cli import run
import strategy_lab


def main():
    with Session(max_requests=6,max_seconds=80,max_request_seconds=8) as session:
        source=run(['AVAX_USDT','BNB_USDT','NEAR_USDT'],fetch=session.get)
        for row in source['results']:row['interval']='1d'
        source['provider_session']=session.summary()
    pathlib.Path('work').mkdir(exist_ok=True)
    pathlib.Path('work/strategy_lab_probe_sources.json').write_text(json.dumps(source,indent=2)+'\n')
    state,result=strategy_lab.attach(source,{'version':1,'accounts':{}},strategy_lab.policy(),time.time())
    result['source_unavailable']=[{'pair':r['pair'],'reason':r.get('reason')} for r in source['results'] if r['status']!='RESEARCH_ONLY']
    result['probe_status']='DEGRADED' if result['source_unavailable'] or len(result['rows'])!=3 or any(r.get('status')=='UNAVAILABLE' for r in result['rows']) else 'COMPLETED'
    pathlib.Path('work/strategy_lab_probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'probe_status':result['probe_status'],'pairs':len(result['rows']),
                      'strategy_validated':False,'buy_authorized':False,'orders_allowed':False}))
    # Provider outages are retained as probe results, never a passing validation.
    # Unit tests remain independent from public provider uptime.


if __name__=='__main__':main()

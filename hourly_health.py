"""Detect observable gaps in scheduled scanner starts; cannot repair a scheduler.

A successful job is not proof of hourly delivery. Reports remain UNKNOWN when
history is unavailable. --notify sends only a significant cadence-gap alert.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import urllib.request


def timestamp(value):
    parsed=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Timezone absent')
    return parsed.timestamp()


def assess(runs,current_id,now,maximum_gap_seconds=5400):
    records=[x for x in runs if x.get('path')=='.github/workflows/main.yml' and x.get('event')=='schedule' and x.get('head_branch')=='main']
    records=sorted(records,key=lambda x:timestamp(x['created_at']))
    current=next((x for x in records if str(x['id'])==str(current_id)),None)
    start=timestamp(current['created_at']) if current else now
    previous=[x for x in records if timestamp(x['created_at'])<start and str(x['id'])!=str(current_id)]
    if not previous:return dict(status='UNKNOWN',reason='Previous scheduled scanner run unavailable',hourly_verified=False)
    previous=previous[-1];gap=start-timestamp(previous['created_at'])
    return dict(status='DEGRADED' if gap>maximum_gap_seconds else 'WITHIN_OBSERVED_CADENCE',
                gap_seconds=gap,previous_run_id=previous['id'],previous_conclusion=previous.get('conclusion'),
                current_run_id=current_id,hourly_verified=False,
                reason='Scheduled scanner start gap exceeds 90 minutes' if gap>maximum_gap_seconds else 'One observed interval within 90 minutes; continuous operation not established')


def history(repository,token):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('Repository identity absent')
    request=urllib.request.Request('https://api.github.com/repos/'+repository+'/actions/runs?event=schedule&per_page=30',
        headers={'Accept':'application/vnd.github+json','Authorization':'Bearer '+token,'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=15) as response:raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Workflow history exceeds limit')
    return json.loads(raw)['workflow_runs']


def run(env=None,notify=False,fetch=history,send=None):
    env=os.environ if env is None else env
    try:
        token=env.get('GH_TOKEN','')
        if not token:raise ValueError('Read-only Actions API credential unavailable')
        report=assess(fetch(env.get('GITHUB_REPOSITORY',''),token),env.get('GITHUB_RUN_ID',''),dt.datetime.now(dt.timezone.utc).timestamp())
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):
        report=dict(status='UNKNOWN',reason='Scheduled-run history unavailable or malformed',hourly_verified=False)
    report.update(alert_delivered=False,orders_allowed=False)
    pathlib.Path('work').mkdir(exist_ok=True)
    path=pathlib.Path('work/hourly_health.json')
    path.write_text(json.dumps(report,indent=2)+'\n')
    if notify and report['status']=='DEGRADED':
        if send is None:
            from telegram_notify import send_message
            send=send_message
        message=('CRYPTO-ORACLE X100 SYSTEM HEALTH: scheduled scanner gap '+format(report['gap_seconds']/3600,'.2f')+
                 ' hours. Hourly operation is NOT verified. No BUY signal. Previous run: https://github.com/'+env.get('GITHUB_REPOSITORY','')+'/actions/runs/'+str(report['previous_run_id']))
        # Persist a failure rather than claiming a send merely because attempted.
        try:
            if send(message) is not True:raise RuntimeError('Delivery unconfirmed')
            report['alert_delivered']=True
        except Exception:
            report['notification_status']='FAILED_OR_UNCONFIRMED'
            path.write_text(json.dumps(report,indent=2)+'\n')
            raise RuntimeError('Cadence health notification unconfirmed') from None
        path.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--notify',action='store_true')
    args=parser.parse_args();print(json.dumps(run(notify=args.notify),indent=2))

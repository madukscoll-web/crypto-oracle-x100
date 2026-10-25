"""Bounded live alert validation; never writes production watchlist/scanner state.

An explicitly authorized --send-example sends at most ONE logical alert example,
labelled EXAMPLE/NOT LIVE, using actual candidate observations and the real renderer.
No classified candidate is promoted to BUY or a live watch for a delivery test.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import opportunity_alerts as alerts
from live_candidate_scan import run,write_report


def validate(output,limit=4,networks=('base','eth'),send_example=False):
    config=alerts.policy(os.environ.get('ORACLE_WATCH_POLICY'))
    classified=set();delivery=dict(status='NOT_REQUESTED',logical_examples_sent=0)
    def checkpoint(report):
        for item in report['candidates']:
            if item['key'] in classified:continue
            result=alerts.classify(item,config)
            result['classified_at']=dt.datetime.now(dt.timezone.utc).isoformat()
            item['opportunity_classification']=result;classified.add(item['key'])
            print('ALERT_CLASSIFICATION',item['network'],item['token_address'],result['classification'],result['score'],flush=True)
            # Independent delivery diagnostic; fail rather than pretend sent.
            if send_example and delivery['logical_examples_sent']==0 and delivery['status']!='FAILED':
                try:
                    alerts.deliver(item,result,'DEPLOYMENT FORMAT/DELIVERY VALIDATION — EXAMPLE ONLY',os.environ,example=True)
                    delivery.update(status='DELIVERY_CONFIRMED',logical_examples_sent=1)
                except (OSError,ValueError,RuntimeError):delivery.update(status='FAILED',reason='Telegram delivery/destination confirmation failed')
        report['alert_validation']=dict(policy=config,delivery=delivery,automated_trading_enabled=False)
        write_report(output,report)
    report=run(networks,limit,checkpoint=checkpoint)
    checkpoint(report)
    report['alert_classification_counts']={label:sum(c['opportunity_classification']['classification']==label for c in report['candidates']) for label in ('VERIFIED BUY','HIGH-PRIORITY WATCH','ENTRY WATCH','REJECT','INELIGIBLE')}
    report['alert_validation']['production_state_modified']=False
    write_report(output,report)
    print('ALERT_VALIDATION',json.dumps(report['alert_classification_counts']),delivery['status'],flush=True)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='watch_alert_validation.json');p.add_argument('--limit',type=int,default=4);p.add_argument('--send-example',action='store_true');args=p.parse_args()
    report=validate(args.output,args.limit,send_example=args.send_example)
    if args.send_example and report['alert_validation']['delivery']['status']!='DELIVERY_CONFIRMED':return 2
    return 0

if __name__=='__main__':raise SystemExit(main())

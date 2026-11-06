"""Explicit research-stage outcomes; green Actions alone is not full readiness."""
import json
import os
import pathlib


def summarize(stages, reports):
    required=('scan','reversal','technical_followup','strategy_lab')
    failures={k:v for k,v in stages.items() if v not in ('success',)}
    missing=[k for k in required if k not in reports or not isinstance(reports[k],dict)]
    historical=reports.get('historical',{})
    admission=reports.get('admission',{})
    # A partial script that emitted an artifact before failing is still degraded.
    degraded=bool(failures or missing)
    return dict(version=1,status='DEGRADED' if degraded else 'COMPLETED',
                stage_outcomes=stages,failed_or_skipped_stages=failures,
                missing_reports=missing,
                admission_status=admission.get('status','UNKNOWN'),
                historical_validation_status=historical.get('status','UNKNOWN'),
                strategy_validated=False,live_buy_admission_verified=False,
                overall_objective='BLOCKED',buy_authorized=False,orders_allowed=False)


def main():
    stages=json.loads(os.environ.get('RESEARCH_STAGE_OUTCOMES','{}'))
    paths={'scan':'scan_summary.json','reversal':'altcoin_reversal_report.json',
           'technical_followup':'technical_followup_report.json','strategy_lab':'strategy_lab_report.json',
           'historical':'historical_validation_report.json','admission':'work/admission_preflight.json'}
    reports={}
    for name,path in paths.items():
        try:
            reports[name]=json.loads(pathlib.Path(path).read_text())
        except (OSError,ValueError):
            continue
    result=summarize(stages,reports)
    pathlib.Path('pipeline_health_report.json').write_text(json.dumps(result,indent=2)+'\n')
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as stream:
            stream.write('## Research stage health\n\nStatus: '+result['status']+
                         '\n\nOverall objective: BLOCKED; no validated strategy or live BUY admission.\n\n')
            for name,outcome in stages.items():
                stream.write(f'- {name}: {outcome}\n')
    print(json.dumps(result))
    return int(result['status']=='DEGRADED')


if __name__=='__main__':
    raise SystemExit(main())

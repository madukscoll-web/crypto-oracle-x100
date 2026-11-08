"""Explicit research-stage outcomes; green Actions alone is not full readiness."""
import json
import os
import pathlib


def summarize(stages, reports):
    required=('scan','reversal','technical_followup','strategy_lab')
    failures={k:v for k,v in stages.items() if v not in ('success',)}
    missing=[k for k in required if k not in reports or not isinstance(reports[k],dict)]
    if 'atl' in stages and not isinstance(reports.get('atl'),dict):
        missing.append('atl')
    atl=reports.get('atl',{})
    if 'atl' in stages and atl.get('status') != 'OBSERVATIONS_UNVERIFIED':
        failures['atl_data']=atl.get('status','MISSING')
    data_degradation={}
    if 'multichain' in stages:
        market=reports.get('multichain')
        if not isinstance(market,dict):
            missing.append('multichain')
        else:
            count=(market.get('coverage_audit') or {}).get('discovery_failure_count')
            if (type(count) is not int or count < 0 or count > 0 or market.get('failures')
                    or any(x.get('status')=='DEGRADED' for x in market.get('provider_health',[]))):
                data_degradation['multichain']='Provider failures or incomplete coverage diagnostics'
    historical=reports.get('historical',{})
    admission=reports.get('admission',{})
    # A partial script that emitted an artifact before failing is still degraded.
    degraded=bool(failures or missing or data_degradation)
    return dict(version=1,status='DEGRADED' if degraded else 'COMPLETED',
                stage_outcomes=stages,failed_or_skipped_stages=failures,
                missing_reports=missing,data_degradation=data_degradation,
                atl_history_status=atl.get('status','NOT_RUN'),
                atl_lifetime_baselines=atl.get('historical_baselines_validated',0),
                admission_status=admission.get('status','UNKNOWN'),
                historical_validation_status=historical.get('status','UNKNOWN'),
                strategy_validated=False,live_buy_admission_verified=False,
                overall_objective='BLOCKED',buy_authorized=False,orders_allowed=False)


def main():
    stages=json.loads(os.environ.get('RESEARCH_STAGE_OUTCOMES','{}'))
    paths={'scan':'scan_summary.json','reversal':'altcoin_reversal_report.json',
           'technical_followup':'technical_followup_report.json','strategy_lab':'strategy_lab_report.json',
           'multichain':'multichain_research_report.json','atl':'atl_coverage_report.json','historical':'historical_validation_report.json','admission':'work/admission_preflight.json'}
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
    # Coverage degradation stays visible in artifacts/digest without presenting
    # a completed scan as a crashed workflow or sending repeated failure alerts.
    return int(bool(result['failed_or_skipped_stages'] or result['missing_reports']))


if __name__=='__main__':
    raise SystemExit(main())


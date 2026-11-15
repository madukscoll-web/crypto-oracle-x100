"""Explicit research-stage outcomes; green Actions alone is not full readiness."""
import json
import os
import pathlib


def summarize(stages, reports):
    required=('scan','reversal','technical_followup','strategy_lab')
    if 'dossiers' in stages:
        required+=('dossiers',)
    failures={k:v for k,v in stages.items() if v not in ('success',)}
    failures.update({k:'NOT_REPORTED' for k in required if k not in stages})
    missing=[k for k in required if k not in reports or not isinstance(reports[k],dict)]
    if 'atl' in stages and not isinstance(reports.get('atl'),dict):
        missing.append('atl')
    atl=reports.get('atl',{})
    atl=atl if isinstance(atl,dict) else {}
    data_degradation={}
    if 'atl' in stages and atl.get('status') != 'OBSERVATIONS_UNVERIFIED':
        data_degradation['atl']='ATL coverage is '+str(atl.get('status','MISSING'))
    # A zero exit code establishes computation, not complete provider coverage.
    scan=reports.get('scan',{})
    if isinstance(scan,dict) and scan.get('warnings'):
        data_degradation['scan']='Core discovery reported incomplete coverage; inspect scan warnings'
    for name in ('scan','reversal','technical_followup','strategy_lab'):
        report=reports.get(name)
        if not isinstance(report,dict):
            continue
        if report.get('errors') or report.get('status') in ('DEGRADED','UNAVAILABLE','FAILED'):
            data_degradation[name]='Stage report contains errors or unavailable observations'
        for channel in ('technical_delivery','invalidation_delivery'):
            delivery=report.get(channel) or {}
            if not isinstance(delivery,dict):
                data_degradation[name]='Malformed delivery diagnostics; delivery not established'
                continue
            if delivery.get('failed'):
                failures[name+'_delivery']='Unconfirmed Telegram delivery'
            if delivery.get('errors'):
                data_degradation[name]='Some observations could not be safely validated for delivery'
    if atl.get('enrichment_errors'):
        data_degradation['atl']='Metadata/history enrichment unavailable or invalid; no verified lifetime claim'
    lifetime=atl.get('lifetime_validation') or {}
    if not isinstance(lifetime,dict):
        data_degradation['atl_lifetime']='Malformed lifetime validation diagnostics'
        lifetime={}
    if lifetime.get('assessed') and lifetime.get('status')=='UNVERIFIED':
        data_degradation['atl_lifetime']='Enrolled history evidence failed independent validation; no qualified alert'
    atl_delivery=atl.get('research_delivery') or {}
    if not isinstance(atl_delivery,dict):
        data_degradation['atl']='Malformed ATL delivery diagnostics'
        atl_delivery={}
    if atl_delivery.get('failed') or lifetime.get('failed'):
        failures['atl_delivery']='Unconfirmed Telegram research delivery' 
    if 'multichain' in stages:
        market=reports.get('multichain')
        if not isinstance(market,dict):
            missing.append('multichain')
        else:
            audit=market.get('coverage_audit') or {}
            audit=audit if isinstance(audit,dict) else {}
            count=audit.get('discovery_failure_count')
            providers=market.get('provider_health') or []
            if not isinstance(providers,list):providers=[None]
            if (type(count) is not int or count < 0 or count > 0 or market.get('failures')
                    or any(not isinstance(x,dict) or x.get('status')=='DEGRADED' for x in providers)):
                data_degradation['multichain']='Provider failures or incomplete coverage diagnostics'
    historical=reports.get('historical',{})
    historical=historical if isinstance(historical,dict) else {}
    admission=reports.get('admission',{})
    admission=admission if isinstance(admission,dict) else {}
    # A partial script that emitted an artifact before failing is still degraded.
    degraded=bool(failures or missing or data_degradation)
    return dict(version=1,status='DEGRADED' if degraded else 'COMPLETED',
                stage_outcomes=stages,failed_or_skipped_stages=failures,
                execution_status='FAILED_OR_INCOMPLETE' if failures or missing else 'COMPLETED',
                coverage_status='DEGRADED' if data_degradation else 'NO_REPORTED_PROVIDER_ERRORS',
                missing_reports=missing,data_degradation=data_degradation,
                research_readiness='PARTIAL_PROVIDER_RESEARCH_ONLY' if reports.get('dossiers') else 'NOT_ESTABLISHED',
                alert_delivery={name: {channel: report.get(channel) for channel in ('alerts_delivered','research_watch_delivered','technical_delivery','invalidation_delivery','research_delivery') if channel in report} for name,report in reports.items() if isinstance(report,dict)},
                delivery_scope='Reported automatic delivery counts; inspect channel receipts for proof. Not purchase approval.',
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
           'multichain':'multichain_research_report.json','atl':'atl_coverage_report.json','historical':'historical_validation_report.json','admission':'work/admission_preflight.json','dossiers':'research_dossiers.json'}
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



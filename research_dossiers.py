"""Source-bound Gate research dossiers; no approvals or notification authority."""
import copy
import datetime as dt
import hashlib
import json
import pathlib
import time

import project_context
import technical_watch


def build(report, *, now=None, maximum=3):
    now=time.time() if now is None else now
    if type(maximum) is not int or not 1 <= maximum <= 6:
        raise ValueError('Invalid dossier budget')
    output=dict(scope='TECHNICAL_RESEARCH_DOSSIERS_NOT_ADMISSION',
                observed_at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),
                buy_authorized=False,orders_allowed=False,dossiers=[],withheld_reasons={})
    policy=technical_watch.policy()
    seen=set()
    rows=sorted(report['results'],key=lambda r:(r.get('interval')!='1d',r.get('pair','')))
    for row in rows:
        if (row.get('research') or {}).get('classification') not in technical_watch.WATCHES:
            continue
        key=(row.get('pair'),row.get('interval'))
        if key in seen:
            continue
        seen.add(key)
        try:
            research=technical_watch.validated_research(row,report,now,policy)
            sources=[dict(url=e['url'],retrieved_at=e['retrieved_at'],
                raw=copy.deepcopy(e['raw']),
                raw_sha256=hashlib.sha256(json.dumps(e['raw'],sort_keys=True,
                    separators=(',',':'),allow_nan=False).encode()).hexdigest())
                for e in row['provider_evidence']]
            screening=row.get('technical_screen') or {}
            findings=screening.get('security') or []
            adverse=any(s.get('status')=='FAIL' for s in findings)
            profile=row.get('project_context')
            if not isinstance(profile,dict) or profile.get('identity',{}).get('pair')!=row['pair']:
                profile=project_context.empty({'pair':row['pair']},now,'Exact-market context unavailable')
            output['dossiers'].append(dict(
                pair=row['pair'],interval=row['interval'],
                status='WITHHELD_ADVERSE_FINDING' if adverse else 'RESEARCH_ONLY_NOT_APPROVED',
                market_identity='Exact Gate Spot pair; independent on-chain identity is not established',
                classification=research['classification'],
                last_closed_price_usdt=research['metrics']['close'],
                entry_trigger_reference_usdt=research['entry_trigger'],
                invalidation_reference_usdt=research['invalidation'],
                volume_ratio=research['metrics']['volume_ratio'],
                confirmation='Require a fresh close/retest and volume; no entry or fill is inferred',
                reassessment='Next closed candle and before acting; withdraw on invalidation or adverse evidence',
                conditional_plan=research.get('conditional_plan'),
                liquidity_observation=screening.get('book') or {'status':'UNKNOWN_NOT_SCREENED_IN_THIS_RUN'},
                liquidity_observed_at=screening.get('observed_at','UNKNOWN'),
                liquidity_scope='Recorded displayed depth, not a current or funded execution guarantee',
                provider_security_findings=findings,
                project_context=profile,sources=sources,
                unresolved=['Independent security/authority and sellability review',
                    'Adjusted beneficial ownership and pool controls where applicable',
                    'Primary/independent circulating supply and unlock evidence',
                    'Fresh order-specific fees, slippage and funded execution evidence',
                    'Strategy calibration; no validated profitability or success probability'],
                buy_authorized=False,orders_allowed=False))
        except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
            reason=str(exc)[:120] if isinstance(exc,ValueError) else type(exc).__name__
            output['withheld_reasons'][reason]=output['withheld_reasons'].get(reason,0)+1
        if len(output['dossiers']) >= maximum:
            break
    output['count']=len(output['dossiers'])
    return output


def markdown(report):
    lines=['# Gate Spot research dossiers', '', 'Research only. No BUY approval, orders or assumed fills.',
           '', 'Observed UTC: '+report['observed_at'], '']
    for d in report['dossiers']:
        lines += ['## '+d['pair']+' | '+d['interval'], '', '**'+d['status']+'**', '',
            '| Item | Recorded evidence |','|---|---|',
            '| Last closed candle | '+str(d['last_closed_price_usdt'])+' USDT |',
            '| Conditional trigger reference | '+str(d['entry_trigger_reference_usdt'])+' USDT |',
            '| Invalidation reference | '+str(d['invalidation_reference_usdt'])+' USDT |',
            '| Volume / baseline | '+str(d['volume_ratio'])+'x |','',
            d['confirmation']+'. '+d['reassessment']+'.', '',d['market_identity']+'.', '',
            project_context.summary(d['project_context'],expected={'pair':d['pair']}), '',
            '### Outstanding evidence', '']
        lines += ['- '+gap for gap in d['unresolved']]
        lines += ['', '### Source observations', '']
        for source in d['sources']:
            lines += ['- '+source['url']+' | retrieved '+source['retrieved_at']+
                      ' | raw SHA-256 '+source['raw_sha256']]
        lines += ['', 'Raw candles, project context and screening observations remain in the accompanying JSON reports.', '']
    if not report['dossiers']:
        lines += ['No dossier passed this bounded replay. Reasons: '+json.dumps(report['withheld_reasons'],sort_keys=True)]
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    report=build(json.loads(pathlib.Path('altcoin_reversal_report.json').read_text()))
    pathlib.Path('research_dossiers.json').write_text(json.dumps(report,indent=2)+'\n')
    pathlib.Path('research_dossiers.md').write_text(markdown(report))
    summary={k:v for k,v in report.items() if k!='dossiers'}
    summary['queue']=[{k:d[k] for k in ('pair','interval','status','entry_trigger_reference_usdt','invalidation_reference_usdt')} for d in report['dossiers']]
    print(json.dumps(summary))

"""Synthetic regressions, never live market or delivery evidence."""
import copy
import unittest
from test_atl_evidence import inputs, NOW, AT
from atl_evidence import dossier, format_research
from multichain_candidate_rotation import rotate

class RepairRegressions(unittest.TestCase):
    def test_provider_research_does_not_require_optional_chart(self):
        observation, details, _ = inputs()
        result = dossier(observation, details, {}, observed_at=AT, now=NOW.timestamp())
        self.assertTrue(result['telegram_research_eligible'])
        self.assertFalse(result['history']['lifetime_verified'])
        self.assertFalse(result['buy_authorized'])
        self.assertIn('2020-01-01', format_research(result))
        self.assertIn('unavailable', format_research(result).lower())

    def test_multichain_tokens_do_not_starve_behind_chain_heads(self):
        rows = [dict(network=n, token_address=str(i)) for n in ('solana','eth') for i in range(6)]
        for budget in (1,2,3):
            selected=set()
            for cursor in range(24):
                result=rotate(rows,per_run=budget,cursor=cursor)
                selected.update((x['network'],x['token_address']) for x in result['selected'])
            self.assertEqual(len(selected),12)

    def test_invalid_atl_date_cannot_be_replayed_as_research(self):
        observation, details, chart = inputs()
        for date in ('garbage','2099-01-01T00:00:00Z',None):
            observation=copy.deepcopy(observation)
            observation['provider_atl_candidate']['source_atl_date']=date
            with self.assertRaises(ValueError):
                dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())

class AuditAndHealthRegressions(unittest.TestCase):
    def test_cadence_audit_preserves_failed_starts_and_missing_cause(self):
        import datetime as dt
        from scanner_cadence import audit_slots
        start=NOW.replace(hour=0,minute=0)
        end=start+dt.timedelta(hours=3)
        runs=[dict(id=1,head_branch='main',event='schedule',run_started_at=start.replace(minute=12).isoformat(),conclusion='failure')]
        report=audit_slots(runs,start,end)
        self.assertEqual(len(report['slots']),3)
        self.assertEqual(report['missing_start_slots'],2)
        self.assertEqual(report['slots'][0]['runs'][0]['conclusion'],'failure')
        self.assertFalse(report['hourly_guarantee'])

    def test_health_separates_delivery_readiness_and_execution(self):
        from pipeline_health import summarize
        reports={name:{} for name in ('scan','reversal','technical_followup','strategy_lab')}
        reports['scan']={'alerts_delivered':0,'research_watch_delivered':0}
        report=summarize({name:'success' for name in reports},reports)
        self.assertEqual(report['execution_status'],'COMPLETED')
        self.assertEqual(report['alert_delivery']['scan']['alerts_delivered'],0)
        self.assertEqual(report['overall_objective'],'BLOCKED')

    def test_gate_join_rejects_symbol_collision_and_preserves_exact_match(self):
        from atl_evidence import gate_listing
        observation,details,chart=inputs()
        asset=dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())['asset']
        evidence=dict(observed_at=AT,currencies=[dict(currency='EX',delisted=False,trade_disabled=False,chains=[dict(name='ETH',addr='0x'+'2'*40)])],pairs=[dict(id='EX_USDT',base='EX',quote='USDT',trade_status='tradable',type='normal',st_tag=False)])
        self.assertEqual(gate_listing(asset,evidence,NOW.timestamp())['status'],'UNVERIFIED')
        evidence['currencies'][0]['chains'][0]['addr']=details['platforms']['ethereum']
        self.assertEqual(gate_listing(asset,evidence,NOW.timestamp())['pairs'],['EX_USDT'])
        evidence['currencies'].append(dict(currency='OTHER',chains=[dict(name='UNKNOWN_CHAIN',addr='unrelated')]))
        result=dossier(observation,details,{},observed_at=AT,now=NOW.timestamp(),gate_evidence=evidence)
        self.assertTrue(result['telegram_research_eligible'])
        evidence['pairs'][0]['trade_status']='untradable'
        self.assertFalse(dossier(observation,details,{},observed_at=AT,now=NOW.timestamp(),gate_evidence=evidence)['telegram_research_eligible'])

    def test_partial_atl_enrichment_retains_deferred_leads_across_pages(self):
        from atl_hourly_research import enrich
        observation,details,chart=inputs()
        state={};observations=[]
        for identifier in ('aaa','bbb','ccc'):
            item=copy.deepcopy(observation);item['provider_id']=identifier;observations.append(item)
        def fetch(url):
            if '/market_chart?' in url:return chart
            result=copy.deepcopy(details);result['id']=url.split('/coins/')[1].split('?')[0];return result
        report=dict(observations=observations)
        enrich(report,state,fetch,now=NOW)
        self.assertEqual(set(state['pending_leads']),{'ccc'})
        enrich(dict(observations=[]),state,fetch,now=NOW)
        self.assertEqual(state['pending_leads'],{})
        self.assertEqual(len(report['candidate_dispositions']),3)

    def test_core_audit_has_one_disposition_for_every_candidate_and_revisit(self):
        from scan_audit import summarize
        row=dict(assessment=dict(decision='WAIT / VERIFY',blockers=['missing security']),notification_outcome='INELIGIBLE',research_notification_outcome='NOT_ELIGIBLE')
        result=summarize({}, {'ineligible':1},[{'key':'a'},{'key':'b'}],[{'key':'a'}],[row])
        self.assertEqual({x['key'] for x in result['candidate_dispositions']},{'a','b'})
        self.assertEqual(result['candidate_dispositions'][1]['reasons'],['missing security'])

    def test_retained_adverse_finding_vetoes_atl_before_transport(self):
        from unittest.mock import patch
        from atl_evidence import notify
        from asset_identity import key
        observation,details,chart=inputs()
        finding=dossier(observation,details,chart,observed_at=AT,now=NOW.timestamp())
        calls=[];state={}
        with patch('technical_watch.retained_negatives',return_value={key('eth',details['platforms']['ethereum'])}):
            result=notify([finding],state,dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='42'),lambda *args:calls.append(args),now=NOW.timestamp())
        self.assertEqual(calls,[]);self.assertEqual(state,{})
        self.assertEqual(result['status'],'WITHHELD_RETAINED_ADVERSE')

    def test_atl_delivery_diagnostics_explain_failed_replay(self):
        from atl_evidence import notify
        result=notify([{}],{}, {},lambda *args:None,now=NOW.timestamp())
        self.assertEqual(result['delivered'],0)
        self.assertEqual(result['decisions'][0]['status'],'REPLAY_FAILED')

    def test_reversal_reports_policy_exclusions_and_exact_deferred_pairs(self):
        from test_reversal_universe import UniverseTests, pair, NOW as MARKET_NOW
        from reversal_universe import collect
        source=UniverseTests().source([pair('LINK'),pair('ONDO'),pair('RENDER')])
        report=collect(fetch=source,now=MARKET_NOW,batch_size=1,allowed_pairs=['LINK_USDT','ONDO_USDT'])
        self.assertEqual(report['coverage']['scope_excluded_pairs'],['RENDER_USDT'])
        self.assertEqual(report['coverage']['selected_pair_ids'],['LINK_USDT'])
        self.assertEqual(report['coverage']['deferred_pair_ids'],['ONDO_USDT'])

    def test_cadence_gap_bypasses_daily_digest_dedup_once_after_recovery(self):
        import tempfile,os,json,pathlib
        from unittest.mock import patch
        from telegram_notify import notify_workflow
        with tempfile.TemporaryDirectory() as folder:
            previous=os.getcwd()
            try:
                os.chdir(folder)
                pathlib.Path('scan_summary.json').write_text(json.dumps(dict(status='completed',github_run_id='9')))
                pathlib.Path('operational_digest_state.json').write_text(json.dumps(dict(version=1,confirmed_day=NOW.date().isoformat())))
                pathlib.Path('scanner_cadence_report.json').write_text(json.dumps(dict(stale_or_missing_core_heartbeat=True,github_run_id='9',checked_at=AT,last_core_success_at='2026-11-07T00:00:00Z')))
                sent=[]
                with patch.dict(os.environ,{'GITHUB_RUN_ID':'9'}):
                    for _ in range(2):notify_workflow('success',now=NOW,sender=lambda message:sent.append(message) or True)
                self.assertEqual(len(sent),1)
                self.assertTrue(sent[0].startswith('BOT HEALTH | OPERATIONAL'))
            finally:os.chdir(previous)

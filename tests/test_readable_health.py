"""Readable production summaries; fixtures do not establish market performance."""
import unittest
from telegram_notify import health_summary

class ReadableHealthTests(unittest.TestCase):
    def report(self):
        return dict(completed_at='2026-11-10T01:00:00Z',candidates=26,buy_candidates_delivered=0,signed_entry_watches_delivered=0,research_watch_delivered=0,
            filter_audit=dict(assessed_candidates=10,discovery_pools_not_selected=16,notification_outcomes=dict(ineligible=10)),suppression_reasons={'REJECT':6,'INSUFFICIENT EVIDENCE':4})
    def test_large_raw_lists_cannot_truncate_performance_or_run_link(self):
        reversal=dict(coverage=dict(selected_pairs=6,liquid_eligible_pairs=15,all_liquid_eligible_pairs=70,scope_excluded_pairs=['NEVER_ECHO_THIS_USDT']*10000),technical_delivery=dict(delivered=0,suppressed={'retained adverse':2,'unchanged':1}))
        paper={'accounts':{'fixture':{'account':{'trades':[],'position':None}}}}
        followup={'hypotheses':{'fixture':{'samples':[{'at_or_above_trigger_observed':False}]}}}
        url='https://github.com/example/repository/actions/runs/1'
        text=health_summary(self.report(),reversal,dict(execution_status='COMPLETED',coverage_status='DEGRADED',admission_status='BLOCKED'),{},paper,followup,url)
        self.assertNotIn('NEVER_ECHO_THIS',text)
        self.assertLess(len(text.encode('utf-16-le'))//2,1800)
        self.assertTrue(text.endswith(url))
        self.assertIn('0 closed paper trades',text)
        self.assertIn('0/1 tracked watches',text)
        self.assertIn('NOT ESTABLISHED',text)
        self.assertIn('02:00 WAT',text)
        self.assertIn('6/15 policy pairs',text)
    def test_missing_performance_is_unknown_never_zero_or_profit(self):
        text=health_summary(self.report(),{}, {}, {},{}, {},'https://github.com/example')
        self.assertIn('unknown closed paper trades',text)
        self.assertIn('unknown/unknown tracked watches',text)
        self.assertIn('NOT ESTABLISHED',text)
    def test_simulated_closed_trades_are_never_labelled_actual_returns(self):
        text=health_summary(self.report(),{}, {}, {},{'accounts':{'fixture':{'account':{'trades':[{},{}],'position':None}}}}, {},'url')
        self.assertIn('2 closed paper trades',text)
        self.assertIn('Paper accounts are simulations',text)
    def test_malformed_optional_fields_do_not_inject_text_or_claim_readiness(self):
        text=health_summary(self.report(),{'coverage':[],'technical_delivery':[]},{'execution_status':'FAKE_SUCCESS'},{},{'accounts':[]},{'hypotheses':[]},'url')
        self.assertNotIn('FAKE_SUCCESS',text)
        self.assertIn('UNKNOWN',text)
        self.assertIn('unknown closed paper trades',text)

    def test_format_upgrade_replaces_unreadable_digest_once_without_erasing_state(self):
        import tempfile,pathlib,json,datetime as dt,os
        from unittest.mock import patch
        from telegram_notify import notify_workflow
        with tempfile.TemporaryDirectory() as folder:
            before=os.getcwd()
            try:
                os.chdir(folder)
                report=self.report();report.update(status='completed',github_run_id='fixture')
                pathlib.Path('scan_summary.json').write_text(json.dumps(report))
                pathlib.Path('operational_digest_state.json').write_text(json.dumps(dict(version=1,confirmed_day='2026-11-10',cadence_gap_confirmed_for='preserved')))
                sent=[];now=dt.datetime(2026,11,10,6,tzinfo=dt.timezone.utc)
                with patch.dict(os.environ,{'GITHUB_RUN_ID':'fixture'}):
                    notify_workflow('success',now=now,sender=lambda text:sent.append(text) or True)
                    result=notify_workflow('success',now=now,sender=lambda text:sent.append(text) or True)
                self.assertEqual(len(sent),1)
                self.assertEqual(result['status'],'SKIPPED_DAILY_DEDUP')
                saved=json.loads(pathlib.Path('operational_digest_state.json').read_text())
                self.assertEqual(saved['cadence_gap_confirmed_for'],'preserved')
                self.assertEqual(saved['confirmed_format_version'],2)
            finally:os.chdir(before)

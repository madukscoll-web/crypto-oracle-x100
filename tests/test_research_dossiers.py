import copy
import unittest
import research_dossiers as d
from test_technical_watch import fixture,NOW


class DossierTests(unittest.TestCase):
    def test_dossier_is_replayed_source_bound_research_and_not_approval(self):
        report,_=fixture()
        result=d.build(report,now=NOW)
        self.assertEqual(result['count'],1)
        item=result['dossiers'][0]
        self.assertEqual(item['pair'],'BCH_USDT')
        self.assertEqual(len(item['sources']),2)
        self.assertIn('raw',item['sources'][0])
        import workflow_state
        self.assertIn('research_dossiers.json',workflow_state.FILES)
        self.assertTrue(all(len(s['raw_sha256'])==64 for s in item['sources']))
        self.assertFalse(item['buy_authorized'])
        self.assertIn('UNKNOWN',item['liquidity_observation']['status'])
        self.assertIn('Outstanding evidence',d.markdown(result))

    def test_missing_or_stale_provenance_cannot_create_dossier(self):
        for mutation in ('missing','stale'):
            report,_=fixture()
            if mutation=='missing':report['results'][0]['provider_evidence']=[]
            else:report['as_of']='2020-01-01T00:00:00+00:00'
            self.assertEqual(d.build(report,now=NOW)['count'],0)

    def test_adverse_screening_is_retained_and_wrong_market_context_is_discarded(self):
        report,_=fixture();row=report['results'][0]
        row['technical_screen']={'security':[{'status':'FAIL','reason':'honeypot'}]}
        row['project_context']={'identity':{'pair':'OTHER_USDT'},'promotional':'bad'}
        item=d.build(report,now=NOW)['dossiers'][0]
        self.assertEqual(item['status'],'WITHHELD_ADVERSE_FINDING')
        self.assertEqual(item['project_context']['identity']['pair'],'BCH_USDT')
        self.assertNotIn('promotional',item['project_context'])

    def test_duplicate_market_timeframe_does_not_fill_review_queue(self):
        report,_=fixture();report['results']*=3
        self.assertEqual(d.build(report,now=NOW)['count'],1)


    def test_hourly_dossier_stage_and_missing_output_are_checked(self):
        import pathlib,pipeline_health
        workflow=(pathlib.Path(__file__).resolve().parents[1]/'.github/workflows/main.yml').read_text()
        self.assertIn('run: python -u research_dossiers.py',workflow)
        self.assertIn('research_dossiers.md',workflow)
        stages={k:'success' for k in ('scan','reversal','technical_followup','strategy_lab','dossiers')}
        reports={k:{} for k in stages if k!='dossiers'}
        result=pipeline_health.summarize(stages,reports)
        self.assertIn('dossiers',result['missing_reports'])

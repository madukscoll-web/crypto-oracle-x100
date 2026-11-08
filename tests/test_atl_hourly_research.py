import copy
import datetime as dt
import unittest
from unittest.mock import patch
from atl_hourly_research import run, main
import pipeline_health

NOW = dt.datetime(2026,11,7,1,tzinfo=dt.timezone.utc)


def row(**changes):
    result = dict(id='example',symbol='ex',market_cap=200000000,
        circulating_supply=200000000,current_price=1,atl=.99,
        atl_date='2025-01-01T00:00:00Z',last_updated='2026-11-07T00:00:00Z')
    result.update(changes)
    return result


def fetch_rows(rows):
    return lambda url: rows if 'page=1&' in url else [row(id='tail',market_cap=100000000,circulating_supply=100000000)]


class HourlyATLTests(unittest.TestCase):
    def test_provider_observations_never_establish_verification(self):
        result=run(now=NOW,fetch=fetch_rows([row()]))
        self.assertEqual(result['fresh_provider_cap_observations'],1)
        self.assertEqual(result['eligible_verified'],0)
        self.assertEqual(result['historical_baselines_validated'],0)
        self.assertEqual(result['provider_atl_candidates'],1)
        observation=result['observations'][0]
        self.assertEqual(observation['cap_classification'],'UNVERIFIED')
        self.assertEqual(observation['provider_reported_cap_category'],'MID_CAP')
        self.assertFalse(observation['telegram_eligible'])
        self.assertFalse(result['buy_authorized'])
        self.assertFalse(result['orders_allowed'])

    def test_cap_boundaries_and_fdv_never_substitutes(self):
        rows=[row(id='below',market_cap=199999999),row(id='boundary'),
              row(id='missing',market_cap=None,fully_diluted_valuation=500000000)]
        result=run(now=NOW,fetch=fetch_rows(rows))
        self.assertEqual([x['provider_id'] for x in result['observations']],['boundary'])
        self.assertEqual(result['market_cap_unverified'],1)

    def test_bad_cap_and_stale_or_future_observations_fail_closed(self):
        for changes in (dict(circulating_supply=1),dict(current_price=True),
                        dict(last_updated='2026-11-08T00:00:00Z'),
                        dict(last_updated='2026-11-06T00:00:00Z'),
                        dict(market_cap='NaN')):
            with self.subTest(changes=changes):
                result=run(now=NOW,fetch=fetch_rows([row(**changes)]))
                self.assertFalse(result['observations'])
                self.assertEqual(result['market_cap_unverified'],1)

    def test_unparseable_or_future_atl_date_does_not_make_candidate(self):
        for value in ('x','2027-01-01T00:00:00Z',None):
            self.assertEqual(run(now=NOW,fetch=fetch_rows([row(atl_date=value)]))['provider_atl_candidates'],0)

    def test_provider_outage_and_empty_partial_responses_are_visible(self):
        def outage(url): raise TimeoutError()
        result=run(now=NOW,fetch=outage)
        self.assertEqual(result['status'],'UNAVAILABLE')
        self.assertEqual(len(result['errors']),2)
        self.assertEqual(result['next_cursor'],2)
        for data in ([],{},None):
            self.assertEqual(run(now=NOW,fetch=lambda url:data)['status'],'UNAVAILABLE')
        result=run(now=NOW,fetch=lambda url:[row()] if 'page=1&' in url else {})
        self.assertEqual(result['status'],'DEGRADED')

    def test_rotation_advances_and_wraps_without_ticker_matching(self):
        def fetch(url):
            return [row(id='first',symbol='BTC')] if 'page=1&' in url else [row(id='tail'+str(i),symbol='BTC') for i in range(100)]
        result=run(now=NOW,fetch=fetch,cursor=3)
        self.assertEqual(result['next_cursor'],4)
        self.assertEqual(len(result['observations']),101)
        self.assertTrue(all(x['cap_classification']=='UNVERIFIED' for x in result['observations']))
        self.assertEqual(run(now=NOW,fetch=fetch,cursor=10)['next_cursor'],2)
        self.assertEqual(run(now=NOW,fetch=fetch_rows([row()]),cursor=3)['next_cursor'],2)

    def test_duplicate_provider_ids_are_degraded(self):
        result=run(now=NOW,fetch=lambda url:[row()])
        self.assertEqual(result['duplicate_rows'],1)
        self.assertEqual(result['status'],'DEGRADED')

    def test_atl_health_cannot_be_green_on_empty_artifact(self):
        reports={k:{} for k in ('scan','reversal','technical_followup','strategy_lab')}
        stages={k:'success' for k in reports};stages['atl']='success'
        for report in (None,{},dict(status='UNAVAILABLE')):
            with self.subTest(report=report):
                r=copy.deepcopy(reports)
                if report is not None:r['atl']=report
                self.assertEqual(pipeline_health.summarize(stages,r)['status'],'DEGRADED')

    def test_main_returns_nonzero_and_preserves_cursor_on_outage(self):
        import tempfile
        from pathlib import Path
        import os
        previous=os.getcwd()
        with tempfile.TemporaryDirectory() as folder:
            try:
                os.chdir(folder)
                with patch('atl_hourly_research.run',return_value=dict(status='UNAVAILABLE',next_cursor=3)):
                    self.assertEqual(main(),1)
                self.assertFalse(Path('atl_research_state.json').exists())
                self.assertTrue(Path('atl_coverage_report.json').exists())
            finally:os.chdir(previous)


class ATLWorkflowTests(unittest.TestCase):
    def test_hourly_stage_health_and_durable_rotation_are_wired(self):
        from pathlib import Path
        import workflow_state
        source=(Path(__file__).resolve().parents[1]/'.github/workflows/main.yml').read_text()
        self.assertIn("cron: '7 * * * *'",source)
        self.assertIn('python -u atl_hourly_research.py',source)
        self.assertLess(source.index('python -u atl_hourly_research.py'),source.index('python -u crypto_oracle_scanner.py'))
        self.assertIn('"atl":"${{ steps.atl_research.outcome }}"',source)
        self.assertIn('            atl_coverage_report.json',source)
        self.assertIn('atl_research_state.json',workflow_state.FILES)
        # Stage timeouts total 30 minutes before setup, state publish and artifacts.
        self.assertIn('    timeout-minutes: 35',source)


class ProviderHealthTests(unittest.TestCase):
    def test_successful_process_with_provider_failures_is_degraded(self):
        reports={k:{} for k in ('scan','reversal','technical_followup','strategy_lab')}
        reports['multichain']={'coverage_audit':{'discovery_failure_count':2},'failures':[{'error_type':'HTTPError'}]}
        stages={k:'success' for k in reports}
        result=pipeline_health.summarize(stages,reports)
        self.assertEqual(result['status'],'DEGRADED')
        self.assertIn('multichain',result['data_degradation'])
        self.assertFalse(result['live_buy_admission_verified'])

    def test_no_provider_failure_is_still_not_objective_completion(self):
        reports={k:{} for k in ('scan','reversal','technical_followup','strategy_lab')}
        reports['multichain']={'coverage_audit':{'discovery_failure_count':0},'failures':[]}
        result=pipeline_health.summarize({k:'success' for k in reports},reports)
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['overall_objective'],'BLOCKED')

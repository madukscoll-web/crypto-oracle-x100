"""Operational health must separate computation, data coverage and delivery."""
import unittest
import pipeline_health


class HealthTests(unittest.TestCase):
    def reports(self):
        return {name:{} for name in ('scan','reversal','technical_followup','strategy_lab')}

    def test_core_coverage_warning_is_not_hidden_by_successful_stages(self):
        reports=self.reports()
        reports['scan']={'warnings':['ProviderRateLimited']}
        result=pipeline_health.summarize({k:'success' for k in reports},reports)
        self.assertEqual(result['status'],'DEGRADED')
        self.assertEqual(result['execution_status'],'COMPLETED')
        self.assertEqual(result['coverage_status'],'DEGRADED')
        self.assertIn('scan',result['data_degradation'])
        self.assertFalse(result['buy_authorized'])

    def test_missing_stage_outcomes_cannot_look_successful(self):
        result=pipeline_health.summarize({},self.reports())
        self.assertEqual(result['status'],'DEGRADED')
        self.assertEqual(result['failed_or_skipped_stages']['scan'],'NOT_REPORTED')
        self.assertEqual(result['execution_status'],'FAILED_OR_INCOMPLETE')

    def test_embedded_delivery_failure_surfaces_even_after_zero_exit(self):
        reports=self.reports()
        reports['technical_followup']={'invalidation_delivery':{'failed':1}}
        result=pipeline_health.summarize({k:'success' for k in reports},reports)
        self.assertIn('technical_followup_delivery',result['failed_or_skipped_stages'])
        self.assertEqual(result['execution_status'],'FAILED_OR_INCOMPLETE')

    def test_partial_observations_remain_distinct_from_workflow_failure(self):
        reports=self.reports()
        reports['technical_followup']={'invalidation_delivery':{'errors':{'bad':'ValueError'}}}
        result=pipeline_health.summarize({k:'success' for k in reports},reports)
        self.assertEqual(result['status'],'DEGRADED')
        self.assertEqual(result['execution_status'],'COMPLETED')
        self.assertIn('technical_followup',result['data_degradation'])


class MalformedReportTests(unittest.TestCase):
    def test_malformed_atl_and_readiness_reports_do_not_crash_or_imply_success(self):
        reports={name:{} for name in ('scan','reversal','technical_followup','strategy_lab')}
        reports.update(atl=[],historical=[],admission=[])
        result=pipeline_health.summarize({name:'success' for name in reports},reports)
        self.assertEqual(result['status'],'DEGRADED')
        self.assertIn('atl',result['missing_reports'])
        self.assertEqual(result['admission_status'],'UNKNOWN')
        self.assertFalse(result['buy_authorized'])

    def test_malformed_delivery_channel_is_visible_degradation(self):
        reports={name:{} for name in ('scan','reversal','technical_followup','strategy_lab')}
        reports['technical_followup']={'invalidation_delivery':['not a diagnostic object']}
        result=pipeline_health.summarize({name:'success' for name in reports},reports)
        self.assertEqual(result['coverage_status'],'DEGRADED')
        self.assertIn('technical_followup',result['data_degradation'])


    def test_malformed_multichain_diagnostics_remain_degraded(self):
        reports={name:{} for name in ('scan','reversal','technical_followup','strategy_lab')}
        reports['multichain']={'coverage_audit':[],'provider_health':[None]}
        result=pipeline_health.summarize({name:'success' for name in reports},reports)
        self.assertIn('multichain',result['data_degradation'])

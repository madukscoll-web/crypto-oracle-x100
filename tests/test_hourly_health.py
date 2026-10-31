import datetime as dt
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import hourly_health

class CadenceTests(unittest.TestCase):
    def rows(self,hours):
        return [dict(id=i,path='.github/workflows/main.yml',event='schedule',head_branch='main',created_at=dt.datetime.fromtimestamp(h*3600,dt.timezone.utc).isoformat(),conclusion='success') for i,h in enumerate(hours)]
    def test_actual_multihour_gap_is_not_successful_hourly_operation(self):
        report=hourly_health.assess(self.rows([0,6.66,11.55]),2,12*3600)
        self.assertEqual(report['status'],'DEGRADED');self.assertFalse(report['hourly_verified'])
        self.assertAlmostEqual(report['gap_seconds'],4.89*3600)
    def test_unrelated_workflow_cannot_fill_missing_scanner_intervals(self):
        rows=self.rows([0,1,2,3]);rows[1]['path']='.github/workflows/other.yml';rows[2]['event']='workflow_dispatch'
        self.assertEqual(hourly_health.assess(rows,3,3*3600)['status'],'DEGRADED')
    def test_one_good_interval_or_absence_never_proves_continuous_operation(self):
        self.assertEqual(hourly_health.assess(self.rows([0,1]),1,3600)['status'],'WITHIN_OBSERVED_CADENCE')
        self.assertFalse(hourly_health.assess(self.rows([0,1]),1,3600)['hourly_verified'])
        self.assertEqual(hourly_health.assess([],1,3600)['status'],'UNKNOWN')
    def test_notification_requires_actual_send_acknowledgement(self):
        with tempfile.TemporaryDirectory() as directory:
            original=os.getcwd()
            try:
                os.chdir(directory)
                env={'GH_TOKEN':'fixture-only','GITHUB_REPOSITORY':'fixture/repo','GITHUB_RUN_ID':'1'}
                with self.assertRaises(RuntimeError):hourly_health.run(env,True,lambda *args:self.rows([0,4]),lambda message:False)
                self.assertIn('FAILED_OR_UNCONFIRMED',pathlib.Path('work/hourly_health.json').read_text())
                report=hourly_health.run(env,True,lambda *args:self.rows([0,4]),lambda message:True)
                self.assertTrue(report['alert_delivered']);self.assertFalse(report['orders_allowed'])
            finally:os.chdir(original)

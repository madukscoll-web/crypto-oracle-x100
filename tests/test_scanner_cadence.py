import datetime as dt
import unittest
import pathlib
from scanner_cadence import decide, finish


class CadenceTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 5, 12, tzinfo=dt.timezone.utc)

    def test_fallback_requires_trusted_source(self):
        self.assertFalse(decide('workflow_run', {}, self.now)[0])
        self.assertTrue(decide('workflow_run', {}, self.now, True)[0])

    def test_success_and_attempt_throttle_independently(self):
        for key, minutes in [('last_core_success_at', 60), ('last_attempt_at', 10)]:
            state = {key: (self.now-dt.timedelta(minutes=minutes)).isoformat()}
            self.assertFalse(decide('workflow_run', state, self.now, True)[0])
        self.assertTrue(decide('schedule', {}, self.now)[0])

    def test_failed_or_stale_summary_never_advances_success(self):
        state = {'last_core_success_at': 'old'}
        for outcome, report in [('failure', {'github_run_id': '1', 'status': 'completed'}),
                                ('success', {'github_run_id': '2', 'status': 'completed'}),
                                ('success', {'github_run_id': '1', 'status': 'failed'})]:
            self.assertEqual(finish(state, report, '1', outcome, self.now)['last_core_success_at'], 'old')
        self.assertEqual(finish(state, {'github_run_id': '1', 'status': 'completed'}, '1', 'success', self.now)['last_core_success_run_id'], '1')

    def test_future_naive_and_invalid_dates_do_not_fake_health(self):
        for stamp in ['bad', '2026-11-05T12:00:00', '2026-11-06T12:00:00+00:00']:
            self.assertTrue(decide('workflow_run', {'last_core_success_at': stamp}, self.now, True)[0])


class CadenceWorkflowFailureTests(unittest.TestCase):
    def test_pre_guard_failure_retains_operational_notification(self):
        workflow=(pathlib.Path(__file__).resolve().parents[1]/'.github/workflows/main.yml').read_text()
        notification=workflow.split('      - name: Notify Telegram when workflow fails\n',1)[1].split('      - name:',1)[0]
        self.assertIn('        if: failure()\n',notification)
        self.assertNotIn("steps.cadence.outputs.run == 'true'",notification)
        self.assertIn('cadence_refresh=${{ steps.cadence_refresh.outcome }}',notification)

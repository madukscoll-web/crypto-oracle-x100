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

    def test_redundant_schedules_do_not_repeat_recent_scans(self):
        recent_success = {'last_core_success_at': (self.now-dt.timedelta(minutes=30)).isoformat()}
        self.assertFalse(decide('schedule', recent_success, self.now)[0])
        self.assertTrue(decide('schedule', recent_success, self.now+dt.timedelta(minutes=26))[0])
        recent_attempt = {'last_attempt_at': (self.now-dt.timedelta(minutes=10)).isoformat()}
        self.assertFalse(decide('schedule', recent_attempt, self.now)[0])
        self.assertTrue(decide('workflow_dispatch', recent_success, self.now)[0])
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


class ExternalTriggerTests(unittest.TestCase):
    """An outside timer dispatches main.yml with trigger=external; it must be throttled."""
    def setUp(self):
        self.now = dt.datetime(2026, 11, 17, 12, tzinfo=dt.timezone.utc)

    def stamp(self, minutes):
        return (self.now - dt.timedelta(minutes=minutes)).isoformat()

    def test_external_dispatch_is_throttled_like_a_schedule(self):
        self.assertFalse(decide('workflow_dispatch', {'last_core_success_at': self.stamp(30)}, self.now, trigger='external')[0])
        self.assertFalse(decide('workflow_dispatch', {'last_attempt_at': self.stamp(10)}, self.now, trigger='external')[0])

    def test_external_dispatch_runs_when_due_or_heartbeat_missing(self):
        self.assertTrue(decide('workflow_dispatch', {'last_core_success_at': self.stamp(56)}, self.now, trigger='external')[0])
        self.assertTrue(decide('workflow_dispatch', {}, self.now, trigger='external')[0])
        self.assertTrue(decide('workflow_dispatch', {'last_core_success_at': 'garbage'}, self.now, trigger='external')[0])

    def test_manual_or_unknown_trigger_always_runs(self):
        recent = {'last_core_success_at': self.stamp(5), 'last_attempt_at': self.stamp(2)}
        for trigger in (None, '', 'manual', 'EXTERNAL', 'external ', 7, ['external']):
            self.assertTrue(decide('workflow_dispatch', recent, self.now, trigger=trigger)[0], trigger)

    def test_trigger_value_does_not_affect_other_events(self):
        recent = {'last_core_success_at': self.stamp(5)}
        self.assertFalse(decide('schedule', recent, self.now, trigger='manual')[0])
        self.assertFalse(decide('workflow_run', recent, self.now, True, trigger='manual')[0])
        self.assertTrue(decide('push', recent, self.now, trigger='external')[0])

    def test_guard_cli_reads_the_dispatch_input_and_fails_open_on_malformed_payload(self):
        import json, os, subprocess, sys, tempfile
        root = pathlib.Path(__file__).resolve().parents[1]
        recent = {'last_core_success_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        cases = [({'inputs': {'trigger': 'external'}}, 'false'), ({'inputs': {'trigger': 'manual'}}, 'true'),
                 ({'inputs': 'external'}, 'true'), ({'inputs': ['external']}, 'true'), ({}, 'true')]
        for payload, expected in cases:
            with tempfile.TemporaryDirectory() as folder:
                folder = pathlib.Path(folder)
                (folder / 'scanner_runtime_state.json').write_text(json.dumps(recent))
                (folder / 'event.json').write_text(json.dumps(payload))
                out = folder / 'out.txt'
                env = dict(os.environ, GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_EVENT_PATH=str(folder / 'event.json'),
                           GITHUB_OUTPUT=str(out), GITHUB_RUN_ID='1')
                subprocess.run([sys.executable, str(root / 'scanner_cadence.py'), 'guard'], cwd=folder, env=env, check=True,
                               capture_output=True, text=True)
                self.assertIn('run=' + expected, out.read_text(), payload)

    def test_workflow_declares_the_trigger_input(self):
        text = (pathlib.Path(__file__).resolve().parents[1] / '.github/workflows/main.yml').read_text()
        self.assertIn('inputs:\n      trigger:', text)

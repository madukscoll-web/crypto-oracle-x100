"""Regression: stale heartbeat must never become a market Telegram alert."""
import datetime as dt
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from telegram_notify import notify_workflow


class TelegramCadenceNoiseTests(unittest.TestCase):
    def test_stale_heartbeat_does_not_send_operational_research_watch(self):
        now = dt.datetime(2026, 11, 11, 18, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            with patch('os.getcwd'):
                old = pathlib.Path.cwd()
                try:
                    os.chdir(directory)
                    pathlib.Path('scan_summary.json').write_text(json.dumps({
                        'status': 'completed', 'github_run_id': '123',
                        'completed_at': now.isoformat()}))
                    pathlib.Path('scanner_cadence_report.json').write_text(json.dumps({
                        'stale_or_missing_core_heartbeat': True,
                        'last_core_success_at': None, 'github_run_id': '123',
                        'checked_at': now.isoformat()}))
                    messages = []
                    def sender(message):
                        messages.append(message)
                        return True
                    with patch.dict(os.environ, {'GITHUB_RUN_ID': '123',
                                                 'GITHUB_REPOSITORY': 'owner/repo'}):
                        result = notify_workflow('success', now=now, sender=sender)
                    self.assertEqual(result['status'], 'BOT_API_CONFIRMED')
                    self.assertEqual(len(messages), 1)
                    self.assertTrue(messages[0].startswith('SYSTEM HEALTH REPORT'))
                    self.assertNotIn('BOT HEALTH | OPERATIONAL', messages[0])
                    self.assertNotIn('RESEARCH WATCH', messages[0])
                    self.assertTrue(pathlib.Path('scanner_cadence_report.json').exists())
                finally:
                    os.chdir(old)


if __name__ == '__main__':
    unittest.main()

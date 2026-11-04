"""Incident regressions: noisy discovery cannot bypass evidence gates."""
import contextlib
import datetime as dt
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import crypto_oracle_scanner as scanner
import telegram_notify as telegram
import workflow_state
import opportunity_alerts


class AlertPolicyTests(unittest.TestCase):
    def test_spoofed_native_symbol_with_large_volume_is_silent(self):
        item = dict(network='solana', token_symbol='BTC',
                    token_address='C5xph2yL6qMdxmuLGxJBkGpmuDFfyi5fqkBNhvL6pump',
                    liquidity=482817, volume=5046223, score=100,
                    risk_category='WAIT / VERIFY',
                    token_identity_status='Base token from GeckoTerminal pool relationship')
        self.assertFalse(scanner.research_alert_eligible(item))
        self.assertFalse(scanner.telegram_eligible(item))

    def test_claimed_labels_do_not_override_missing_evidence(self):
        for label in ('DISCARD', 'WAIT AND VERIFY', 'ENTRY WATCH', 'VERIFIED BUY'):
            item = dict(canonical_outcome=label, buy_authorized=True, trade_ready=True)
            self.assertFalse(scanner.research_alert_eligible(item))

    def test_canonical_watch_with_critical_gaps_is_silent(self):
        with patch.object(scanner.canonical_outcomes, 'assess', return_value={
                'outcome': 'ENTRY WATCH', 'critical_gaps': ['sellability unknown']}), \
                patch('evidence_audit.audit', return_value={'trade_ready': True}):
            self.assertFalse(scanner.research_alert_eligible({}))

    def test_policy_exception_is_silent(self):
        with patch.object(scanner.canonical_outcomes, 'assess', side_effect=ValueError):
            self.assertFalse(scanner.research_alert_eligible({}))

    def test_other_delivery_route_and_cached_parts_cannot_bypass_policy(self):
        for parts in (None, ['previously formatted unverified alert']):
            calls = []
            with self.assertRaisesRegex(RuntimeError, 'critical evidence incomplete'):
                opportunity_alerts.deliver({}, {'classification': 'VERIFIED BUY'}, 'NEW',
                    {'TELEGRAM_BOT_TOKEN': 'fixture', 'TELEGRAM_CHAT_ID': '42'},
                    transport=lambda *args: calls.append(args), parts=parts)
            self.assertFalse(calls)


class DailyDigestTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.previous = os.getcwd()
        os.chdir(self.folder.name)
        self.addCleanup(os.chdir, self.previous)
        pathlib.Path('scan_summary.json').write_text(json.dumps({
            'status': 'completed', 'github_run_id': 'fixture'}))
        self.now = dt.datetime(2026, 11, 4, 12, tzinfo=dt.timezone.utc)

    def notify(self, sender, now=None):
        with patch.dict(os.environ, {'GITHUB_RUN_ID': 'fixture'}), \
                patch.object(telegram, 'workflow_message', return_value='Pipeline counts only'):
            return telegram.notify_workflow('success', now=now or self.now, sender=sender)

    def test_daily_dedup_and_lagos_midnight(self):
        sent = []
        def sender(message):
            sent.append(message)
            return True
        self.assertEqual(self.notify(sender)['status'], 'BOT_API_CONFIRMED')
        self.assertEqual(self.notify(sender)['status'], 'SKIPPED_DAILY_DEDUP')
        self.assertEqual(self.notify(sender, self.now.replace(hour=23))['status'], 'BOT_API_CONFIRMED')
        self.assertEqual(len(sent), 2)

    def test_unconfirmed_send_does_not_advance_day(self):
        with self.assertRaises(telegram.NotificationError):
            self.notify(lambda _: None)
        self.assertFalse(pathlib.Path('operational_digest_state.json').exists())
        self.assertEqual(self.notify(lambda _: True)['status'], 'BOT_API_CONFIRMED')

    def test_corrupt_state_fails_without_sending(self):
        pathlib.Path('operational_digest_state.json').write_text('{')
        sent = []
        with self.assertRaises(ValueError):
            self.notify(sent.append)
        self.assertFalse(sent)

    def test_failed_or_foreign_run_never_sends(self):
        for report in ({'status': 'failed'}, {'status': 'completed', 'github_run_id': 'other'}):
            pathlib.Path('scan_summary.json').write_text(json.dumps(report))
            sent = []
            with self.assertRaises(telegram.NotificationError):
                self.notify(sent.append)
            self.assertFalse(sent)

    def test_digest_marker_is_published_after_send(self):
        self.assertIn('operational_digest_state.json', workflow_state.FILES)
        workflow = pathlib.Path(self.previous, '.github/workflows/main.yml').read_text()
        self.assertLess(workflow.index('python telegram_notify.py success'),
                        workflow.index('python workflow_state.py publish'))

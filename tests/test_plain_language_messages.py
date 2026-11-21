"""Plain-language wording of operational messages; labels and safety statements must survive."""
import os
import re
import unittest
from unittest.mock import patch
import technical_followup as tf
import telegram_notify as tn

ROW = {'pair': 'SOL_USDT', 'alert': {'interval': '4h', 'invalidation': '80',
                                     'delivered_at': '2026-11-07T10:00:00+00:00'}}
BOOK = {'best_bid': '78.4'}
SAMPLE = {'observed_at': '2026-11-07T14:05:09Z', 'source_url': 'https://api.gateio.ws/x'}
JARGON = ('hypothesis', 'invalidation reference', 'between-sample', 'realized loss', 'authority is inferred',
          'heartbeat', 'Withdraw this')


class InvalidatedSetupTests(unittest.TestCase):
    def text(self, row=ROW, book=BOOK, sample=SAMPLE):
        return tf.invalidation_text(row, book, sample)

    def test_first_line_is_exact_label(self):
        self.assertEqual(self.text().splitlines()[0], 'INVALIDATED SETUP')
        from research_notice import _issue
        self.assertEqual(_issue('INVALIDATED SETUP', self.text()).splitlines()[0].strip(), 'INVALIDATED SETUP')

    def test_says_what_happened_and_what_to_do_in_plain_words(self):
        t = self.text()
        self.assertIn('Price now: 78.4 USDT. Cancel line: 80 USDT (2.0% below it)', t)
        self.assertIn('What to do: nothing', t)
        self.assertIn('Earlier alert sent: 07 Nov 2026 10:00 UTC', t)
        self.assertIn('Price checked: 07 Nov 2026 14:05 UTC', t)
        for word in JARGON:
            self.assertNotIn(word, t)

    def test_safety_statements_survive(self):
        t = self.text()
        for phrase in ('has NOT bought or sold', 'Nothing was executed or stopped out',
                       'not advice to buy or sell', 'one price check'):
            self.assertIn(phrase, t)
        self.assertNotRegex(t, r'(?i)\bBUY (CANDIDATE|NOW)\b')

    def test_malformed_values_never_crash_or_invent(self):
        row = {'pair': 'X_USDT', 'alert': {'interval': '1h', 'invalidation': 'abc', 'delivered_at': 'junk'}}
        t = self.text(row, {'best_bid': 'nan?'}, {'observed_at': None, 'source_url': 's'})
        self.assertIn('time unknown', t)
        self.assertNotIn('below it', t)
        self.assertEqual(t.splitlines()[0], 'INVALIDATED SETUP')

    def test_percent_helper(self):
        self.assertEqual(tf._percent_below('78', '80'), '2.5%')
        self.assertIsNone(tf._percent_below('81', '80'))
        self.assertIsNone(tf._percent_below('1', '0'))
        self.assertIsNone(tf._percent_below('x', '1'))


class HealthAndFailureTests(unittest.TestCase):
    def test_failure_messages_are_plain_and_keep_labels(self):
        env = {'GITHUB_REPOSITORY': 'o/r', 'GITHUB_RUN_ID': '1'}
        with patch.dict(os.environ, dict(env, FAILED_STAGES='scan=failure')):
            critical = tn.workflow_message('failure')
        with patch.dict(os.environ, dict(env, FAILED_STAGES='scan=success, technical_followup=failure')):
            health = tn.workflow_message('failure')
        self.assertEqual(critical.splitlines()[0], 'CRITICAL SYSTEM FAILURE')
        self.assertEqual(health.splitlines()[0], 'SYSTEM HEALTH REPORT')
        self.assertIn('did not finish', critical)
        self.assertIn('main market scan worked', health)
        for t in (critical, health):
            self.assertIn('cannot trade', t)
            self.assertIn('/o/r/actions/runs/1', t)
            self.assertNotIn('pipeline completion', t)

    def test_plain_time_helper(self):
        self.assertEqual(tn._plain_time('2026-11-07T01:00:00Z'), '07 Nov 2026 01:00 UTC')
        self.assertEqual(tn._plain_time(None), 'not recorded')
        self.assertEqual(tn._plain_time('garbage'), 'not recorded')


if __name__ == '__main__':
    unittest.main()

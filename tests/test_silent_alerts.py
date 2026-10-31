"""Regression tests for fail-closed DEX Telegram eligibility."""
import unittest
from unittest.mock import patch
import crypto_oracle_scanner as scanner


class SilentAlertsTests(unittest.TestCase):
    def test_discard_is_silent_even_with_claimed_trade_ready(self):
        with patch.object(scanner, 'decision_summary', return_value=('DISCARD', 'bad')), \
             patch('evidence_audit.audit', return_value={'trade_ready': True}), \
             patch.object(scanner, 'validate_execution_evidence', return_value=True):
            self.assertFalse(scanner.telegram_eligible({}))

    def test_incomplete_is_silent(self):
        with patch.object(scanner, 'decision_summary', return_value=('WAIT AND VERIFY', 'missing')):
            self.assertFalse(scanner.telegram_eligible({}))

    def test_buy_candidate_without_audit_is_silent(self):
        with patch.object(scanner, 'decision_summary', return_value=('BUY CANDIDATE — REVIEW ENTRY', '')), \
             patch('evidence_audit.audit', return_value={'trade_ready': False}):
            self.assertFalse(scanner.telegram_eligible({}))

    def test_candidate_without_execution_is_silent(self):
        with patch.object(scanner, 'decision_summary', return_value=('BUY CANDIDATE — REVIEW ENTRY', '')), \
             patch('evidence_audit.audit', return_value={'trade_ready': True}), \
             patch.object(scanner, 'validate_execution_evidence', return_value=False):
            self.assertFalse(scanner.telegram_eligible({}))

    def test_fully_verified_candidate_is_eligible(self):
        with patch('authenticated_admission.evaluate', return_value={'safety_verified': True, 'entry_status':'READY'}):
            self.assertTrue(scanner.telegram_eligible({}))

    def test_malformed_evidence_fails_closed(self):
        with patch.object(scanner, 'decision_summary', side_effect=KeyError('bad')):
            self.assertFalse(scanner.telegram_eligible({}))


if __name__ == '__main__':
    unittest.main()
